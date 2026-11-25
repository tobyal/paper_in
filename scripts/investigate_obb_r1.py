"""Replay upstream L2 grouping and the unmodified OBB function on original inputs."""
import ast,collections,hashlib,json,pathlib,subprocess,sys,time
import numpy as np
import torch
import open3d as o3d
from plyfile import PlyData
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/relags_baseline';OUT=ROOT/'outputs/relags_obb_repair_r1/00_investigation'
def upstream(name):return subprocess.check_output(['git','-C',str(ROOT/'ReLaGS'),'show','HEAD:'+name],text=True)
def save_json(name,d):(OUT/'metrics'/name).write_text(json.dumps(d,indent=2))
sources={name:upstream(name) for name in ['merge_proj.py','scene_graph/network_utils.py','predict_3d_scene_graph.py','sp_partition.py']}
for name,t in sources.items():(OUT/'data'/('upstream_'+name.replace('/','_'))).write_text(t)
scope={};exec(compile(sources['scene_graph/network_utils.py'],'official_network_utils.py','exec'),scope)
official_obb=scope['get_oriented_bounding_boxes']
original_class=next(x for x in ast.parse(sources['merge_proj.py']).body if isinstance(x,ast.ClassDef) and x.name=='SAI3D')
current_class=next(x for x in ast.parse((ROOT/'ReLaGS/merge_proj.py').read_text()).body if isinstance(x,ast.ClassDef) and x.name=='SAI3D')
method_checks={}
for name in ['assign_seg_label_torch','judge_connect_torch_opt','get_seg_data_torch','merge_small_segs_torch']:
    old=next(x for x in original_class.body if isinstance(x,ast.FunctionDef) and x.name==name)
    new=next(x for x in current_class.body if isinstance(x,ast.FunctionDef) and x.name==name)
    method_checks[name]=ast.dump(old,include_attributes=False)==ast.dump(new,include_attributes=False)
assert all(method_checks.values())
ns={'torch':torch,'np':np,'deque':collections.deque,'time':time}
exec(compile(ast.Module(body=[original_class],type_ignores=[]),'official_merge_class.py','exec'),ns)
nag=torch.load(BASE/'06_semantic_aggregation/data/model/sai_nag_openseg.pt',map_location='cpu')
clip=torch.load(BASE/'05_hierarchical_grouping/data/model/sai_nag_3.0.pt',map_location='cpu')
v=PlyData.read(BASE/'03_gaussian_pruning/data/model/point_cloud/iteration_0/point_cloud.ply')['vertex'].data
xyz=np.stack([v[k] for k in ['x','y','z']],axis=1);centered=xyz-xyz.mean(0,keepdims=True)
original_fail=torch.load(BASE/'08_scene_graph/data/20261125T004631Z_predict_graph/level_2_pre_obb.pt',map_location='cpu')
checks={'gaussian_xyz_finite':bool(np.isfinite(xyz).all()),'pre_obb_points_exact':np.array_equal(centered,original_fail['points_centered']),'pre_obb_labels_exact':np.array_equal(nag['nag'][2].numpy(),original_fail['cluster_labels']),'branch_labels_identical':all(torch.equal(x,y) for x,y in zip(nag['nag'],clip['nag']))}
for level in [2,3]:
    labels=nag['nag'][level].numpy();ids=np.unique(labels)
    checks[f'level_{level}_length']=len(labels)==len(xyz)
    checks[f'level_{level}_ids_contiguous']=np.array_equal(ids,np.arange(len(ids)))
    checks[f'level_{level}_feature_rows']=len(nag['nag_feat'][level-1])==len(ids)
