"""Unified execution; resume completed predictions and retain failed stage logs."""
from common import *
import argparse,subprocess
p=argparse.ArgumentParser();p.add_argument('--method',choices=['all','relags','langsplat','thgs','ours'],default='all');p.add_argument('--gpu',default='0');a=p.parse_args();check_frozen();assets=read(ROOT/'inputs/assets.json')['paths']
for method in (['relags','langsplat','thgs','ours'] if a.method=='all' else [a.method]):
    python=assets[method+'_python'] if method!='thgs' else str(ROOT/'envs/thgs/bin/python')
    if method=='relags' and not (ROOT/'outputs/relags/model/jina_edges_predicted.pt').exists():
        code=subprocess.call(['python3',str(ROOT/'scripts/run_command.py'),'--stage','relags_coordinate_alignment','--gpu',a.gpu,'--',python,str(ROOT/'scripts/align_relags.py')])
        if code:continue
    if method=='thgs':
        code=subprocess.call([assets['relags_python'],str(ROOT/'scripts/build_thgs.py')])
        if code:continue
    code=subprocess.call(['python3',str(ROOT/'scripts/run_command.py'),'--stage',method+'_queries','--gpu',a.gpu,'--',python,str(ROOT/'scripts'/('run_'+method+'.py'))])
    print(method,'exit',code,flush=True)
