#!/usr/bin/env python3
"""Execute one official command with immutable attempt logs, resource samples and cache validation."""
import argparse,datetime,hashlib,json,os,pathlib,shlex,shutil,subprocess,sys,threading,time
ROOT=pathlib.Path(__file__).resolve().parents[1]
def js(p,d):
    p.parent.mkdir(parents=True,exist_ok=True)
    q=p.with_suffix(p.suffix+'.tmp');q.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n');os.replace(q,p)
def fingerprint(p):
    p=pathlib.Path(p)
    if not p.is_absolute(): p=ROOT/p
    s=p.stat();d={'path':str(p),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
    if s.st_size<10*1024*1024: d['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
    return d
def tree(pid):
    raw=subprocess.check_output(['ps','-eo','pid=,ppid='],text=True)
    pairs=[tuple(map(int,s.split())) for s in raw.splitlines() if s.strip()]
    own={pid};last=0
    while len(own)!=last:
        last=len(own);own.update(p for p,q in pairs if q in own)
    return own
def main():
    a=argparse.ArgumentParser();a.add_argument('--stage',required=True);a.add_argument('--job',required=True);a.add_argument('--cwd',default='ReLaGS');a.add_argument('--gpu',default='3');a.add_argument('--input',action='append',default=[]);a.add_argument('--expect',action='append',default=[]);a.add_argument('--force',action='store_true');a.add_argument('command',nargs=argparse.REMAINDER);args=a.parse_args()
    cmd=args.command[1:] if args.command[:1]==['--'] else args.command
    if not cmd: raise ValueError('No command')
    stage=ROOT/'outputs/relags_baseline'/args.stage
    oldpath=stage/'metrics'/f'{args.job}.json'
    # A command may legitimately produce metrics/<job>.json. Never overwrite
    # that scientific result with this runner's execution bookkeeping.
    declared_outputs={(pathlib.Path(p) if pathlib.Path(p).is_absolute() else ROOT/p).resolve() for p in args.expect}
    if oldpath.resolve() in declared_outputs:
        oldpath=oldpath.with_name(f'{args.job}_execution.json')
    inputs=[fingerprint(p) for p in args.input]
    signature=hashlib.sha256(json.dumps({'cmd':cmd,'cwd':args.cwd,'gpu':args.gpu,'inputs':inputs},sort_keys=True).encode()).hexdigest()
    if oldpath.exists() and not args.force:
        old=json.loads(oldpath.read_text())
        if old.get('status')=='completed' and old.get('signature')==signature:
            try:
                if old['outputs']==[fingerprint(p) for p in args.expect]:
                    print('REUSED',args.stage,args.job,flush=True);return
            except FileNotFoundError: pass
    timestamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    attempt=stage/'runs'/f'{timestamp}_{args.job}';attempt.mkdir(parents=True,exist_ok=False)
    env=os.environ.copy();env.update(CUDA_VISIBLE_DEVICES=args.gpu,CUDA_HOME='/usr/local/cuda-11.8',TORCH_CUDA_ARCH_LIST='8.6',MAX_JOBS='8',OMP_NUM_THREADS='8',OPENBLAS_NUM_THREADS='8',MKL_NUM_THREADS='8',PYTHONUNBUFFERED='1',PYTHONDONTWRITEBYTECODE='1',HF_HOME=str(ROOT/'models/huggingface'),TORCH_HOME=str(ROOT/'models/torch'),PIP_CACHE_DIR=str(ROOT/'.cache/pip'),http_proxy='http://127.0.0.1:17891',https_proxy='http://127.0.0.1:17891',HF_HUB_DISABLE_TELEMETRY='1')
    env['PATH']=str(ROOT/'envs/relags/bin')+':/usr/local/cuda-11.8/bin:'+env.get('PATH','')
    env['RELAGS_ATTEMPT_ID']=attempt.name
    env['RELAGS_CLIP_CHECKPOINT']=str(ROOT/'models/openclip_vit_b16/open_clip_pytorch_model.bin')
    cwd=ROOT/args.cwd
    envkeys=['CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','HF_HOME','TORCH_HOME','CUDA_HOME','TORCH_CUDA_ARCH_LIST','MAX_JOBS','RELAGS_CLIP_CHECKPOINT','LD_LIBRARY_PATH','http_proxy','https_proxy']
    run={'stage':args.stage,'job':args.job,'status':'running','started_utc':timestamp,'command':cmd,'shell_command':shlex.join(cmd),'cwd':str(cwd),'gpu':args.gpu,'signature':signature,'inputs':inputs,'expected_outputs':args.expect,'attempt':str(attempt),'environment':{k:env[k] for k in envkeys if k in env}}
    js(attempt/'config.yaml',run);js(oldpath,run)
    for meta in inputs:
        source=pathlib.Path(meta['path'])
        if meta['bytes']<1024*1024 and source.is_file():
            rel=source.relative_to(ROOT) if source.is_relative_to(ROOT) else pathlib.Path(source.name)
            target=attempt/'input_snapshot'/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    for name in ['logs/environment_manifest.json','logs/patches/all_baseline_adaptations.patch','logs/patches/2dgs_matplotlib_api.patch']:
        source=ROOT/name
        if source.exists():
            target=attempt/'input_snapshot'/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    (attempt/'command.sh').write_text('source '+shlex.quote(str(ROOT/'scripts/common.sh'))+'\n'+'\n'.join('export '+k+'='+shlex.quote(v) for k,v in run['environment'].items())+'\ncd '+shlex.quote(str(cwd))+'\n'+shlex.join(cmd)+'\n')
    stop=threading.Event();samples=[];start=time.time()
    with (attempt/'run.log').open('w') as log:
        p=subprocess.Popen(['/usr/bin/time','-v','-o',str(attempt/'time.txt'),*cmd],cwd=cwd,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        run['pid']=p.pid;js(oldpath,run)
        def monitor():
            with (attempt/'gpu_samples.jsonl').open('w') as f:
                while not stop.is_set():
                    row={'elapsed_seconds':time.time()-start}
                    try:
                        row['gpus']=subprocess.check_output(['nvidia-smi','--query-gpu=index,uuid,memory.used,utilization.gpu','--format=csv,noheader,nounits'],text=True,timeout=10).strip()
                        raw=subprocess.check_output(['nvidia-smi','--query-compute-apps=pid,gpu_uuid,used_memory','--format=csv,noheader,nounits'],text=True,timeout=10)
                        own=tree(p.pid);row['own_pids']=sorted(own);row['compute_processes']=raw.strip()
                        mem=[]
                        for line in raw.splitlines():
                            cols=[x.strip() for x in line.split(',')]
                            if len(cols)==3 and cols[0].isdigit() and int(cols[0]) in own and cols[2].isdigit(): mem.append(int(cols[2]))
                        row['own_gpu_memory_mib']=sum(mem);samples.append(row['own_gpu_memory_mib'])
                    except Exception as e: row['error']=repr(e)
                    f.write(json.dumps(row)+'\n');f.flush();stop.wait(5)
        t=threading.Thread(target=monitor,daemon=True);t.start();rc=p.wait();stop.set();t.join(timeout=15)
    run.update(exit_code=rc,elapsed_seconds=time.time()-start,peak_sampled_own_gpu_mib=max(samples,default=0),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    try:
        run['outputs']=[fingerprint(p) for p in args.expect]
        if any(x['bytes']==0 for x in run['outputs']): raise ValueError('Empty output file')
        run['status']='completed' if rc==0 else 'failed'
    except Exception as e: run.update(status='failed',validation_error=repr(e))
    js(attempt/'status.json',run);js(oldpath,run)
    with (stage/'run.log').open('a') as f:
        f.write('\nATTEMPT '+str(attempt)+'\n'+shlex.join(cmd)+'\n')
        with (attempt/'run.log').open(errors='replace') as src:
            for line in src:f.write(line)
        f.write('\n'+json.dumps({k:run[k] for k in ['status','exit_code','elapsed_seconds','peak_sampled_own_gpu_mib']})+'\n')
    print(json.dumps(run,ensure_ascii=False),flush=True)
    if run['status']!='completed':sys.exit(rc or 1)
if __name__=='__main__':main()
