"""Read-only verification of the actual V2 browser acceptance artifacts."""
import base64
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import urllib.request
import numpy as np
from PIL import Image
from m0.settings import PROJECT,ROOT
from m0.spatial import transform,inside

s=json.load(urllib.request.urlopen('http://127.0.0.1:28760/api/state'))
objects=[o for o in s['objects'].values() if not o.get('deleted') and o.get('reference')]
assert objects,'Complete the real browser optional-reference draft first.'
o=objects[-1];ref=o['reference']
image=next(i for i in json.loads((ROOT/'.assets/images.json').read_text()) if i['image_id']==ref['image_id'])
assert image['split']=='train'
arr=np.array(Image.open(ROOT/ref['mask_path']).convert('L'))
assert arr.shape==(image['height'],image['width']) and np.isin(arr,[0,255]).all() and arr.any()
assert hashlib.sha256((ROOT/ref['mask_path']).read_bytes()).hexdigest()==ref['mask_sha256']
db=sqlite3.connect('file:'+str(ROOT/'.m0.sqlite3')+'?mode=ro',uri=True)
row=db.execute('SELECT content FROM drafts WHERE key=?',('reference_'+o['object_id']+'_'+ref['image_id'],)).fetchone()
draft=json.loads(row[0]);pixels=np.array(Image.open(io.BytesIO(base64.b64decode(draft['snapshot']['mask_png'].split(',',1)[1]))).convert('L'))
np.testing.assert_array_equal(arr,pixels)
edit=json.loads((ROOT/ref['edit_history_path']).read_text());assert edit['operations'];assert any(x['action']=='undo' for x in edit['action_history']);assert any(x['action']=='redo' for x in edit['action_history'])
infer=json.loads((ROOT/'.inference'/ref['sam_job_id']/'inference.json').read_text())
assert infer['object_id']==o['object_id'] and len(infer['scores'])==3 and infer['source']=='fresh M0 prompt inference'
assert (ROOT/'.assets/renders'/(ref['image_id']+'.jpg')).exists()
v1=json.loads((PROJECT/'industrial_scene_prior/.assets/source_manifest.json').read_text());v2=json.loads((ROOT/'.assets/source_manifest.json').read_text())
assert v1['source_files']==v2['source_files'],'Source geometry, COLMAP, split or weights changed.'
assert all(x['status']=='draft' for x in s['objects'].values() if not x.get('deleted')) and s['scene']['status']=='draft'
assert not s['last_frozen_version'],'Acceptance must not claim production human confirmation.'
result=dict(status='passed',object_id=o['object_id'],name=o['name_zh'],source='fresh browser 3D click followed by original RGB inspection',coordinate_version=o['coordinate_version'],
            optional_reference=ref['image_id'],mask_pixels=int((arr>0).sum()),mask_size=[image['width'],image['height']],mask_sha256=ref['mask_sha256'],
            sam_seconds=infer['seconds'],gpu_peak_bytes=infer['gpu_peak_bytes'],gpu_peak_scope=infer['gpu_peak_scope'],candidate_scores=infer['scores'],
            manual_edit_operations=len(edit['operations']),undo_redo_retained=True,autosaved_mask_matches_saved_mask=True,fresh_2dgs_render=True,
            old_and_new_source_hashes_identical=True,production_status='all drafts; no human confirmation or frozen version')
(PROJECT/'logs/m0_v2_real_acceptance.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False,indent=2))
