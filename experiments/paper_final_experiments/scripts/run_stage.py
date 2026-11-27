from common import *
import subprocess,os,datetime,threading,shutil,argparse
p=argparse.ArgumentParser();p.add_argument('stage');p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();cmd=a.command
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');dest=ROOT/'logs'/a.stage/stamp;dest.mkdir(parents=True)
for s in (ROOT/'scripts').glob('*.py'):shutil.copy2(s,dest/s.name)
env=os.environ.copy();env.update(PYTHONDONTWRITEBYTECODE='1',CUDA_VISIBLE_DEVICES='0',TMPDIR=str(ROOT/'cache/tmp'),MPLCONFIGDIR=str(ROOT/'cache/matplotlib'))
write(dest/'command.json',dict(argv=cmd,cwd=str(ROOT),environment={k:env[k] for k in ['PYTHONDONTWRITEBYTECODE','CUDA_VISIBLE_DEVICES','TMPDIR','MPLCONFIGDIR']},utc=stamp))
done=threading.Event()
def sample():
    with (dest/'gpu.csv').open('w') as f:
        f.write('utc,index,memory_used_MiB,utilization_percent\n')
        while not done.is_set():
            out=subprocess.run(['nvidia-smi','--query-gpu=index,memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True)
            for line in out.stdout.splitlines():f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+','+line+'\n')
            f.flush();done.wait(1)
t=threading.Thread(target=sample);t.start();start=time.perf_counter()
try:
    with (dest/'run.log').open('w') as f:
        proc=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1)
        for line in proc.stdout:f.write(line);f.flush();print(line,end='',flush=True)
        rc=proc.wait()
finally:done.set();t.join()
write(dest/'runtime.json',dict(exit_code=rc,wall_seconds=time.perf_counter()-start,command=cmd,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()));sys.exit(rc)

