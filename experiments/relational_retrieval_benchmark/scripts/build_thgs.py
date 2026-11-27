"""Run the four official THGS stages; resume only fully completed commands."""
from common import *
import subprocess,os
check_frozen();source=ROOT/'third_party/THGS';model=ROOT/'outputs/thgs/model';data=ROOT/'inputs/thgs_data';python=ROOT/'envs/thgs/bin/python'
stages=[('neighbors',['sp_partition.py','-m',str(model),'-a'],'neighbor.pt'),('reweight',['graph_weight.py','-s',str(data),'-m',str(model),'-r','2','--config',str(source/'configs/lerf.yml'),'--level','1'],'neighbor_new.pt'),('partition',['sp_partition.py','-m',str(model),'-a','-k','neighbor_new.pt','--pcp_regularization','0.1','--pcp_spatial_weight','0.1'],'nag-l1.pt'),('hierarchy',['merge_proj.py','-s',str(data),'-m',str(model),'-r','2','--thres_connect','0.9,0.7,0.7','--thres_merge','20','--feat_assign','2'],'sai_nag.pt')]
for stage,args,artifact in stages:
    record=ROOT/'outputs/thgs/build'/f'{stage}.json'
    if record.exists() and read(record)['status']=='completed' and (model/artifact).exists():continue
    start=time.perf_counter();command=[str(python),*args];code=subprocess.call(['python3',str(ROOT/'scripts/run_command.py'),'--stage','thgs_'+stage,'--cwd',str(source),'--gpu','0','--',*command])
    write(record,dict(status='completed' if code==0 else 'failed',command=command,seconds=time.perf_counter()-start,artifact=str(model/artifact),exit_code=code))
    if code:raise SystemExit(code)
