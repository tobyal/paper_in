"""Simple independent/resumable stage entry points. No task-scheduling framework."""
import argparse,os,sys,time,subprocess,threading,traceback,datetime,importlib,hashlib,shutil
from pathlib import Path
from .common import Context,STAGES,read,write,sha
MODULES={'M1':('spatial','run'),'M2.1':('views','run'),'M2.2':('segmentation','run'),'M2.3':('association','associate'),'M2.4':('association','extract'),'M2.5':('reprojection','run'),'M2.6':('reprojection','semantic_map'),'M3.1':('semantics','visual'),'M3.2':('semantics','aggregate'),'M3.3':('semantics','text'),'M3.4':('semantics','combine'),'M4':('graph','run'),'M5':('query','run'),'package':('export','run')}
DEPENDENCIES={'M1':[],'M2.1':['M1'],'M2.2':['M2.1'],'M2.3':['M2.2'],'M2.4':['M2.3'],'M2.5':['M2.4'],'M2.6':['M2.4'],'M3.1':['M2.2'],'M3.2':['M3.1'],'M3.3':['M1'],'M3.4':['M2.4','M3.2','M3.3'],'M4':['M3.4'],'M5':['M4'],'package':['M2.5','M2.6','M5']}
CONFIG_KEYS={'M1':['input'],'M2.1':['views','visibility'],'M2.2':['sam'],'M2.3':['visibility'],'M2.4':['association'],'M2.5':['reprojection','visibility'],'M2.6':[],'M3.1':['semantics'],'M3.2':['semantics'],'M3.3':[],'M3.4':[],'M4':['relations'],'M5':['query'],'package':[]}
def dependencies(ctx,stage):
 records={}
 for upstream in DEPENDENCIES[stage]:
  path=ctx.path(upstream,'summary.json')
  if not path.exists() or read(path).get('status')!='completed':raise RuntimeError(f'{stage} requires a completed {upstream}; run the upstream stage first')
  value=read(path);records[upstream]={'signature':value['signature'],'attempt':value['attempt']}
 return records
def fingerprint(ctx,stage):
 # Fingerprint the selected entry function, not unrelated functions in its file.
 import ast,json
 module,function=MODULES[stage];source=Path(__file__).with_name(module+'.py');tree=ast.parse(source.read_text(encoding='utf-8'))
 called=[]
 for node in tree.body:
  if not isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) or node.name==function or node.name not in {f for m,f in MODULES.values() if m==module}:called.append(ast.dump(node,include_attributes=False))
 keys=CONFIG_KEYS[stage];config={k:ctx.c[k] for k in keys};config.update(seed=ctx.c['seed'],visualization=ctx.c['visualization'])
 if stage in ['M2.2','M3.1','M3.3']:config['model_inputs']={k:v for k,v in ctx.c['input'].items() if k in (['sam'] if stage=='M2.2' else ['clip','clip_arch'])}
 code=sha(Path(__file__).with_name('common.py'))
 if stage in ['M1','M2.1','M2.3','M2.5','M2.6','M5']:code+=sha(Path(__file__).with_name('render.py'))
 if stage in ['M5','package']:code+=sha(Path(__file__).with_name('model.py'))
 return hashlib.sha256((json.dumps(config,sort_keys=True)+str(called)+code).encode()).hexdigest()
class Tee:
 def __init__(self,*files):self.files=files
 def write(self,value):
  for f in self.files:f.write(value);f.flush()
 def flush(self):
  for f in self.files:f.flush()
def execute(ctx,stage,force=False):
 module,function=MODULES[stage];signature=fingerprint(ctx,stage);inputs=dependencies(ctx,stage);summary=ctx.path(stage,'summary.json')
 if summary.exists() and read(summary).get('status')=='completed' and read(summary).get('signature')==signature and read(summary).get('upstream')==inputs and not force:print('REUSE',stage,flush=True);return
 if summary.exists() and read(summary).get('status')=='completed':
  archive=ctx.out/'.history'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')/STAGES[stage];archive.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(ctx.path(stage),archive)
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');attempt=ctx.out/'runs'/stage/stamp;attempt.mkdir(parents=True,exist_ok=True);shutil.copy2(ctx.config_path,attempt/'config.json');shutil.copytree(Path(__file__).parent,attempt/'code',ignore=shutil.ignore_patterns('__pycache__'))
 write(attempt/'command.json',dict(argv=sys.argv,python=sys.executable,working_directory=os.getcwd(),gpu=ctx.c['gpu'],signature=signature,upstream=inputs));stop=threading.Event()
 def sample():
  with open(attempt/'gpu.csv','w') as f:
   f.write('time_utc,index,memory.used MiB,memory.total MiB,utilization.gpu percent\n')
   while not stop.is_set():
    r=subprocess.run(['nvidia-smi','-i',str(ctx.c['gpu']),'--query-gpu=index,memory.used,memory.total,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True);f.write(datetime.datetime.now(datetime.timezone.utc).isoformat()+','+r.stdout.strip()+'\n');f.flush();stop.wait(5)
 thread=threading.Thread(target=sample,daemon=True);thread.start();start=time.time();oldout,olderr=sys.stdout,sys.stderr
 with open(attempt/'run.log','w',buffering=1) as log:
  sys.stdout=Tee(oldout,log);sys.stderr=Tee(olderr,log)
  try:
   import torch
   torch.set_num_threads(4);torch.manual_seed(ctx.c['seed']);torch.cuda.reset_peak_memory_stats();result=getattr(importlib.import_module('.'+module,__package__),function)(ctx)
   record=dict(stage=stage,status='completed',signature=signature,upstream=inputs,signature_version=2,seconds=time.time()-start,result=result,torch_peak_allocated_bytes=torch.cuda.max_memory_allocated(),torch_peak_reserved_bytes=torch.cuda.max_memory_reserved(),gpu_samples_scope='Entire selected GPU, including other processes',attempt=str(attempt.relative_to(ctx.out)));write(summary,record);write(attempt/'result.json',record);print('COMPLETE',stage,result,flush=True)
  except BaseException as e:
   traceback.print_exc();record=dict(stage=stage,status='failed',signature=signature,upstream=inputs,seconds=time.time()-start,error=type(e).__name__+': '+str(e),attempt=str(attempt.relative_to(ctx.out)));write(summary,record);write(attempt/'result.json',record);raise
  finally:stop.set();thread.join(timeout=6);sys.stdout,sys.stderr=oldout,olderr
def main():
 p=argparse.ArgumentParser();p.add_argument('--config',default='configs/industrial_world_model.json');p.add_argument('--stage',choices=list(STAGES));p.add_argument('--from',dest='start',default='M1',choices=list(STAGES));p.add_argument('--to',dest='end',default='package',choices=list(STAGES));p.add_argument('--force',action='store_true');a=p.parse_args();ctx=Context(a.config);os.environ['CUDA_VISIBLE_DEVICES']=str(ctx.c['gpu']);os.environ.setdefault('OMP_NUM_THREADS','4');os.environ.setdefault('OPENBLAS_NUM_THREADS','4')
 if a.stage:return execute(ctx,a.stage,a.force)
 stages=list(STAGES);selected=stages[stages.index(a.start):stages.index(a.end)+1]
 for stage in selected:
  command=[sys.executable,'-u','-m',__package__+'.run','--config',str(ctx.config_path),'--stage',stage]+(['--force'] if a.force else []);r=subprocess.run(command,cwd=ctx.project)
  if r.returncode:raise SystemExit(r.returncode)
if __name__=='__main__':main()
