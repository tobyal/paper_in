"""Optional-reference export on a transactional copy of actual V2 browser data."""
import base64,io,json,os,shutil,sqlite3,time,zipfile
from pathlib import Path
import numpy as np
from PIL import Image
P=Path(__file__).resolve().parents[2];live=P/'industrial_scene_prior_3dgs';qa=P/'logs'/('m0_v2_reference_qa_'+time.strftime('%Y%m%dT%H%M%S'));qa.mkdir()
for name in ('.assets','.artifacts','.inference'):shutil.copytree(live/name,qa/name)
src=sqlite3.connect('file:'+str(live/'.m0.sqlite3')+'?mode=ro',uri=True);dest=sqlite3.connect(qa/'.m0.sqlite3');src.backup(dest);src.close();dest.close()
os.environ['M0_DATA']=str(qa)
from fastapi.testclient import TestClient
from m0 import app as server
c=TestClient(server.app);c.headers['X-M0-Client']='1'
def state():return c.get('/api/state').json()
def post(path,body,code=200):
 r=c.post('/api'+path,json={**body,'revision':state()['revision'],'reviewer':'AUTOMATED REFERENCE QA — not human truth'})
 assert r.status_code==code,(path,r.text);return r.json()
s=state();oid=next(oid for oid,o in s['objects'].items() if not o.get('deleted') and o.get('reference'));o=s['objects'][oid];ref=o['reference']
post('/scene',{**s['scene'],'status':'confirmed','floor_confirmed':True,'directions_confirmed':True,'review_ack':True})
post('/objects',{**o,'status':'confirmed','review_ack':True})
edits=json.loads((qa/ref['edit_history_path']).read_text())
b=dict(image_id=ref['image_id'],sam_job_id=ref['sam_job_id'],candidate=ref['candidate'],status='confirmed',review_ack=True,mask_png='data:image/png;base64,'+base64.b64encode((qa/ref['mask_path']).read_bytes()).decode(),edit_history=edits['operations'],action_history=edits['action_history'])
post('/objects/'+oid+'/reference',b)
post('/objects/'+oid+'/reference',{**b,'image_id':'frame_000057'},422)
v=post('/freeze',{'review_ack':True})['version'];r=c.get('/api/exports/'+v);assert r.status_code==200
z=zipfile.ZipFile(io.BytesIO(r.content));prefix='objects/'+oid+'/optional_reference/'
for name in ['reference.json','prompts.json','mask.png','overlay.jpg','edits.json','original/candidate_0.png','original/candidate_1.png','original/candidate_2.png']:assert prefix+name in z.namelist(),name
a=np.asarray(Image.open(io.BytesIO(z.read(prefix+'mask.png'))));original=np.asarray(Image.open(qa/ref['mask_path']));np.testing.assert_array_equal(a,original)
assert json.loads(z.read(prefix+'reference.json'))['split']=='train'
post('/objects/'+oid+'/reference/remove',{})
assert not (qa/prefix).exists()
assert c.get('/api/quality').json()['can_freeze']
assert (qa/'versions'/v/prefix/'mask.png').exists()
result=dict(status='passed',qa_directory=str(qa),object_id=oid,reference=ref['image_id'],original_resolution=list(Image.open(io.BytesIO(z.read(prefix+'mask.png'))).size),checks=['actual V2 masks only','reference confirmation','heldout rejection','all 3 original candidates exported','full edit history','mask pixel equality','reference removal','frozen version preserved'],note='Isolated software test, not production human confirmation.')
(P/'logs/m0_v2_optional_export.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