assert all(checks.values()),checks
failure_ids=[1822,1836,1927,1987,2307];records=[]
for cid in failure_ids:
    idx=np.flatnonzero(nag['nag'][2].numpy()==cid);pts=centered[idx]
    try:official_obb(centered,nag['nag'][2].numpy(),[cid],True);raise AssertionError('Original failure did not reproduce')
    except RuntimeError as error: original_error=str(error)
    pc=o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts));_,kept=pc.remove_statistical_outlier(nb_neighbors=20,std_ratio=2.0)
    robust=[]
    for use_filtered in [False,True]:
        p=pc.select_by_index(kept) if use_filtered else pc
        try:p.get_oriented_bounding_box(robust=True);robust.append({'filtered':use_filtered,'success':True})
        except RuntimeError as e:robust.append({'filtered':use_filtered,'success':False,'error':str(e)})
    lineage=[]
    for level in range(4):
        lab=nag['nag'][level].numpy();cids=np.unique(lab[idx]);lineage.append({'level':level,'ancestor_ids':cids.tolist(),'whole_group_counts':[int((lab==i).sum()) for i in cids]})
    records.append({'cluster_id':cid,'gaussian_indices':idx.tolist(),'raw_count':len(idx),'post_outlier_count':len(kept),'coordinate_rank':int(np.linalg.matrix_rank(pts.astype(float)-pts.astype(float).mean(0))),'lineage':lineage,'unmodified_upstream_error':original_error,'robust_true_trials':robust})
    np.savez_compressed(OUT/'data'/f'failed_group_{cid}.npz',gaussian_indices=idx,xyz=xyz[idx],xyz_centered=pts,outlier_indices=kept)
# Re-run the exact upstream BFS/judge code using the saved official L2 affinity and neighborhood.
folder=BASE/'05_hierarchical_grouping/data/20261125T002743Z_hierarchy_openseg_rofa'
d=torch.load(folder/'openseg_level_2_adjacency.pt',map_location='cpu')
agent=ns['SAI3D'].__new__(ns['SAI3D']);agent.dis_decay=.5;agent.max_neighbor_distance=2
agent.seg_num=int(d['seg_ids'].max())+1;agent.seg_member_count=torch.bincount(d['seg_ids'].long()).cuda()
direct=d['direct_neighbors'].cuda();n=agent.seg_num
indirect=torch.zeros((2,n,n),dtype=torch.bool,device='cuda');indirect[0]=direct
for i in range(n):indirect[1,i]=indirect[0,indirect[0,i]].sum(0)>0
indirect[1,torch.eye(n,dtype=torch.bool,device='cuda')]=False
indirect[1,indirect[0].clone()]=True
agent.seg_direct_neighbors=direct;agent.seg_indirect_neighbors=indirect
groups=agent.assign_seg_label_torch(d['seg_adj'].cuda(),.7,max_neighbor_distance=2)
saved=torch.load(folder/'openseg_level_2_grouping.pt',map_location='cpu')
checks['upstream_l2_superpoint_assignments_exact']=torch.equal(groups.cpu(),saved['superpoint_group_labels'])
replayed=(groups[d['seg_ids'].long().cuda()]-1).cpu()
checks['upstream_l2_all_gaussian_labels_exact']=torch.equal(replayed,nag['nag'][2])
torch.save({'upstream_replayed_superpoint_groups':groups.cpu(),'upstream_replayed_gaussian_labels':replayed},OUT/'data/upstream_l2_replay.pt')
assert all(checks.values()),checks
report={'status':'verified','open3d_version':o3d.__version__,'checks':checks,'core_methods_ast_identical':method_checks,'failure_groups':records,'source_sha256':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in sources.items()},'cause':'Released hierarchy postprocess merges tiny groups only at the final level, while graph prediction requests L2 and L3 without a degenerate-OBB guard. The same five failures reproduce in untouched upstream OBB code. L2 labels replay exactly from upstream grouping code; no point reordering, label truncation or feature-row mismatch found.','scope':'Proves this failure is an upstream boundary-condition gap triggered by industrial data; does not certify every upstream data assumption or semantic accuracy.'}
save_json('root_cause.json',report);print(json.dumps({'checks':checks,'failure_sizes':[r['raw_count'] for r in records],'status':'verified'}),flush=True)
