from common import *
import os,torch,argparse,traceback
check_frozen();load_start=time.perf_counter();sys.path.insert(0,str(PROJECT/'ReLaGS'));sys.path.insert(0,str(PROJECT/'ReLaGS/ext'));sys.path.insert(0,str(PROJECT/'scripts'));local_clip_weights()
from gaussian_renderer import render,GaussianModel
from arguments import PipelineParams
from nag_data import SemanticNAG
import utils.triplet_search_utils as triplet
from utils.vlm_utils import ClipSimMeasure
from relags_relationships import load_relationship_embeddings
from predict_3d_scene_graph import REL_NAMES
from relags_audit import cpu
graph=ROOT/'outputs/relags/model';nag=torch.load(graph/'sai_nag_openseg.pt',map_location='cpu');edges=torch.load(graph/'jina_edges_predicted.pt',map_location='cpu')
snag=SemanticNAG(nag['nag'],[None]+[v.cuda() for v in nag['nag_feat']]);vlm=ClipSimMeasure(clip_type='ViT-L-14-336');_,encoder=load_relationship_embeddings(REL_NAMES,keep_model=True)
g=GaussianModel(3);g.load_ply(str(graph/'point_cloud/iteration_0/point_cloud.ply'));pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda');sync();load_seconds=time.perf_counter()-load_start
queries=read(ROOT/'configs/benchmark_queries.json');views=read(ROOT/'configs/evaluation_views.json')['cameras'];native={k:camera_native(v) for k,v in views.items()};audit=[];original_rank=triplet._rank_edges
def rank(*a,**kw):
    result=original_rank(*a,**kw);audit.append(result);return result
triplet._rank_edges=rank
records=[]
for q in queries:
    dest=ROOT/'outputs/relags'/q['query_id'];dest.mkdir(parents=True,exist_ok=True)
    if (dest/'result.json').exists() and read(dest/'result.json')['status']=='completed':records.append(read(dest/'result.json'));continue
    try:
        def query():
            audit.clear();selection=triplet.search_triplet_subjects(q['subject_category'],q['object_category'],q['predicate_relags'],snag,snag.labels,edges,vlm,encoder)
            mask=torch.zeros(len(g.get_xyz),device='cuda',dtype=torch.bool)
            for (cid,level),sims in selection:mask|=(snag.labels[level]==cid).cuda()
            return selection,mask
        def project(result):
            color=result[1].float()[:,None].repeat(1,3)
            with torch.no_grad():return [render(native[iid],g,pipe,bg,override_color=color)['render'][0].clamp(0,1).cpu().numpy() for iid in q['evaluation_camera_ids']]
        (selected,mask),responses,timing=timed_pipeline(query,project)
        ids=torch.where(mask)[0].cpu().numpy();np.save(dest/'gaussian_indices.npy',ids);torch.save(cpu(dict(selection=selected,ranked_edges=audit,mask=mask)),dest/'raw_query.pt')
        if len(ids):g.filter_gaussians(mask).save_ply(str(dest/'selected_gaussians.ply'))
        record=dict(query=q,status='completed',empty_result=not len(ids),selected_gaussians=len(ids),selected_nodes=plain(selected),official_threshold_fallback_used=bool(selected) and not all(all(float(s)>=t for s,t in zip(sims,[.55,.4,.55])) for _,sims in selected),timing=timing,views=[export_view('relags',q,views[iid],soft,soft>.5) for iid,soft in zip(q['evaluation_camera_ids'],responses)])
    except Exception as e:
        traceback.print_exc();record=dict(query=q,status='failed',error=repr(e),traceback=traceback.format_exc())
    write(dest/'result.json',record);records.append(record);print(q['query_id'],record['status'],record.get('selected_gaussians'),flush=True)
    write(ROOT/'outputs/relags/summary.json',dict(method='ReLaGS',model_load_seconds=load_seconds,queries=records,completed=sum(r['status']=='completed' for r in records),total=len(queries)))
