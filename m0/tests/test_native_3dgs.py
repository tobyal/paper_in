"""Read-only source/index/camera equivalence and migration checks on real M0 data."""
import copy
import io
import json
import math
import sqlite3
import subprocess
import hashlib
import urllib.request
import urllib.error
import numpy as np
from PIL import Image
from m0.settings import ROOT, ASSETS, PROJECT, GAUSSIANS, NATIVE_GS
from m0.prepare import sha
from m0.spatial import transform, inside
from m0.storage import Store

url='http://127.0.0.1:28760/api'
def get(path):return json.load(urllib.request.urlopen(url+path))
def post(path,body,method='POST'):
    return urllib.request.urlopen(urllib.request.Request(url+path,data=json.dumps(body).encode(),method=method,
        headers={'Content-Type':'application/json','X-M0-Client':'1'}),timeout=65)

before=get('/state');migration=json.loads((ROOT/'MIGRATION.json').read_text())
backup=PROJECT/before['migration']['backup']
old=json.loads((backup/'state.json').read_text())
assert before['revision']==old['revision']+1 and before['dataset_id']!=old['dataset_id']
for key in ('bbox','transform','coordinate_version','status','floor_confirmed','directions_confirmed'):
    assert before['scene'][key]==old['scene'][key]
for oid,o in old['objects'].items():
    assert {k:v for k,v in o.items() if k!='preview_path'}=={k:v for k,v in before['objects'][oid].items() if k!='preview_path'}
old_db=sqlite3.connect('file:'+str(backup/'state.sqlite3')+'?mode=ro',uri=True)
for key,content in old_db.execute('SELECT key,content FROM drafts'):
    original=json.loads(content);current=get('/draft/'+key)['content']
    if key=='workspace' and original.get('base_revision')==old['revision']:
        original['base_revision']=before['revision']
        original['sceneDraft'].update(artifacts=before['scene']['artifacts'],gaussian_count=before['scene']['gaussian_count'])
        obj=original.get('objectDraft')
        if obj and obj['object_id'] in before['objects']:obj['preview_path']=before['objects'][obj['object_id']].get('preview_path')
    assert original==current,key
old_db.close()
manifest=json.loads((ROOT/'manifest.json').read_text());provenance=get('/provenance')
geometry=manifest['scene_indices_binding']
assert geometry['representation']=='native_3dgs' and geometry['scale_dimensions']==3
assert geometry['sha256']==sha(GAUSSIANS) and geometry['gaussians']==1828777
assert all('relags_baseline/' not in x['path'] for x in manifest['source_files'])
xyz=np.fromfile(ASSETS/'positions.bin',dtype='<f4').reshape(-1,3);ids=np.load(ASSETS/'display_indices.npy')
np.testing.assert_array_equal(np.load(ROOT/'scene/scene_gaussian_indices.npy'),ids[inside(transform(xyz,before['scene']['transform']),before['scene']['bbox'])])
for f in json.loads((NATIVE_GS/'UPSTREAM.json').read_text())['unmodified_files']:
    assert sha(NATIVE_GS/f['path'])==f['sha256'],f['path']
assert hashlib.sha256(subprocess.check_output(['git','diff','--binary'],cwd=PROJECT/'ReLaGS')).hexdigest()=='2418e82357232c76300b5de6563bca0bc1756ce9325def19b44c5eae615880a8'
# A retired browser tab must not overwrite a migrated workspace on pagehide.
draft=get('/draft/workspace');stale=copy.deepcopy(draft['content']);stale['base_revision']=old['revision']
try:post('/draft/workspace',stale,'PUT');raise AssertionError('stale workspace accepted')
except urllib.error.HTTPError as e:assert e.code==409
assert get('/draft/workspace')==draft
# Independently construct the same free-roam camera from original COLMAP extrinsics.
im=next(v for v in get('/images') if v['image_id']=='frame_000340');r=np.asarray(im['world_to_camera_R']);t=np.asarray(im['world_to_camera_t'])
pose=np.eye(4);pose[:3,:3]=r.T@np.diag([1,-1,-1]);pose[:3,3]=-r.T@t
request=dict(camera_world=(np.asarray(before['scene']['transform'])@pose).tolist(),width=938,height=528,
             fov=math.degrees(2*math.atan(im['height']/(2*im['K'][1][1]))),coordinate_version=before['scene']['coordinate_version'],show_outside=True)
response=post('/roam/render',request);pixels=np.asarray(Image.open(io.BytesIO(response.read())),dtype=float)
assert response.headers['X-M0-Renderer']=='official-3dgs' and int(response.headers['X-M0-Gaussians'])==1828777
import torch
from m0.native_3dgs import load_model,camera,render_rgb
# Original COLMAP fx != fy. Free-roam has a square-pixel Three camera; compare at its
# actual FOV, not an anisotropic fixed reference. Production reference rendering keeps K.
fy=math.radians(request['fov']);fx=2*math.atan(math.tan(fy/2)*request['width']/request['height'])
with torch.inference_mode():
    model=load_model();reference=render_rgb(camera(938,528,r,t,fx,fy),model)['render']
    rgb=(reference.clamp(0,1).permute(1,2,0).cpu().numpy()*255+.5).astype('uint8')
buffer=io.BytesIO();Image.fromarray(rgb).save(buffer,format='JPEG',quality=90)
fixed=np.asarray(Image.open(io.BytesIO(buffer.getvalue())),dtype=float)
error=float(np.abs(pixels-fixed).mean());assert error<.05,error
assert get('/state')==before
# New Web code must reject the retired dataset before opening its SQLite database.
retired=PROJECT/before['migration']['source_root'];retired_hash=sha(retired/'.m0.sqlite3')
try:Store(retired);raise AssertionError('retired 2DGS directory accepted')
except RuntimeError as e:assert 'native 3DGS data directory' in str(e)
assert sha(retired/'.m0.sqlite3')==retired_hash
result=dict(status='passed',source_hash=geometry['sha256'],native_gaussians=len(xyz),selected_gaussians=before['scene']['gaussian_count'],
            human_fields_and_drafts_preserved=True,indices_exact=True,stale_workspace_rejected=True,upstream_code_hashes_unchanged=True,
            relags_diff_unchanged=True,camera_rgb_mean_absolute_error=error,renderer=response.headers['X-M0-Renderer'],read_only=True)
(PROJECT/'logs/m0_native3dgs_contract.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
