#!/usr/bin/env python3
"""Compact read-only status of the finite baseline task."""
import datetime,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1];b=ROOT/'outputs/relags_baseline/02_image_encoding'
s={'time_beijing':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),'sam_clip':len(list((b/'data/language_features').glob('*_f.npy'))),'openseg':len(list((b/'data/language_features_openseg').glob('*_f_openseg.npy'))),'jobs':{}}
for name in ['sam_clip_shard_0','sam_clip_shard_1','sam_clip_shard_2','sam_clip_shard_3','openseg_all']:
    p=b/'metrics'/f'{name}.json'
    if not p.exists():continue
    d=json.loads(p.read_text());s['jobs'][name]=d['status']
    if d['status']=='failed':s[name+'_failure']=(pathlib.Path(d['attempt'])/'run.log').read_text(errors='replace')[-2200:]
p=ROOT/'logs/pipeline_progress.json'
if p.exists():s['pipeline']=json.loads(p.read_text())
s['active_jobs']=[]
for p in sorted((ROOT/'outputs/relags_baseline').glob('*/metrics/*.json')):
    try:d=json.loads(p.read_text())
    except (OSError,json.JSONDecodeError):continue
    if not isinstance(d,dict) or 'job' not in d or d.get('status')!='running':continue
    log=pathlib.Path(d['attempt'])/'run.log'
    tail=''
    if log.exists():
        with log.open('rb') as f:
            f.seek(max(0,log.stat().st_size-1600));tail=f.read().decode('utf-8',errors='replace')
    s['active_jobs'].append({'stage':d['stage'],'job':d['job'],'log_tail':tail})
print(json.dumps(s,ensure_ascii=False))
