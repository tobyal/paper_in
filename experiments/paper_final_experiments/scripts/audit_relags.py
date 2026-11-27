from common import *
import torch,argparse,inspect
verify_locks();sys.path.insert(0,str(PROJECT/'ReLaGS'));sys.path.insert(0,str(PROJECT/'ReLaGS/ext'))
from gaussian_renderer import render,GaussianModel
from arguments import PipelineParams
import utils.triplet_search_utils as triplet
bench_common=load_module('benchmark_common',BENCH/'scripts/common.py')
root=BENCH/'outputs/relags/model';audit=BENCH/'outputs/relags/coordinate_adaptation'
nag=torch.load(root/'sai_nag_openseg.pt',map_location='cpu');g=GaussianModel(3);g.load_ply(str(root/'point_cloud/iteration_0/point_cloud.ply'));xyz=g.get_xyz.detach().cpu().numpy();levels=[]
R=np.array(read(V2/'inputs/m0_state.json')['scene']['transform'])[:3,:3];assert np.allclose(R.T@R,np.eye(3),atol=1e-6);assert np.linalg.det(R)>0
adapt=read(audit/'adaptation.json');assert np.array_equal(R,np.array(adapt['rotation']))
for level in [2,3]:
    pre=torch.load(audit/f'level_{level}_pre_obb.pt',map_location='cpu');inp=torch.load(audit/f'level_{level}_graph_inputs.pt',map_location='cpu');labels=nag['nag'][level].cpu().numpy();unique=np.unique(labels)
    assert len(labels)==len(xyz);assert np.array_equal(labels,pre['cluster_labels']);assert np.allclose(xyz-xyz.mean(0),pre['points_centered'],atol=1e-4)
    assert list(inp['original_cluster_ids'])==unique.tolist();assert np.array_equal(unique,np.arange(len(unique)))
    assert torch.allclose(inp['node_language'],nag['nag_feat'][level-1][unique].cpu())
    lower=nag['nag'][level-1].cpu().numpy();order=np.argsort(lower);a=lower[order];b=labels[order];assert not np.any((a[1:]==a[:-1])&(b[1:]!=b[:-1]))
    levels.append(dict(level=level,gaussian_rows=len(labels),unique_nodes=len(unique),node_ids_contiguous=True,hierarchy_parent_consistent=True,language_rows_exact=True,pre_obb_xyz_centered_exact=True))
pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda');views=read(BENCH/'configs/evaluation_views.json')['cameras'];records=[]
for q in read(BENCH/'configs/benchmark_queries.json'):
    d=BENCH/'outputs/relags'/q['query_id'];result=read(d/'result.json');raw=torch.load(d/'raw_query.pt',map_location='cpu');mask=np.zeros(len(xyz),bool)
    for (cid,level),scores in result['selected_nodes']:mask|=nag['nag'][level].cpu().numpy()==cid
    ids=np.load(d/'gaussian_indices.npy');assert np.array_equal(np.flatnonzero(mask),ids);assert np.array_equal(mask,raw['mask'].numpy())
    colors=torch.tensor(mask.astype(np.float32),device='cuda')[:,None].repeat(1,3);rows=[]
    for iid in q['evaluation_camera_ids']:
        with torch.no_grad():soft=render(bench_common.camera_native(views[iid]),g,pipe,bg,override_color=colors)['render'][0].clamp(0,1).cpu().numpy()
        prior=np.load(d/iid/'response.npz')['response'];binary=np.array(Image.open(d/iid/'mask.png'))>0
        assert np.allclose(soft,prior,atol=2e-5);assert np.array_equal(soft>.5,binary)
        rows.append(dict(camera_id=iid,response_max_abs_error=float(np.max(abs(soft-prior))),mask_exact=True,pixels=int(binary.sum())))
    records.append(dict(query_id=q['query_id'],selected_nodes=result['selected_nodes'],gaussians=len(ids),fallback=result['official_threshold_fallback_used'],views=rows))
defaults={k:str(v.default) for k,v in inspect.signature(triplet.search_triplet_subjects).parameters.items() if v.default is not inspect.Parameter.empty}
write(ROOT/'E01_external_comparison/relags_engineering_audit.json',dict(status='passed_no_engineering_error_found',source_ply=str((root/'point_cloud/iteration_0/point_cloud.ply').resolve()),source_nag=str((root/'sai_nag_openseg.pt').resolve()),source_ply_sha256=sha(root/'point_cloud/iteration_0/point_cloud.ply'),source_nag_sha256=sha(root/'sai_nag_openseg.pt'),gaussian_rows=len(xyz),levels=levels,coordinate_rotation=R.tolist(),determinant=float(np.linalg.det(R)),official_defaults=defaults,official_fallback_count=sum(r['fallback'] for r in records),queries=records,conclusion='All 25 selected-node unions and 50 full-scene projections exactly match frozen outputs. No index, hierarchy, camera or rotation mismatch found. Learned-relation/domain mismatch remains a scientific limitation; no threshold changes or reranking.'))
print('ReLaGS audit passed: 25 selections, 50 binary projections, hierarchy and coordinate inputs',flush=True)
