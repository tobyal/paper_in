"""Isolated API acceptance using real M0 SAM masks and freshly rendered geometry.

Test reviewer flags exercise software transitions only; this directory is never a
human-confirmed prior dataset and never feeds downstream research modules.
"""
import base64
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import time
import unittest
import zipfile

PROJECT=Path(__file__).resolve().parents[2]
REAL=PROJECT/'industrial_scene_prior'
SANDBOX=PROJECT/'logs'/('m0_contract_qa_'+time.strftime('%Y%m%dT%H%M%S'))
SANDBOX.mkdir(parents=True)
(SANDBOX/'.assets').mkdir()
for name in ['images.json','scene_points.json','source_manifest.json']:shutil.copy2(REAL/'.assets'/name,SANDBOX/'.assets'/name)
shutil.copytree(REAL/'.assets/renders',SANDBOX/'.assets/renders')
os.environ['M0_DATA']=str(SANDBOX)
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
from m0 import app as api
from m0.storage import Store
from m0.validation import relation_signature

client=TestClient(api.app,headers={'X-M0-Client':'1'})
checks=[]


def get(path):
    r=client.get('/api'+path);assert r.status_code==200,r.text;return r.json()


def write(path,body,expected=200):
    payload={**body,'revision':get('/state')['revision'],'reviewer':'AUTOMATED CONTRACT QA — not human truth','review_ack':True}
    r=client.post('/api'+path,json=payload)
    assert r.status_code==expected,(path,r.status_code,r.text[:1000]);checks.append(dict(endpoint=path,status=r.status_code))
    return r.json()


