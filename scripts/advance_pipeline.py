#!/usr/bin/env python3
"""Dependency-aware continuation of this finite baseline run, not a recurring automation."""
import datetime,json,pathlib,subprocess,sys,time,os
from pipeline import ROOT,STAGES,stage,done
def execute(i):
    subprocess.run([sys.executable,str(ROOT/'scripts/pipeline.py'),'--stage',str(i)],cwd=ROOT,check=True)
status=ROOT/'logs/pipeline_progress.json'
def record(state,detail):
    data={'time_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':state,'detail':detail,'pid':os.getpid()}
    status.write_text(json.dumps(data,indent=2));print(json.dumps(data),flush=True)
def wait_job(i,job):
    p=stage(i)/'metrics'/f'{job}.json';last=''
    while True:
        d=json.loads(p.read_text()) if p.exists() else {}
        state=d.get('status','pending')
        if state=='completed':return
        if state=='failed':raise RuntimeError(f'{STAGES[i]}/{job} failed: '+d.get('attempt',''))
        if state!=last:record('waiting',f'{STAGES[i]}/{job}: {state}');last=state
        time.sleep(20)
def wait_file(path):
    record('waiting',str(path))
    while not path.exists():time.sleep(20)
try:
    wait_job(1,'train_2dgs');wait_job(1,'render_2dgs')
    record('executing','03_gaussian_pruning');execute(3)
    wait_file(ROOT/'logs/environment.completed')
    record('executing','04_superpoint_partition');execute(4)
    for j in range(4):wait_job(2,f'sam_clip_shard_{j}')
    wait_job(2,'verify_encoding')
    record('executing','05_hierarchical_grouping');execute(5)
    wait_job(2,'openseg_all')
    d=json.loads((stage(2)/'metrics/openseg_verification.json').read_text());assert d['status']=='verified' and d['images']==350
    subprocess.run([sys.executable,str(ROOT/'scripts/run_stage.py'),'--stage','02_image_encoding','--job','encoding_diagnostics','--gpu','3','--cwd','.','--input',str(ROOT/'scripts/encoding_diagnostics.py'),'--expect',str(stage(2)/'metrics/encoding_diagnostics.json'),'--','python','scripts/encoding_diagnostics.py'],cwd=ROOT,check=True)
    done(2,'350 帧全新 SAM/CLIP 和 OpenSeg 完成并通过格式/有限数值检查；不代表分割和语义准确率已得到真值验证。')
    for i in range(6,10):record('executing',STAGES[i]);execute(i)
    record('completed','All requested computation stages executed; final qualitative review required.')
except Exception as e:
    record('failed',repr(e));subprocess.run([sys.executable,str(ROOT/'scripts/update_report.py')]);raise
