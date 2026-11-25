"""Real-geometry V2 contracts in an isolated directory. QA flags are NOT human truth."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import time
import unittest
import urllib.request
import zipfile
import numpy as np

PROJECT=Path(__file__).resolve().parents[2]
LIVE=PROJECT/'industrial_scene_prior_v2'
SOURCE=json.load(urllib.request.urlopen('http://127.0.0.1:28760/api/state'))
REAL=next(o for o in SOURCE['objects'].values() if not o.get('deleted') and o['name_zh'])
QA=PROJECT/'logs'/('m0_v2_contract_'+time.strftime('%Y%m%dT%H%M%S'))
QA.mkdir(parents=True);shutil.copytree(LIVE/'.assets',QA/'.assets')
os.environ['M0_DATA']=str(QA)
from fastapi.testclient import TestClient
from m0 import app as server
from m0.spatial import transform,inside,corners
from m0.storage import Store
client=TestClient(server.app);client.headers['X-M0-Client']='1'
checks=[]

def state():return client.get('/api/state').json()
def post(path,data,expected=200):
    body={**data,'revision':state()['revision'],'reviewer':'AUTOMATED CONTRACT QA — not human truth'}
    response=client.post('/api'+path,json=body)
    assert response.status_code==expected,(path,response.status_code,response.text[:1500])
    checks.append({'endpoint':path,'status':response.status_code});return response.json()

class V2Contract(unittest.TestCase):
 def test_real_geometry_workflow(self):
    s=state();self.assertEqual(s['schema_version'],'m0-2.0');self.assertFalse(s['objects'])
    self.assertEqual(len(client.get('/api/images').json()),306)
    self.assertEqual(client.get('/api/images/frame_000057').status_code,422)
    self.assertEqual(client.post('/api/steps/1/confirm',json={}).status_code,404)
    self.assertEqual(client.post('/api/evaluation/queries',json={}).status_code,404)
    scene=copy.deepcopy(SOURCE['scene']);scene.update(status='confirmed',floor_confirmed=True,directions_confirmed=True,review_ack=True)
    bad=copy.deepcopy(scene);bad['transform'][0][:3]=[-x for x in bad['transform'][0][:3]]
    post('/scene',bad,422)
    s=post('/scene',scene)
    t=np.asarray(s['scene']['transform']);np.testing.assert_allclose(t[:3,:3]@t[:3,:3].T,np.eye(3),atol=1e-6);self.assertAlmostEqual(np.linalg.det(t[:3,:3]),1,places=5)
    indices=np.load(QA/'scene/scene_gaussian_indices.npy')
    expected=server.original_ids[inside(transform(server.xyz,t),s['scene']['bbox'])]
    np.testing.assert_array_equal(indices,expected)
    np.testing.assert_allclose(transform(transform(server.xyz[::5000],t),np.linalg.inv(t)),server.xyz[::5000],atol=1e-5)
    body={k:copy.deepcopy(REAL[k]) for k in ('bbox','name_zh','name_en','description_zh','description_en','granularity')}
    body.update(coordinate_version=s['scene']['coordinate_version'],status='confirmed',review_ack=True,source='real_workshop_candidate_in_isolated_contract')
    result=post('/objects',body);oid=result['object_id'];o=result['state']['objects'][oid]
    self.assertNotIn('anchor_image_id',o);self.assertIsNone(o['reference'])
    hidden=post('/objects/'+oid+'/visibility',{'visible':False});self.assertEqual(hidden['objects'][oid]['status'],'confirmed')
    post('/objects/'+oid+'/visibility',{'visible':True})
    self.assertTrue(client.get('/api/quality').json()['can_freeze'])
    post('/freeze',{'review_ack':False},422)
    version=post('/freeze',{'review_ack':True})['version']
    response=client.get('/api/exports/'+version);self.assertEqual(response.status_code,200)
    archive=zipfile.ZipFile(io.BytesIO(response.content));names=archive.namelist()
    self.assertIn('scene/scene_gaussian_indices.npy',names)
    self.assertIn('objects/'+oid+'/coarse_bbox.json',names)
    self.assertIn('objects/'+oid+'/bbox_preview.jpg',names)
    self.assertFalse(any('optional_reference/' in n or 'ground_truth/' in n or 'scene_graph' in n for n in names))
    self.assertFalse(any(n.startswith('objects/') and n.endswith('.npy') for n in names))
    manifest=json.loads(archive.read('manifest.json'));self.assertFalse(manifest['optional_reference_is_required']);self.assertEqual(manifest['scene_indices_binding']['index_base'],0)
    box=json.loads(archive.read('objects/'+oid+'/coarse_bbox.json'));self.assertEqual(box['center'],REAL['bbox']['center'])
    exported=np.load(io.BytesIO(archive.read('scene/coordinate_transform.npy')));np.testing.assert_array_equal(exported,t)
    # Repeated names are supported as distinct IDs; the duplicate is ONLY a contract fixture.
    twin=post('/objects',body)['object_id'];self.assertNotEqual(oid,twin)
    self.assertEqual(len([o for o in state()['objects'].values() if not o.get('deleted')]),2)
    post('/objects/'+twin+'/delete',{});self.assertTrue(state()['objects'][twin]['deleted'])
    self.assertTrue((QA/'versions'/version/'objects'/oid/'coarse_bbox.json').exists())
    stale={**body,'object_id':oid,'revision':0,'reviewer':'QA'}
    self.assertEqual(client.post('/api/objects',json=stale).status_code,409)
    invalid={**body,'bbox':{'center':[1e6,0,0],'size':[1,1,1]}}
    post('/objects',invalid,422)
    post('/sam',{'object_id':oid,'image_id':'frame_000057','prompts':{'bbox':[1,1,20,20]}},422)
    post('/objects',dict(body,description_en='The rack is left of another machine.'),422)
    rec=post('/objects/'+oid+'/recommend',{})['recommendations']
    self.assertTrue(rec);self.assertTrue(all(server.images[r['image_id']]['split']=='train' for r in rec))
    for r in rec:
        x,y,x1,y1=r['bbox'];im=server.images[r['image_id']];self.assertTrue(0<=x<x1<=im['width'] and 0<=y<y1<=im['height'])
    draft={'bbox':REAL['bbox'],'description_en':REAL['description_en'],'base_revision':state()['revision']}
    self.assertEqual(client.put('/api/draft/qa_restore',json=draft).status_code,200)
    restarted=Store(QA);self.assertEqual(restarted.read(),state());self.assertEqual(restarted.draft('qa_restore')['content'],draft);restarted.db.close()
    before=state();old=before['objects'][oid];old_raw=transform(corners(old['bbox']),np.linalg.inv(before['scene']['transform']))
    moved=copy.deepcopy(before['scene']);moved['bbox']['center'][0]+=.02;moved.update(status='draft')
    after=post('/scene',moved);self.assertEqual(after['objects'][oid]['status'],'draft')
    self.assertNotEqual(before['scene']['coordinate_version'],after['scene']['coordinate_version'])
    np.testing.assert_allclose(transform(corners(after['objects'][oid]['bbox']),np.linalg.inv(after['scene']['transform'])),old_raw,atol=1e-6)
    self.assertFalse(client.get('/api/quality').json()['can_freeze'])
    path=QA/'versions'/version/'objects'/oid/'description.json';saved=path.read_bytes();path.write_bytes(saved+b' ')
    self.assertEqual(client.get('/api/exports/'+version).status_code,422);path.write_bytes(saved)
    self.assertEqual(client.get('/api/exports/'+version).status_code,200)
    self.assertEqual(client.get('/api/files/.m0.sqlite3').status_code,422)
    no_header=TestClient(server.app);self.assertEqual(no_header.post('/api/objects',json=body).status_code,403)
    # Original source hashes were read and checked by freeze, never copied into object outputs.
    result=dict(status='passed',assertion_groups=22,requests=checks,qa_directory=str(QA),real_candidate_source=REAL['object_id'],frozen_version=version,
                note='All confirmations in this directory are automated contract fixtures, not human annotations. Production remains drafts.')
    (PROJECT/'logs/m0_v2_contract_latest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))

if __name__=='__main__':unittest.main()
