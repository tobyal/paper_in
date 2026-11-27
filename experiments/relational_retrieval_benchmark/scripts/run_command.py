"""Record exact commands, complete logs, elapsed time and GPU usage per stage."""
import argparse,datetime,hashlib,json,os,subprocess,sys,threading,time,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--cwd',default=str(ROOT));p.add_argument('--gpu',default='0');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();cmd=a.command[1:] if a.command[:1]==['--'] else a.command
assert cmd
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');run=ROOT/'logs'/a.stage/stamp;run.mkdir(parents=True)
(ROOT/'cache/tmp').mkdir(parents=True,exist_ok=True)
env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES=a.gpu,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',TMPDIR=str(ROOT/'cache/tmp'),PIP_CACHE_DIR=str(ROOT/'cache/pip'),TORCH_EXTENSIONS_DIR=str(ROOT/'cache/torch_extensions'),HF_HOME=str(ROOT/'cache/huggingface'),TORCH_HOME=str(ROOT/'cache/torch'))
record=dict(command=cmd,cwd=a.cwd,gpu=a.gpu,start_utc=stamp,stage=a.stage)
with tarfile.open(run/'experiment_sources.tar.gz','w:gz') as archive:
    for source_dir in ['src','scripts','configs','docs/patches']:
        for file in (ROOT/source_dir).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts:archive.add(file,arcname=str(file.relative_to(ROOT)))
(run/'command.json').write_text(json.dumps(record,indent=2)+'\n');stop=threading.Event()
def monitor():
    with (run/'gpu.csv').open('w') as f:
        f.write('utc,index,memory.used MiB,utilization.gpu percent\n')
        while not stop.is_set():
            r=subprocess.run(['nvidia-smi','-i',a.gpu,'--query-gpu=index,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True)
            f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+','+r.stdout.strip()+'\n');f.flush();stop.wait(5)
t=threading.Thread(target=monitor,daemon=True);t.start();start=time.time()
with (run/'run.log').open('w',buffering=1) as log:
    child=subprocess.Popen(cmd,cwd=a.cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
    record['pid']=child.pid;(run/'command.json').write_text(json.dumps(record,indent=2)+'\n')
    for line in child.stdout:log.write(line);sys.stdout.write(line);sys.stdout.flush()
    code=child.wait()
stop.set();t.join(timeout=6);record.update(exit_code=code,status='completed' if code==0 else 'failed',seconds=time.time()-start)
(run/'result.json').write_text(json.dumps(record,indent=2)+'\n');print('RUN_RECORD',run,flush=True);sys.exit(code)
