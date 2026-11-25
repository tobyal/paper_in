"""Integration evidence on genuine workshop data. All records remain unconfirmed drafts."""
import base64
import json
import time
from pathlib import Path
import httpx
import numpy as np
from PIL import Image
from m0.settings import ROOT, PROJECT
from m0.storage import now

client=httpx.Client(base_url='http://127.0.0.1:28760/api',headers={'X-M0-Client':'1'},timeout=180,trust_env=False)
evidence={'started_at':now(),'purpose':'Real-data software acceptance only. No human-confirmed prior or ground truth is created.','checks':[]}

def get(p):
    r=client.get(p);r.raise_for_status();return r.json()

def post(p,b):
    r=client.post(p,json=b);assert r.status_code==200,(p,r.status_code,r.text[:1000]);return r.json()

def env(b): return {'revision':get('/state')['revision'],'reviewer':'Codex acceptance / pending human review','review_ack':False,**b}

def job(p,b):
    r=post(p,b)
    while r['status'] in ('queued','running'):time.sleep(.5);r=get('/jobs/'+r['job_id'])
    assert r['status']=='complete',r
    return r['result']

def main():
    s=get('/state');oid=next(o['object_id'] for o in s['objects'].values() if o['category_en']=='white mesh cart')
    o=s['objects'][oid];post('/objects',env({**o,'source':'codex_candidate'}))
    # Repeat the same image with positive + negative points; exercise image embedding reuse.
    rec=job('/sam',dict(object_id=oid,image_id='frame_000050',scope='priors',prompts=dict(bbox=o['anchor_bbox'],points=[[1250,400],[1400,500]],labels=[1,0])))
    evidence['checks'].append({'name':'fresh_prompt_sam_and_cached_encoding','result':rec})
    for number,scope,box,point in [(66,'priors',[1410,290,1680,570],[1535,410]),(57,'ground_truth',[890,285,1090,545],[985,410])]:
        image_id=f'frame_{number:06d}'
        rec=job('/sam',dict(object_id=oid,image_id=image_id,scope=scope,prompts=dict(bbox=box,points=[point],labels=[1])))
        candidate=int(np.argmax(rec['scores']));path=ROOT/'.inference'/rec['job_id']/f'candidate_{candidate}.png'
        payload=dict(object_id=oid,image_id=image_id,scope=scope,sam_job_id=rec['job_id'],candidate=candidate,
                     mask_png='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode(),visibility='clear',review_status='draft',
                     edit_history=[],notes='Real-data acceptance candidate. Same white mesh cart visually matched across views; identity and boundaries require human review.')
        saved=post('/annotations',env(payload))['annotation']
        with Image.open(ROOT/saved['mask_path']) as im: assert im.size==(1875,1056)
        assert np.array_equal(np.asarray(Image.open(path)),np.asarray(Image.open(ROOT/saved['mask_path'])))
        evidence['checks'].append(dict(name='multi_view_and_heldout_round_trip',inference=rec,annotation=saved))
    desc=dict(name_zh='白色网格推车',name_en='White mesh cart',synonyms_en=['wheeled mesh cart','mesh-sided cart'],
              visual_description_en='A white rectangular mesh-sided cart with a flat top, dark interior areas, a low yellow bar and visible caster wheels.',
              visual_description_zh='白色矩形框架的网格推车，可见平顶、深色内部区域、底部黄色横条和脚轮。',
              color='white; yellow lower bar',shape='rectangular',structural_features='white frame and grid panels',visible_parts='frame; mesh panels; caster wheels',
              distinguishing_features='yellow lower bar; narrow rectangular front',optional_facts='unknown',source='codex_candidate',review_status='draft')
    post('/descriptions/'+oid,env(desc));evidence['checks'].append(dict(name='bound_bilingual_description',object_id=oid,review_status='draft'))
    for p,b in [('/sam',dict(object_id=oid,image_id='frame_000057',scope='priors',prompts=dict(bbox=[890,285,1090,545]))),('/freeze',env({'review_ack':True}))]:
        r=client.post(p,json=b);assert r.status_code==422,(p,r.text);evidence['checks'].append(dict(name='expected_rejection',endpoint=p,status=r.status_code,detail=r.json()))
    render=job('/render/frame_000050',{});evidence['checks'].append(dict(name='fresh_geometry_render',result=render))
    state=get('/state');assert all(a['review_status']=='draft' for a in state['annotations'].values())
    evidence.update(finished_at=now(),object_id=oid,revision=state['revision'],quality=get('/quality'),status='passed')
    target=PROJECT/'logs/m0_real_scene_acceptance.json';target.write_text(json.dumps(evidence,indent=2,ensure_ascii=False))
    print(json.dumps({'status':'passed','object_id':oid,'checks':len(evidence['checks']),'report':str(target)},ensure_ascii=False))


if __name__=='__main__':main()
