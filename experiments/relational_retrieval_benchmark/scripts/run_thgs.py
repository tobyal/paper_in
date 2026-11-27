from common import *
import torch,argparse,traceback
from plyfile import PlyData,PlyElement
check_frozen();start=time.perf_counter();source=ROOT/'third_party/THGS';sys.path.insert(0,str(source));sys.path.insert(0,str(source/'ext'));local_clip_weights()
from gaussian_renderer import render,GaussianModel
from nag_data import SemanticNAG
from utils.vlm_utils import ClipSimMeasure
from arguments import PipelineParams
model=ROOT/'outputs/thgs/model';nag=torch.load(model/'sai_nag.pt',map_location='cuda');snag=SemanticNAG(nag['nag'],nag['nag_feat']);vlm=ClipSimMeasure();vlm.load_model();g=GaussianModel(3,20);plypath=model/'point_cloud/iteration_30000/point_cloud.ply';g.load_ply(str(plypath));g.active_sh_degree=3;vertices=PlyData.read(plypath)['vertex'].data;pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda');sync();load_seconds=time.perf_counter()-start
views=read(ROOT/'configs/evaluation_views.json')['cameras'];native={iid:camera_native(c) for iid,c in views.items()};records=[]
for q in read(ROOT/'configs/benchmark_queries.json'):
    dest=ROOT/'outputs/thgs'/q['query_id'];dest.mkdir(parents=True,exist_ok=True)
    if (dest/'result.json').exists() and read(dest/'result.json')['status']=='completed':records.append(read(dest/'result.json'));continue
    try:
        def query():
            vlm.encode_text(q['query_en']);scores=[vlm.compute_similarity(f) for f in snag.feat];mask=snag.get_related_gaussian(scores,topk=3,level=[2,3]);return scores,mask
        def project(result):
            g._semantics=result[1].expand(-1,20).cuda()
            with torch.no_grad():return [render(native[iid],g,pipe,bg)['semantics'][0].clamp(0,1).cpu().numpy() for iid in q['evaluation_camera_ids']]
        (scores,mask),responses,timing=timed_pipeline(query,project);ids=torch.where(mask[:,0]>0)[0].cpu().numpy();np.save(dest/'gaussian_indices.npy',ids);torch.save(dict(scores=[s.detach().cpu() for s in scores],mask=mask.cpu()),dest/'raw_query.pt')
        matches=[]
        for level in [2,3]:
            values,indices=scores[level-1].topk(3);matches.extend([(level,float(v),int(i)) for v,i in zip(values,indices)])
        matches.sort(key=lambda x:x[1],reverse=True);matches=matches[:3]
        if len(ids):PlyData([PlyElement.describe(vertices[ids],'vertex')]).write(str(dest/'selected_gaussians.ply'))
        record=dict(query=q,status='completed',empty_result=not len(ids),selected_gaussians=len(ids),selected_nodes=[dict(level=l,score=s,node_id=i) for l,s,i in matches],timing=timing,views=[export_view('thgs',q,views[iid],soft,soft>.5) for iid,soft in zip(q['evaluation_camera_ids'],responses)])
    except Exception as e:traceback.print_exc();record=dict(query=q,status='failed',error=repr(e),traceback=traceback.format_exc())
    write(dest/'result.json',record);records.append(record);write(ROOT/'outputs/thgs/summary.json',dict(method='THGS',model_load_seconds=load_seconds,queries=records,completed=sum(r['status']=='completed' for r in records),total=25));print(q['query_id'],record['status'],record.get('selected_gaussians'),flush=True)
