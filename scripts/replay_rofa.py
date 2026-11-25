#!/usr/bin/env python3
"""Independently replay the unchanged official ROFA on saved multiview observations."""
import argparse,json,pathlib,os,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'ReLaGS'));os.chdir(ROOT/'ReLaGS')
import torch
import torch.nn.functional as F
from merge_proj import SAI3D
p=argparse.ArgumentParser();p.add_argument('--observations',required=True);p.add_argument('--output',required=True);p.add_argument('--vlm',choices=['clip','openseg'],required=True);a=p.parse_args()
source=pathlib.Path(a.observations);out=pathlib.Path(a.output);out.mkdir(parents=True,exist_ok=True)
stats=[]
for level in [1,2,3]:
    raw=torch.load(source/f'{a.vlm}_level_{level}_raw_observations.pt',map_location='cpu')
    expected=torch.load(source/f'{a.vlm}_level_{level}_rofa.pt',map_location='cpu')['aggregated_features']
    agent=SAI3D(argparse.Namespace(max_neighbor_distance=2,view_freq=5,dis_decay=.5,tau=raw['tau']));agent._audit_rofa=[]
    pooled=[];counts=[]
    for cid,observations in enumerate(raw['features']):
        agent._audit_cluster=cid;counts.append(len(observations))
        if observations:pooled.append(agent._filter_feature_outliers(torch.stack(observations).cuda(),'cuda'))
        else:pooled.append(torch.zeros(expected.shape[1],device='cuda'))
    result=F.normalize(torch.stack(pooled),p=2,dim=-1).cpu()
    error=float((result-expected).abs().max());assert torch.allclose(result,expected,atol=1e-6,rtol=1e-5),(level,error)
    torch.save({'aggregated_features':result,'decisions':agent._audit_rofa,'source':str(source),'tau':raw['tau']},out/f'{a.vlm}_level_{level}_replayed.pt')
    kept=sum(int(x['keep_mask'].sum()) for x in agent._audit_rofa);total=sum(counts)
    stats.append({'level':level,'clusters':len(counts),'empty_clusters':counts.count(0),'observation_count':total,'kept':kept,'rejected':total-kept,'max_abs_replay_error':error,'feature_dim':expected.shape[1]})
(out/f'{a.vlm}_replay_metrics.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats,indent=2))
