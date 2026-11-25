"""Isolated software contracts: fixtures are never production device annotations."""
import copy
import json
import os
from pathlib import Path
import shutil
import time
import urllib.request
import numpy as np
from scipy.spatial.transform import Rotation

PROJECT=Path(__file__).resolve().parents[2]
SOURCE=json.load(urllib.request.urlopen('http://127.0.0.1:28760/api/state'))
QA=PROJECT/'logs'/('m0_obb_contract_'+time.strftime('%Y%m%dT%H%M%S'))
QA.mkdir(parents=True);shutil.copytree(PROJECT/'industrial_scene_prior_v2/.assets',QA/'.assets')
os.environ['M0_DATA']=str(QA)
from fastapi.testclient import TestClient
from m0 import app as server
from m0.spatial import corners,inside,transform,rebase_box
from m0.validation import box_check
from m0.storage import Store
client=TestClient(server.app);client.headers['X-M0-Client']='1'
checks=[]
def state():return client.get('/api/state').json()
def post(path,body,code=200):
    result=client.post('/api'+path,json={**body,'revision':state()['revision'],'reviewer':'SOFTWARE QA ONLY'})
    assert result.status_code==code,(path,result.status_code,result.text[:1000]);checks.append(dict(path=path,status=code));return result.json()

scene=copy.deepcopy(SOURCE['scene']);scene.update(status='confirmed',review_ack=True,floor_confirmed=True,directions_confirmed=True)
post('/scene',scene);scene=copy.deepcopy(state()['scene']);original=state()
q=Rotation.from_euler('z',37,degrees=True).as_quat().tolist()
box={'center':scene['bbox']['center'],'size':[.25,.6,.3],'quaternion':q}
assert inside(corners(box),box).all()
assert not inside([np.asarray(box['center'])+[.4,0,0]],box)[0]
legacy={'center':[0,0,0],'size':[1,2,3]};assert box_check(legacy)['quaternion']==[0,0,0,1]
np.testing.assert_allclose(corners(legacy),corners(box_check(legacy)))
base=dict(bbox=box,name_zh='软件契约测试框',name_en='Software fixture',description_zh='仅用于软件验证，不是设备标注。',description_en='Software validation only.',granularity='equipment',status='draft',coordinate_version=scene['coordinate_version'],visible=True)
items=[dict(base,object_id='draft_aaaaaaaa'),dict(base,object_id='draft_bbbbbbbb',bbox={**box,'center':(np.asarray(box['center'])+[.7,0,0]).tolist()})]
result=post('/objects/batch',{'objects':items});assert result['state']['revision']==original['revision']+1
ids=list(result['id_mapping'].values());assert len(set(ids))==2
assert state()['scene']==scene
for oid in ids:
    out=json.loads((QA/'objects'/oid/'coarse_bbox.json').read_text());np.testing.assert_allclose(out['quaternion'],q);assert out['box_type']=='OBB'
before=state();bad=copy.deepcopy(list(before['objects'].values()));bad[-1]['bbox']['quaternion']=[0,0,0,0]
post('/objects/batch',{'objects':bad},422);assert state()==before
stale=client.post('/api/objects/batch',json={'objects':[before['objects'][ids[0]]],'revision':0});assert stale.status_code==409
confirmed=[dict(before['objects'][oid],status='confirmed',review_ack=True) for oid in ids]
post('/objects/batch',{'objects':confirmed})
hidden=dict(state()['objects'][ids[0]],visible=False);post('/objects/batch',{'objects':[hidden]});assert state()['objects'][ids[0]]['status']=='confirmed'
assert client.get('/api/quality').json()['can_freeze']
reopened=Store(QA);assert reopened.read()==state();reopened.db.close()
post('/draft/no_such_route',{},405)
draft={'base_revision':state()['revision'],'pendingObjects':{'draft_cccccccc':dict(base,object_id='draft_cccccccc')}}
assert client.put('/api/draft/workspace',json=draft).status_code==200
assert client.get('/api/draft/workspace').json()['content']==draft
# Export materialization and true scene-frame rotations retain OBBs exactly.
server.store.write_dataset(QA/'export_contract',state())
export=json.loads((QA/'export_contract/objects'/ids[0]/'coarse_bbox.json').read_text());np.testing.assert_allclose(export['quaternion'],q)
rot=np.eye(4);rot[:3,:3]=Rotation.from_euler('z',23,degrees=True).as_matrix();old_frame=np.asarray(scene['transform']);new_frame=rot@old_frame
rebased=rebase_box(box,old_frame,new_frame)
np.testing.assert_allclose(transform(corners(box),np.linalg.inv(old_frame)),transform(corners(rebased),np.linalg.inv(new_frame)),atol=1e-7)
changed=copy.deepcopy(scene);changed.update(transform=new_frame.tolist(),status='draft')
post('/scene',changed)
np.testing.assert_allclose(transform(corners(state()['objects'][ids[0]]['bbox']),np.linalg.inv(new_frame)),transform(corners(box),np.linalg.inv(old_frame)),atol=1e-7)
assert state()['objects'][ids[0]]['status']=='draft'
# Reset only this isolated workspace for visual tests; no synthetic boxes in the live dataset.
post('/scene',{**scene,'status':'confirmed','review_ack':True})
for oid in ids:post('/objects/'+oid+'/delete',{})
assert json.load(urllib.request.urlopen('http://127.0.0.1:28760/api/state'))==SOURCE
record=dict(status='passed',qa_directory=str(QA),checks=checks,scene_preserved=True,production_unchanged=True,
            verified=['OBB corners/containment','legacy identity rotation','two objects in one revision','invalid batch rollback','stale revision rejection','visibility preserves confirmation','reload','export orientation','draft restore','exact rotated-frame rebasing'])
(QA/'result.json').write_text(json.dumps(record,indent=2));(PROJECT/'logs/m0_obb_qa_path.txt').write_text(str(QA));print(json.dumps(record))
