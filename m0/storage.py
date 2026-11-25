"""Transactional revision store plus regenerable standard JSON materializations."""
import copy
import datetime as dt
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
import numpy as np


def now(): return dt.datetime.now(dt.timezone.utc).isoformat()


def atomic_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    os.replace(tmp, path)


def initial():
    core = []
    for key, zh, inverse, target in [('near', '邻近', 'near', 'object'), ('left_of', '位于左侧', 'right_of', 'object'), ('right_of', '位于右侧', 'left_of', 'object'), ('inside_region', '位于区域内', None, 'region')]:
        core.append(dict(name=key, label_zh=zh, label_en=key.replace('_', ' '), subject_type='object', object_type=target,
                         directional=key != 'near', inverse=inverse, coordinate_frame='industrial',
                         rule='', distance_definition='', threshold=None, units='sfm_relative', source='M0 core vocabulary; rule requires human definition'))
    return dict(schema_version='m0-1.0', dataset_id='m0_' + uuid.uuid4().hex, revision=0, updated_at=now(),
                coordinate_system=None, regions=[], scene_reference_views=[], geometry_verified=False,
                objects={}, annotations={}, descriptions={}, coarse_rois={}, relation_schema=core,
                known_relations=[], semantic_queries=[], reference_relations=[], relational_queries=[],
                approvals={}, stale_steps=[], changes=[], last_frozen_version=None)


class Store:
    def __init__(self, root):
        self.root = Path(root); self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(self.root / '.m0.sqlite3'), check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL'); self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS revisions (revision INTEGER PRIMARY KEY, state TEXT NOT NULL, event TEXT NOT NULL); CREATE TABLE IF NOT EXISTS drafts (key TEXT PRIMARY KEY, content TEXT NOT NULL, updated_at TEXT NOT NULL);')
        if not self.db.execute('SELECT 1 FROM revisions LIMIT 1').fetchone():
            s = initial(); self.db.execute('INSERT INTO revisions VALUES (0,?,?)', (json.dumps(s), json.dumps(dict(action='initialize', at=now())))); self.db.commit()
        self.materialize(self.read())

    def read(self):
        with self.lock: return json.loads(self.db.execute('SELECT state FROM revisions ORDER BY revision DESC LIMIT 1').fetchone()[0])

    def mutate(self, expected, action, step, actor, update):
        with self.lock:
            s = self.read()
            if expected != s['revision']: raise ValueError('REVISION_CONFLICT: 请刷新最新数据后重试，未覆盖其他编辑。')
            update(s)
            s['revision'] += 1; s['updated_at'] = now()
            if step:
                for n in range(step, 8): s['approvals'].pop(str(n), None)
                s['stale_steps'] = sorted(set(s['stale_steps']) | set(range(step + 1, 8)))
            event = dict(revision=s['revision'], at=now(), actor=actor, action=action, affected_steps=list(range(step + 1, 8)) if step else [])
            s['changes'] = (s['changes'] + [event])[-30:]
            # A committed SQLite revision is authoritative; JSON projections are recovered on startup.
            self.db.execute('INSERT INTO revisions VALUES (?,?,?)', (s['revision'], json.dumps(s, allow_nan=False), json.dumps(event)))
            self.db.commit(); self.materialize(s)
            return s

    def materialize(self, s):
        files = {'priors/scene/coordinate_system.json': s['coordinate_system'], 'priors/scene/regions.json': s['regions'],
                 'priors/scene/scene_reference_views.json': s['scene_reference_views'], 'priors/objects/object_catalog.json': list(s['objects'].values()),
                 'priors/objects/object_descriptions.json': s['descriptions'], 'priors/spatial/coarse_rois.json': s['coarse_rois'],
                 'priors/relations/relation_schema.json': s['relation_schema'], 'priors/relations/known_relations.json': s['known_relations'],
                 'ground_truth/semantic_queries.json': s['semantic_queries'], 'ground_truth/reference_relations.json': s['reference_relations'],
                 'ground_truth/relational_queries.json': s['relational_queries']}
        if s['coordinate_system']:
            p = self.root / 'priors/scene/coordinate_transform.npy'; p.parent.mkdir(parents=True, exist_ok=True)
            with open(p.with_suffix('.tmp'), 'wb') as f: np.save(f, np.asarray(s['coordinate_system']['transform']))
            os.replace(p.with_suffix('.tmp'), p)
        for oid in s['objects']:
            for scope, prefix in [('priors', 'priors/masks'), ('ground_truth', 'ground_truth/heldout_masks')]:
                anns = [a for a in s['annotations'].values() if a['object_id'] == oid and a['scope'] == scope]
                base = f'{prefix}/{oid}'
                files.update({base + '/annotations.json': anns, base + '/reference_views.json': [a['image_id'] for a in anns],
                              base + '/prompts.json': {a['image_id']: a.get('prompts', {}) for a in anns},
                              base + '/visibility.json': {a['image_id']: a['visibility'] for a in anns}})
        for path, value in files.items(): atomic_json(self.root / path, value)
        manifest = dict(schema_version=s['schema_version'], dataset_id=s['dataset_id'], revision=s['revision'], updated_at=s['updated_at'],
                        approvals=s['approvals'], stale_steps=s['stale_steps'], source_manifest='.assets/source_manifest.json',
                        priors_only_for_modeling=True, ground_truth_for_evaluation_only=True, last_frozen_version=s['last_frozen_version'])
        atomic_json(self.root / 'PRIOR_MANIFEST.json', manifest)
        for row in self.db.execute('SELECT revision,event FROM revisions'):
            p = self.root / 'operation_history' / f'{row[0]:08d}.json'
            if not p.exists(): atomic_json(p, json.loads(row[1]))

    def draft(self, key, value=None):
        with self.lock:
            if value is not None:
                self.db.execute('INSERT OR REPLACE INTO drafts VALUES (?,?,?)', (key, json.dumps(value), now())); self.db.commit()
            row = self.db.execute('SELECT content,updated_at FROM drafts WHERE key=?', (key,)).fetchone()
            return dict(content=json.loads(row[0]), updated_at=row[1]) if row else None

    def history(self):
        with self.lock: return [json.loads(r[0]) for r in self.db.execute('SELECT event FROM revisions ORDER BY revision DESC LIMIT 300')]
