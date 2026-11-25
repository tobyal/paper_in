"""One-time M0 migration. Stop its service first; source is opened read-only."""
import argparse
import copy
import json
import shutil
import sqlite3
import uuid
from pathlib import Path
import numpy as np
from .settings import ROOT, ASSETS, PROJECT
from .storage import Store, atomic_json, now
from .prepare import sha
from .spatial import inside, transform, overview


def migrate(source):
    source=Path(source).resolve()
    assert source!=ROOT and source.is_relative_to(PROJECT), 'Use a separate project-local source'
    assert not (ROOT/'.m0.sqlite3').exists(), 'Target database exists; refusing to replace annotations'
    provenance=json.loads((ASSETS/'source_manifest.json').read_text())
    assert provenance['geometry_source']['representation']=='native_3dgs'
    old_provenance=json.loads((source/'.assets/source_manifest.json').read_text())
    old_files={x['path']:x['sha256'] for x in old_provenance['source_files']}
    for item in provenance['source_files']:
        if item['path'] in old_files and ('colmap/' in item['path'] or 'camera_split' in item['path']):
            assert old_files[item['path']]==item['sha256'], 'COLMAP frame/split mismatch'
    assert json.loads((source/'.assets/images.json').read_text())==json.loads((ASSETS/'images.json').read_text()), 'Image/camera manifest changed'
    src=sqlite3.connect('file:'+str(source/'.m0.sqlite3')+'?mode=ro',uri=True)
    backup=PROJECT/'backups'/('m0_before_native3dgs_'+uuid.uuid4().hex[:12]);backup.mkdir(parents=True)
    snapshot=sqlite3.connect(backup/'state.sqlite3');src.backup(snapshot);src.close()
    old=json.loads(snapshot.execute('SELECT state FROM revisions ORDER BY revision DESC LIMIT 1').fetchone()[0])
    drafts=list(snapshot.execute('SELECT key,content,updated_at FROM drafts'));snapshot.close()
    atomic_json(backup/'state.json',old)
    for name in ('.artifacts','.inference','versions','operation_history'):
        if (source/name).exists():shutil.copytree(source/name,backup/name)
    # Copy M0's own image references/candidates; never import paper_eli segmentation results.
    for name in ('.artifacts/references','.artifacts/objects','.inference'):
        if (source/name).exists():shutil.copytree(source/name,ROOT/name)
    xyz=np.fromfile(ASSETS/'positions.bin',dtype='<f4').reshape(-1,3)
    rgb=np.fromfile(ASSETS/'colors.bin',dtype='uint8').reshape(-1,3)
    ids=np.load(ASSETS/'display_indices.npy')
    state=copy.deepcopy(old);scene=state['scene']
    chosen=ids[inside(transform(xyz,scene['transform']),scene['bbox'])]
    assert len(chosen)>=100
    folder=Path('.artifacts/scene')/(scene['coordinate_version']+'_native3dgs');(ROOT/folder).mkdir(parents=True)
    np.save(ROOT/folder/'scene_gaussian_indices.npy',chosen)
    overview(ROOT/folder/'scene_overview.jpg',xyz,rgb,scene['transform'],scene['bbox'])
    scene['artifacts']={n:str(folder/n) for n in ('scene_gaussian_indices.npy','scene_overview.jpg')}
    scene['gaussian_count']=len(chosen)
    for oid,o in state['objects'].items():
        if o.get('deleted'):continue
        target=Path('.artifacts/objects')/oid/'native3dgs/bbox_preview.jpg'
        overview(ROOT/target,xyz,rgb,scene['transform'],scene['bbox'],o['bbox']);o['preview_path']=str(target)
    state.update(dataset_id='m0_3dgs_'+uuid.uuid4().hex,revision=old['revision']+1,updated_at=now(),last_frozen_version=None)
    state['migration']=dict(source_root=str(source.relative_to(PROJECT)),source_dataset_id=old['dataset_id'],source_revision=old['revision'],
                            source_representation='2dgs',target_representation='native_3dgs',backup=str(backup.relative_to(PROJECT)),
                            coordinate_transform_unchanged=True,human_fields_preserved=True,gaussian_indices_regenerated=True,
                            previous_frozen_versions_preserved_in_source=True)
    # A new dataset history starts with an explicit migration; never relabel old 2DGS revisions as 3DGS.
    db=sqlite3.connect(ROOT/'.m0.sqlite3')
    db.executescript('CREATE TABLE revisions (revision INTEGER PRIMARY KEY,state TEXT NOT NULL,event TEXT NOT NULL); CREATE TABLE drafts (key TEXT PRIMARY KEY,content TEXT NOT NULL,updated_at TEXT NOT NULL);')
    db.execute('INSERT INTO revisions VALUES(?,?,?)',(state['revision'],json.dumps(state),json.dumps(dict(action='migrate.native3dgs',at=now(),**state['migration']))))
    for key,content,updated in drafts:
        draft=json.loads(content)
        if key=='workspace' and draft.get('base_revision')==old['revision']:
            draft['base_revision']=state['revision']
            # Preserve dirty geometry/text. Replace only derived bindings to the retired PLY.
            if draft.get('sceneDraft'):
                draft['sceneDraft']['artifacts']=scene['artifacts']
                draft['sceneDraft']['gaussian_count']=scene['gaussian_count']
            o=draft.get('objectDraft')
            if o and o.get('object_id') in state['objects']:
                o['preview_path']=state['objects'][o['object_id']].get('preview_path')
        db.execute('INSERT INTO drafts VALUES(?,?,?)',(key,json.dumps(draft),updated))
    db.commit();db.close()
    result=Store(ROOT);assert result.read()==state;result.db.close()
    # Actual saved human fields and optional native-pixel references must be byte-for-byte equivalent.
    for key in ('bbox','transform','coordinate_version','status','floor_confirmed','directions_confirmed'):
        assert state['scene'][key]==old['scene'][key],key
    for oid,o in old['objects'].items():
        assert {k:v for k,v in o.items() if k!='preview_path'}=={k:v for k,v in state['objects'][oid].items() if k!='preview_path'}
    summary=dict(status='passed',root=str(ROOT),old_revision=old['revision'],new_revision=state['revision'],
                 gaussians=len(xyz),selected_gaussians=len(chosen),drafts_preserved=len(drafts),backup=str(backup),
                 geometry_sha256=provenance['geometry_source']['sha256'],source_database_snapshot_sha256=sha(backup/'state.sqlite3'))
    atomic_json(ROOT/'MIGRATION.json',summary);atomic_json(PROJECT/'logs/m0_native3dgs_migration.json',summary)
    print(json.dumps(summary))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',required=True)
    migrate(parser.parse_args().source)