class RealContract(unittest.TestCase):
    def test_complete_contract(self):
        real=Store(REAL).read();anchor=next(o for o in real['objects'].values() if o['category_en']=='white mesh cart')
        source_id=anchor['object_id'];im=api.images['frame_000050']
        # Actual freshly rendered floor depth at visible floor pixels, no historical ground estimate.
        depth=np.load(REAL/'.assets/renders/frame_000050_geometry.npz')['depth'][0]
        h,w=depth.shape;K=np.asarray(im['K']);R=np.asarray(im['world_to_camera_R']);t=np.asarray(im['world_to_camera_t'])
        floor=[]
        for px,py in [(1360,720),(1455,730),(1400,855),(1500,850)]:
            picked=write('/scene/pick',dict(image_id=im['image_id'],x=px,y=py))
            projected=K@(R@np.array(picked['point'])+t);projected=projected[:2]/projected[2]
            self.assertLess(np.linalg.norm(projected-np.array([px,py])),2.0)
            z=float(depth[int(py*h/im['height']),int(px*w/im['width'])]);self.assertGreater(z,0)
            ray=np.linalg.inv(K)@np.array([px,py,1]);floor.append((R.T@(ray*z-t)).tolist())
        fitting=write('/scene/fit',dict(floor_points=floor,origin=floor[0],heading_points=floor[:2],up_hint=(np.asarray(im['center'])-np.mean(floor,axis=0)).tolist()))
        T=np.asarray(fitting['transform']);self.assertTrue(np.allclose(T[:3,:3]@T[:3,:3].T,np.eye(3),atol=1e-6));self.assertAlmostEqual(np.linalg.det(T[:3,:3]),1)
        write('/scene/fit',dict(floor_points=[floor[0]]*3,origin=floor[0],heading_points=floor[:2],up_hint=[0,1,0]),422)
        write('/scene/reference',dict(coordinate_system=fitting,scene_reference_views=['frame_000050'],geometry_verified=True,review_status='confirmed'))
        for name,offset in [('QA observed floor area',0),('QA separate floor area',100)]:
            write('/regions',dict(name=name,boundary=[[offset-20,-20],[offset+20,-20],[offset+20,20],[offset-20,20]],include=True,review_status='confirmed',reference_image_ids=['frame_000050']))
        regions=get('/state')['regions'];region_id=regions[0]['region_id']
        result=write('/objects',{**{k:v for k,v in anchor.items() if k!='object_id'},'candidate_region_id':region_id,'status':'confirmed','source':'isolated API acceptance fixture'})
        oid=result['object_id'];self.assertNotEqual(oid,source_id)
        # All success-path masks are actual newly generated SAM outputs (plus the actual UI edit).
        for a in real['annotations'].values():
            if a['object_id']!=source_id:continue
            shutil.copytree(REAL/'.inference'/a['sam_job_id'],SANDBOX/'.inference'/a['sam_job_id'],dirs_exist_ok=True)
            edits=json.loads((REAL/a['edit_history_path']).read_text())['operations']
            body=dict(object_id=oid,image_id=a['image_id'],scope=a['scope'],sam_job_id=a['sam_job_id'],candidate=a['candidate'],
                      mask_png='data:image/png;base64,'+base64.b64encode((REAL/a['mask_path']).read_bytes()).decode(),edit_history=edits,visibility=a['visibility'],review_status='confirmed',notes='Isolated QA transition; not human truth')
            saved=write('/annotations',body)['annotation'];self.assertEqual(saved['mask_sha256'],a['mask_sha256'])
            if a['scope']=='ground_truth':write('/annotations',{**body,'scope':'priors'},422)
        # Wrong image, empty mask and wrong dimensions are rejected, never accepted as annotations.
        first=next(a for a in real['annotations'].values() if a['scope']=='priors')
        body=dict(object_id=oid,image_id=first['image_id'],scope='priors',sam_job_id=first['sam_job_id'],candidate=first['candidate'],visibility='clear',review_status='draft')
        for size in [(1,1),(1875,1056)]:
            buf=io.BytesIO();Image.new('L',size,0).save(buf,format='PNG')
            write('/annotations',{**body,'mask_png':'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()},422)
        for status in ['not_present','fully_occluded','unannotated']:
            result=write('/annotations',dict(object_id=oid,image_id='frame_000058',scope='priors',visibility=status,review_status='draft'))
            self.assertIsNone(result['annotation']['mask_path'])
        # Keep the uncertainty status test as an independently retained revision, then mark this extra view absent.
        write('/annotations',dict(object_id=oid,image_id='frame_000058',scope='priors',visibility='not_present',review_status='confirmed'))
        desc=real['descriptions'][source_id]
        write('/descriptions/'+oid,{**desc,'review_status':'confirmed'})
        write('/descriptions/'+oid,{**desc,'visual_description_en':'The cart is left of the rack.','review_status':'draft'},422)
        roi_state=write('/coarse-roi/'+oid,{})
        self.assertGreaterEqual(roi_state['coarse_rois'][oid]['candidate_count'],5)
        self.assertEqual(len(roi_state['coarse_rois'][oid]['source_masks']),2)
        write('/coarse-roi/'+oid+'/clear',{})
        self.assertNotIn(oid,get('/state')['coarse_rois'])
        schema=get('/state')['relation_schema']
        for r in schema:
            r['rule']={'near':'Euclidean candidate-center distance below declared relative threshold','left_of':'subject industrial X < object industrial X','right_of':'subject industrial X > object industrial X','inside_region':'candidate center XY inside the region polygon'}[r['name']]
            if r['name']=='near':r.update(distance_definition='Euclidean candidate centers',threshold=2.0)
        write('/relations/schema',{'relations':schema})
        for region,label in zip(regions,['true','false']):
            body=dict(collection='reference_relations',subject_id=oid,relation_type='inside_region',region_id=region['region_id'],expected_label=label,evidence='Isolated contract fixture tied to the real view and freshly selected geometry; not human ground truth',review_status='confirmed')
            write('/relations/records',body)
            write('/relations/records',{**body,'collection':'known_relations','knowledge_reason':'test leakage guard'},422)
        self.assertEqual(relation_signature(dict(subject_id='a',object_id='b',relation_type='left_of'),schema),relation_signature(dict(subject_id='b',object_id='a',relation_type='right_of'),schema))
        for collection,types in [('semantic_queries',['attribute']),('relational_queries',['category','attribute','region','relation','disambiguation','multi_condition','no_match'])]:
            for typ in types:
                text={'category':'Find the mesh-sided wheeled container.','attribute':'Which object has a yellow bar near its casters?','region':'Find the annotated cart in the selected study region.','relation':'Find the cart inside the selected region.','disambiguation':'Select the mesh cart with a yellow lower crossbar.','multi_condition':'Find the white mesh cart with casters in the study region.','no_match':'Find a purple sphere.'}[typ]
                write('/evaluation/queries',dict(collection=collection,query_type=typ,query_text=text,expected_object_ids=[] if typ=='no_match' else [oid],allow_multiple=False,evidence='Real observed cart; isolated schema/export QA only',review_status='confirmed'))
        quality=get('/quality');self.assertFalse([i for i in quality['issues'] if i['severity']=='error'],quality)
        write('/freeze',{},422)
        for step in range(1,7):write(f'/steps/{step}/confirm',{})
        self.assertTrue(get('/quality')['can_freeze'])
        frozen=write('/freeze',{});folder=SANDBOX/'versions'/frozen['version'];freeze_hash=hashlib.sha256((folder/'FREEZE.json').read_bytes()).hexdigest()
        for scope,other in [('priors','ground_truth'),('ground_truth','priors')]:
            response=client.get(f'/api/exports/{frozen["version"]}/{scope}');self.assertEqual(response.status_code,200)
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                self.assertTrue(any(n.startswith(scope+'/') for n in z.namelist()));self.assertFalse(any(n.startswith(other+'/') for n in z.namelist()))
        # Optimistic locking prevents overwrite, and upstream edits invalidate downstream approvals.
        stale={'revision':0,'reviewer':'QA','review_ack':True,**desc}
        r=client.post('/api/descriptions/'+oid,json=stale);self.assertEqual(r.status_code,409)
        write('/descriptions/'+oid,{**desc,'review_status':'draft'})
        after=get('/state');self.assertNotIn('4',after['approvals']);self.assertNotIn('5',after['approvals']);self.assertFalse(get('/quality')['can_freeze'])
        self.assertEqual(hashlib.sha256((folder/'FREEZE.json').read_bytes()).hexdigest(),freeze_hash)
        self.assertEqual(Store(SANDBOX).read()['revision'],after['revision'])
        self.assertGreater(len(get('/history')),20)
        denied=client.get('/api/files/priors/../../.m0.sqlite3');self.assertNotEqual(denied.status_code,200)
        outside=client.post('/api/objects',json={},headers={'Origin':'https://external.example'});self.assertEqual(outside.status_code,403)
        # Frozen manifests detect out-of-band tampering; only the isolated QA copy is changed.
        target=folder/'priors/objects/object_catalog.json';original=target.read_bytes();target.write_bytes(original+b' ')
        r=client.get(f'/api/exports/{frozen["version"]}/priors');self.assertEqual(r.status_code,422);target.write_bytes(original)
        report=dict(status='passed',assertion_groups=20,request_checks=checks,sandbox=str(SANDBOX),real_object_source=source_id,frozen_test_version=frozen['version'],
                    note='This isolated freeze tests software only. It is not a completed M0 dataset or human-confirmed ground truth.')
        (SANDBOX/'TEST_RESULTS.json').write_text(json.dumps(report,indent=2));(PROJECT/'logs/m0_contract_latest.json').write_text(json.dumps(report,indent=2))


if __name__=='__main__':unittest.main(verbosity=2)
