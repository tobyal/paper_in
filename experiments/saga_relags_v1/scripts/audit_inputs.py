import os,sys,json,sqlite3,shutil,hashlib,subprocess,importlib.util,datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parents[1]
sys.path.insert(0,str(PROJECT))
import numpy as np
from industrial_world_model.common import CATEGORIES

def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(8<<20),b''):h.update(block)
    return h.hexdigest()

from m0.settings import ROOT as M0ROOT,GAUSSIANS,IMAGES,COLMAP,SPLIT
db=sqlite3.connect('file:'+str(M0ROOT/'.m0.sqlite3')+'?mode=ro',uri=True);db.execute('BEGIN')
state=json.loads(db.execute('SELECT state FROM revisions ORDER BY revision DESC LIMIT 1').fetchone()[0])
row=db.execute("SELECT content FROM drafts WHERE key='workspace'").fetchone();draft=json.loads(row[0]) if row else None;db.close()
dirty=bool(draft and (draft.get('pendingObjects') or draft.get('sceneDirty') or draft.get('objectDirty')))
assert not dirty,'Uncommitted M0 workspace changes need explicit inspection'
snapshot=ROOT/'inputs/m0_state.json'
if snapshot.exists():assert read(snapshot)==state,'Latest M0 differs from frozen experiment snapshot'
write(snapshot,state);write(ROOT/'inputs/m0_workspace.json',draft)
images=read(M0ROOT/'.assets/images.json');write(ROOT/'inputs/cameras.json',images)
write(ROOT/'inputs/camera_split.json',read(SPLIT));write(ROOT/'inputs/m0_source_manifest.json',read(M0ROOT/'.assets/source_manifest.json'))
objects=[];categories=[]
for i,(zh,en) in enumerate(CATEGORIES,1):categories.append(dict(category_id=f'category_{i:02d}',name_zh=zh,name_en=en))
for obj in state['objects'].values():
    if obj.get('deleted'):continue
    item=dict(obj);name=item['name_zh'].rstrip(' 0123456789');category=next(c for c in categories if c['name_zh']==name)
    if item.get('category_id'):assert item['category_id']==category['category_id'],'Inspect native category IDs'
    item.update(category_id=category['category_id'],category_name_zh=category['name_zh'],category_name_en=category['name_en']);objects.append(item)
write(ROOT/'inputs/objects.json',objects);write(ROOT/'inputs/categories.json',categories)
models=PROJECT/'models';paths=[GAUSSIANS,M0ROOT/'.m0.sqlite3',models/'sam/sam_vit_h_4b8939.pth',models/'openclip_vit_b16/open_clip_pytorch_model.bin',SPLIT]
paths+=list(COLMAP.glob('*.bin'))
for folder in ['m0','industrial_world_model']:
    paths += [p for p in (PROJECT/folder).rglob('*') if p.is_file() and p.suffix in ['.py','.js','.html','.css'] and 'vendor' not in p.parts and '__pycache__' not in p.parts]
protected={str(p.relative_to(PROJECT)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths}
write(ROOT/'inputs/protected_sources_before.json',protected)
older={}
for folder in (PROJECT/'outputs').iterdir():
    if folder.is_dir():
        for p in folder.rglob('*'):
            if p.is_file():older[str(p.relative_to(PROJECT))]=[p.stat().st_size,p.stat().st_mtime_ns]
write(ROOT/'inputs/protected_outputs_before.json',older)
import torch
env=dict(python=sys.version,executable=sys.executable,torch=torch.__version__,cuda=torch.version.cuda,packages={name:bool(importlib.util.find_spec(name)) for name in ['pytorch3d','segment_anything','open_clip','diff_gaussian_rasterization','diff_gaussian_rasterization_contrastive_f','diff_gaussian_rasterization_depth','sklearn','hdbscan']})
write(ROOT/'inputs/environment_before.json',env)
hybrid=PROJECT/'outputs/industrial_world_model/M2_1_hybrid_view_selection_20261126_r29'
hybrid_compatible=False
if (hybrid/'manifest.json').exists():
    manifest=read(hybrid/'manifest.json');baseline=PROJECT/manifest['baseline']
    hybrid_compatible=read(baseline/'config/m0_state.json')==state and manifest['source_ply_sha256']==sha(GAUSSIANS)
manifest=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),m0_revision=state['revision'],objects=len(objects),categories=categories,category_id_source='Stable experiment catalog from existing M0 category names; source M0 has no explicit category_id',scene_status=state['scene']['status'],formal_confirmed=sum(o['status']=='confirmed' for o in objects),units='sfm_relative',ply=str(GAUSSIANS.relative_to(PROJECT)),images=str(IMAGES.relative_to(PROJECT)),colmap=str(COLMAP.relative_to(PROJECT)),train=sum(im['split']=='train' for im in images),heldout=sum(im['split']=='heldout' for im in images),hybrid_observations=str(hybrid.relative_to(PROJECT)) if hybrid_compatible else None,hybrid_compatible_with_latest_m0=hybrid_compatible,external_image_upload_authorized=False,available_local_vlm_checkpoints=[]) 
write(ROOT/'inputs/manifest.json',manifest)
print(json.dumps(dict(manifest=manifest,environment=env,objects=[(o['object_id'],o['name_zh'],o['bbox']) for o in objects]),ensure_ascii=False,indent=2))
