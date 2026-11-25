#!/usr/bin/env python3
"""Invoke official open-vocabulary and triplet selection, save raw rankings and selected subsets."""
import argparse,json,pathlib,sys,os,re,hashlib
import numpy as np
from PIL import Image
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ReLaGS'));os.chdir(ROOT/'ReLaGS')
import torch
from scene import Scene,GaussianModel
from gaussian_renderer import render
from arguments import PipelineParams
from nag_data import SemanticNAG
from utils.vlm_utils import ClipSimMeasure
import utils.triplet_search_utils as triplet
from relags_relationships import load_relationship_embeddings
from predict_3d_scene_graph import REL_NAMES
from relags_audit import cpu
p=argparse.ArgumentParser();p.add_argument('--clip-model',required=True);p.add_argument('--graph-model',required=True);p.add_argument('--output',required=True);p.add_argument('--queries',default=str(ROOT/'configs/industrial_queries.json'));p.add_argument('--mode',choices=['all','open','relational'],default='all');a=p.parse_args()
out=pathlib.Path(a.output);(out/'data').mkdir(parents=True,exist_ok=True);(out/'visualizations').mkdir(exist_ok=True);(out/'metrics').mkdir(exist_ok=True)
config=json.loads(pathlib.Path(a.queries).read_text())
g=GaussianModel(3);args=argparse.Namespace(source_path=str(ROOT/'data'),model_path=a.clip_model,images='images',eval=True,resolution=2,white_background=False,data_device='cpu',sh_degree=3)
scene=Scene(args,g,load_iteration=0,shuffle=False,load_img=True,load_sem=False);pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda')
refs=[pathlib.Path(x).stem for x in json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']]
views=[v for v in scene.getTestCameras()+scene.getTrainCameras() if v.image_name in refs]
records=[]
def to_json(x):
    if torch.is_tensor(x):return x.detach().cpu().tolist()
    if isinstance(x,np.ndarray):return x.tolist()
    if isinstance(x,np.generic):return x.item()
    if isinstance(x,dict):return {str(k):to_json(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [to_json(v) for v in x]
    return x
def export(name,mask,record,raw):
    folder=out/'data'/name;folder.mkdir(exist_ok=True);vis=out/'visualizations'/name;vis.mkdir(exist_ok=True)
    mask=mask.detach().flatten().bool().cuda();ids=torch.where(mask)[0];np.save(folder/'gaussian_indices.npy',ids.cpu().numpy());torch.save(cpu(raw),folder/'raw_query.pt')
    record.update(id=name,selected_gaussians=len(ids));(folder/'result.json').write_text(json.dumps(to_json(record),indent=2))
    if len(ids):g.filter_gaussians(mask).save_ply(str(folder/'selected_gaussians.ply'))
    with torch.no_grad():
        color=mask.float()[:,None].repeat(1,3)
        for v in views:
            soft=render(v,g,pipe,bg,override_color=color)['render'][0].clamp(0,1)
            np.savez_compressed(folder/f'{v.image_name}_projection.npz',alpha_weighted_selection=soft.cpu().numpy())
            rgb=v.original_image[:3].cuda().clamp(0,1);highlight=torch.tensor([1.,.1,.1],device='cuda')[:,None,None]
            overlay=rgb*(1-.55*soft[None])+highlight*(.55*soft[None])
            Image.fromarray((overlay.permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8)).save(vis/f'{v.image_name}.png')
    records.append(to_json(record));print(json.dumps(to_json(record)),flush=True)
if a.mode in ['all','open']:
    clip=torch.load(pathlib.Path(a.clip_model)/'sai_nag_3.0.pt',map_location='cpu')
    snag=SemanticNAG(clip['nag'],[None]+[x.cuda() for x in clip['nag_feat']]);vlm=ClipSimMeasure()
for i,q in enumerate(config['open_vocabulary'] if a.mode in ['all','open'] else []):
    vlm.encode_text(q);scores=[vlm.compute_similarity(f) for f in snag.feat[1:]]
    root_mask,root_candidates=snag.search_matched_superpoint_in_mhtree(scores)
    mask,candidates=snag.search_matched_superpoint_in_mhtree(scores,level_until=0)
    raw={'scores':scores,'text_embeddings':vlm.text_feature,'root_candidates':root_candidates,'root_gaussian_mask':root_mask,'hierarchical_candidates':candidates,'hierarchical_gaussian_mask':mask}
    export(f'open_{i:02d}',mask,{'type':'open_vocabulary','query':q,'hierarchical_candidates':candidates,'root_candidates':root_candidates,'official_arguments':{'topk':5,'level_until':0,'filter_small':50,'remove_small':True},'empty_result':not bool(mask.any()),'note':'Official hierarchy code selects root/leaf levels; its single-candidate similarity-gap behavior is preserved.'},raw)
if a.mode in ['all','open']:
    del vlm,snag
    torch.cuda.empty_cache()
if a.mode in ['all','relational']:
    graph=pathlib.Path(a.graph_model);nag=torch.load(graph/'sai_nag_openseg.pt',map_location='cpu');jina_edges=torch.load(graph/'jina_edges_predicted.pt',map_location='cpu')
    snag=SemanticNAG(nag['nag'],[None]+[x.cuda() for x in nag['nag_feat']]);vlm=ClipSimMeasure(clip_type='ViT-L-14-336');_,encoder=load_relationship_embeddings(REL_NAMES,keep_model=True)
original_rank=triplet._rank_edges;ranked_audit=[]
def rank_with_audit(*args,**kwargs):
    r=original_rank(*args,**kwargs);ranked_audit.append(cpu(r));return r
triplet._rank_edges=rank_with_audit
for i,q in enumerate(config['relations'] if a.mode in ['all','relational'] else []):
    ranked_audit.clear()
    selection=triplet.search_triplet_subjects(q['subject'],q['object'],q['relation'],snag,snag.labels,jina_edges,vlm,encoder)
    scores={}
    for role in ['subject','object']:
        vlm.encode_text(q[role]);scores[role]=[vlm.compute_similarity(f) for f in snag.feat[1:]]
    mask=torch.zeros(len(g.get_xyz),device='cuda',dtype=torch.bool)
    for (cid,level),sims in selection:mask|=snag.labels[level]==cid
    fallback=bool(selection) and not all(all(float(s)>=t for s,t in zip(sims,[.55,.4,.55])) for _,sims in selection)
    export(f'relation_{i:02d}',mask,{'type':'relational','query':q,'selected':selection,'official_threshold_fallback_used':fallback,'empty_result':not bool(mask.any()),'official_arguments':{'topk':10,'filter_small':300,'sim_thresholds':[.55,.4,.55],'max_subjects':3},'relation_features':'Official predictor saves top-1 Jina relation-class embeddings; continuous GNN edge predictions are saved separately in Stage 08.'},{'scores':scores,'ranked_edges':ranked_audit,'selection':selection,'mask':mask})
query_hash=hashlib.sha256(pathlib.Path(a.queries).read_bytes()).hexdigest()
for mode in (['open','relational'] if a.mode=='all' else [a.mode]):
    selected=[r for r in records if r['type']==('open_vocabulary' if mode=='open' else 'relational')]
    (out/'metrics'/f'query_{mode}_summary.json').write_text(json.dumps({'status':'executed','mode':mode,'query_config_sha256':query_hash,'queries':selected},indent=2))
combined=[];missing=[]
for mode in ['open','relational']:
    path=out/'metrics'/f'query_{mode}_summary.json'
    report=json.loads(path.read_text()) if path.exists() else {}
    if report.get('query_config_sha256')==query_hash and report.get('status')=='executed':combined.extend(report['queries'])
    else:missing.append(mode)
(out/'metrics/query_summary.json').write_text(json.dumps({'status':'partial' if missing else 'executed','missing_modes':missing,'query_config_sha256':query_hash,'queries':combined,'no_ground_truth_accuracy':True,'coordinates':'Original COLMAP frame; left/right/gravity not calibrated'},indent=2))
