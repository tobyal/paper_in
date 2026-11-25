"""V2 transactional state. Source geometry and V1 data are never mutated."""
import datetime as dt
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import uuid
import numpy as np

def now(): return dt.datetime.now(dt.timezone.utc).isoformat()

def atomic_json(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(tmp,path)

def copy_atomic(source,target):
    target=Path(target);target.parent.mkdir(parents=True,exist_ok=True)
    tmp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.tmp');shutil.copy2(source,tmp);os.replace(tmp,target)

class Store:
    def __init__(self,root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.lock=threading.RLock()
        self.db=sqlite3.connect(str(self.root/'.m0.sqlite3'),check_same_thread=False)
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')
        self.db.executescript('CREATE TABLE IF NOT EXISTS revisions (revision INTEGER PRIMARY KEY, state TEXT NOT NULL, event TEXT NOT NULL); CREATE TABLE IF NOT EXISTS drafts (key TEXT PRIMARY KEY, content TEXT NOT NULL, updated_at TEXT NOT NULL);')
        if not self.db.execute('SELECT 1 FROM revisions LIMIT 1').fetchone():
            initial=json.loads((self.root/'.assets/initial_scene.json').read_text())
            scene=dict(bbox=initial['bbox'],transform=initial['transform'],coordinate_version='coord_'+uuid.uuid4().hex[:12],
                       status='draft',floor_confirmed=False,directions_confirmed=False,estimation=initial['estimation'],artifacts={})
            s=dict(schema_version='m0-2.0',dataset_id='m0v2_'+uuid.uuid4().hex,revision=0,updated_at=now(),scene=scene,objects={},last_frozen_version=None)
            self.db.execute('INSERT INTO revisions VALUES(0,?,?)',(json.dumps(s),json.dumps(dict(action='initialize_geometry_only',at=now()))));self.db.commit()
        if self.read()['schema_version']!='m0-2.0':raise RuntimeError('V2 requires a separate data directory. V1 is read-only.')
        self.materialize(self.read())
    def read(self):
        with self.lock:return json.loads(self.db.execute('SELECT state FROM revisions ORDER BY revision DESC LIMIT 1').fetchone()[0])
    def mutate(self,expected,action,actor,update):
        with self.lock:
            s=self.read()
            if expected!=s['revision']:raise ValueError('REVISION_CONFLICT: 数据已更新，请刷新；本次编辑未覆盖已保存内容。')
            update(s);s['revision']+=1;s['updated_at']=now()
            event=dict(revision=s['revision'],at=now(),actor=actor,action=action)
            self.db.execute('INSERT INTO revisions VALUES(?,?,?)',(s['revision'],json.dumps(s,allow_nan=False),json.dumps(event)));self.db.commit()
            self.materialize(s);return s
    def materialize(self,s):
        self.write_dataset(self.root,s)
        for rev,event in self.db.execute('SELECT revision,event FROM revisions'):
            p=self.root/'operation_history'/f'{rev:08d}.json'
            if not p.exists():atomic_json(p,json.loads(event))
    def write_dataset(self,dest,s):
        dest=Path(dest);scene=s['scene'];t=np.asarray(scene['transform']);box=scene['bbox'];bottom=np.asarray(box['center'])-np.array([0,0,box['size'][2]/2])
        coord=dict(coordinate_frame='industrial',parent_frame='colmap_raw',coordinate_version=scene['coordinate_version'],
                   units='sfm_relative',transform=t.tolist(),inverse_transform=np.linalg.inv(t).tolist(),
                   convention='column vectors: p_industrial = T @ p_colmap; +X right +Y forward +Z up; right-handed',
                   floor_plane_colmap=[*t[2,:3].tolist(),float(t[2,3]-bottom[2])] if scene['floor_confirmed'] else None,
                   floor_confirmed=scene['floor_confirmed'],directions_confirmed=scene['directions_confirmed'],review_status=scene['status'])
        atomic_json(dest/'scene/scene_bbox.json',{**box,'coordinate_frame':'industrial','coordinate_version':scene['coordinate_version'],'units':'sfm_relative','review_status':scene['status'],'purpose':'research spatial extent, not segmentation'})
        atomic_json(dest/'scene/coordinate_system.json',coord)
        path=dest/'scene/coordinate_transform.npy';tmp=path.with_suffix('.tmp')
        with open(tmp,'wb') as f:np.save(f,t)
        os.replace(tmp,path)
        for name,source in scene.get('artifacts',{}).items():copy_atomic(self.root/source,dest/'scene'/name)
        catalog=[]
        # Only regenerate current materialized projections; immutable artifacts/history remain.
        active_ids={oid for oid,o in s['objects'].items() if not o.get('deleted')}
        for old in (dest/'objects').glob('obj_*'):
            if old.is_dir() and old.name not in active_ids:shutil.rmtree(old)
        for oid,o in s['objects'].items():
            if o.get('deleted'):continue
            catalog.append({k:o[k] for k in ('object_id','name_zh','name_en','granularity','status','coordinate_version')})
            base=dest/'objects'/oid
            atomic_json(base/'coarse_bbox.json',{'quaternion':[0,0,0,1],**o['bbox'],'box_type':'OBB','rotation_convention':'quaternion xyzw; box-local to industrial; size along local axes','object_id':oid,'coordinate_frame':'industrial','coordinate_version':o['coordinate_version'],'units':'sfm_relative','purpose':'M2 search space only; not a final instance','review_status':o['status']})
            atomic_json(base/'description.json',{k:o.get(k,'') for k in ('object_id','name_zh','name_en','description_zh','description_en','status','source','reviewer')})
            if o.get('preview_path'):copy_atomic(self.root/o['preview_path'],base/'bbox_preview.jpg')
            ref=o.get('reference')
            if (not ref or ref.get('status')!='confirmed') and (base/'optional_reference').exists():shutil.rmtree(base/'optional_reference')
            if ref and ref.get('status')=='confirmed':
                folder=base/'optional_reference';atomic_json(folder/'reference.json',ref);atomic_json(folder/'prompts.json',ref['prompts'])
                for key,name in [('mask_path','mask.png'),('overlay_path','overlay.jpg'),('edit_history_path','edits.json')]:copy_atomic(self.root/ref[key],folder/name)
                for i,source in enumerate(ref.get('original_mask_paths',[])):copy_atomic(self.root/source,folder/'original'/f'candidate_{i}.png')
        atomic_json(dest/'objects/object_catalog.json',catalog)
        provenance=json.loads((self.root/'.assets/source_manifest.json').read_text())
        geometry=next(x for x in provenance['source_files'] if '03_gaussian_pruning' in x['path'])
        manifest=dict(schema_version=s['schema_version'],dataset_id=s['dataset_id'],revision=s['revision'],updated_at=s['updated_at'],
                      coordinate_version=scene['coordinate_version'],units='sfm_relative',source_files=provenance['source_files'],
                      image_manifest='source_images.json',scene_indices_binding={**geometry,'element':'vertex','index_base':0,'order':'original PLY vertex order','selection':'center inside scene box'},
                      object_count=len(catalog),object_bbox_schema='obb-xyzw-v1',optional_reference_is_required=False,contains_final_object_indices=False,
                      contains_semantic_features=False,contains_scene_graph=False,contains_evaluation_data=False,last_frozen_version=s['last_frozen_version'])
        atomic_json(dest/'manifest.json',manifest);copy_atomic(self.root/'.assets/images.json',dest/'source_images.json')
        confirmed=sum(o['status']=='confirmed' for o in catalog)
        report=f'# M0 v2 数据状态\n\n修订 r{s["revision"]}；坐标 {scene["coordinate_version"]}。\n\n场景状态：{scene["status"]}。对象：{len(catalog)}，确认：{confirmed}。\n\n所有尺寸为 SfM 相对单位。设备框仅为 M2 粗略搜索范围；无最终对象高斯索引、语义融合或场景图。单张训练参考掩膜可选。\n\n未自动迁移旧 M0 标注。候选和草稿不代表人工确认。\n'
        (dest/'M0_REPORT.md').write_text(report,encoding='utf-8')
    def draft(self,key,value=None):
        with self.lock:
            if value is not None:self.db.execute('INSERT OR REPLACE INTO drafts VALUES(?,?,?)',(key,json.dumps(value,allow_nan=False),now()));self.db.commit()
            row=self.db.execute('SELECT content,updated_at FROM drafts WHERE key=?',(key,)).fetchone()
            return dict(content=json.loads(row[0]),updated_at=row[1]) if row else None
    def history(self):
        with self.lock:return [json.loads(r[0]) for r in self.db.execute('SELECT event FROM revisions ORDER BY revision DESC LIMIT 300')]
