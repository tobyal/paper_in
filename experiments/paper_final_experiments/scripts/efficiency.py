from common import *
import os,collections
logs=[]
for root in [V1,V2,BENCH]:
    for p in sorted((root/'logs').glob('*/*/result.json')):
        d=read(p)
        if 'seconds' in d:logs.append(dict(experiment=root.name,stage=p.parents[1].name,seconds=d['seconds'],exit_code=d.get('exit_code'),status=d.get('status'),source=str(p),command=d.get('command')))
write(ROOT/'E06_computational_efficiency/historical_runs.json',logs);csvwrite(ROOT/'E06_computational_efficiency/historical_runs.csv',[{k:v for k,v in x.items() if k!='command'} for x in logs])
stage_names=['A_masks','A_mask_scales_final','A_affinity_training','A_final_extraction','A_reference_prompts_visibility','B_category_semantics','C_geometry_and_local_som','A_references','A_initial_extraction','A_refined_extraction','A_prompt_refinement','BC_world_model']
stages=[r for r in logs if r['stage'] in stage_names and r['exit_code']==0];write(ROOT/'E06_computational_efficiency/ours_stage_costs.json',stages)
online=[]
for m in ['langsplat','thgs','relags','ours']:
    d=read(BENCH/'outputs'/m/'summary.json');qs=d['queries'];assert len(qs)==25
    for q in qs:
        assert len(q['views'])==2 and q['timing']['warmup']==1 and q['timing']['repetitions']==3
    row=dict(method=m,queries=25,views_per_query=2,resolution='938x528',warmup=1,repetitions=3,statistic='mean across queries of 3-repeat medians',hardware='NVIDIA RTX A6000 GPU 0',model_load_seconds=d['model_load_seconds'],**{k+'_seconds':float(np.mean([q['timing'][k]['median_seconds'] for q in qs])) for k in ['query','render','end_to_end']},source=str(BENCH/'outputs'/m/'summary.json'))
    online.append(row)
write(ROOT/'E06_computational_efficiency/online.json',online);csvwrite(ROOT/'E06_computational_efficiency/online.csv',online)
storage=[]
for label,p in [('native_3dgs',PROJECT/read(V2/'inputs/manifest.json')['ply']),('saga_shared_checkpoint',V1/'outputs/A/saga_model/point_cloud/iteration_10000/contrastive_feature_point_cloud.ply'),('saga_scale_gate',V1/'outputs/A/saga_model/point_cloud/iteration_10000/scale_gate.pt'),('category_prototypes',V2/'world_model/category_features.npz'),('relation_graph',V2/'world_model/scene_graph.json'),('clip_weights',PROJECT/'models/openclip_vit_b16/open_clip_pytorch_model.bin')]:storage.append(dict(asset=label,bytes=p.stat().st_size,MiB=p.stat().st_size/(1<<20),source=str(p)))
for label,glob in [('all33_gaussian_ids','*/gaussian_indices.npy'),('all33_independent_ply','*/object.ply')]:
    paths=list((V2/'outputs/A/extractions/refined/objects').glob(glob));size=sum(p.stat().st_size for p in paths);storage.append(dict(asset=label,bytes=size,MiB=size/(1<<20),files=len(paths),source=str(V2/'outputs/A/extractions/refined/objects')))
write(ROOT/'E06_computational_efficiency/storage.json',storage);csvwrite(ROOT/'E06_computational_efficiency/storage.csv',storage)
write(ROOT/'E06_computational_efficiency/protocol.json',dict(online='Reuse prior sequential same-GPU benchmark with CUDA synchronization and identical 2-view output. No new timing required.',io_excluded=True,model_loading_excluded=True,lang_query_includes='text, 2-view AE decoding, response and mask postprocessing',ours_query='known-category alias matching, relation filtering and Gaussian-ID file reading; no online CLIP encoding',offline_comparable_total=False,reason='Historical stages differ in reuse, environments, failed retries and feature caches; not an equal-data end-to-end construction benchmark.',m0_manual_cost='not recorded; separately acknowledged',saga_training_seconds=next(r['seconds'] for r in logs if r['stage']=='A_affinity_training' and r['exit_code']==0),reuse_scope='same scene, v1 10 extracted (9 usable), v2 33 extracted (30 fine/partial usable), same iteration_10000, no further training',bc_separate_cost='v2 B/C combined stage only; separate original v1 semantic/graph logs retained; do not split combined wall time artificially'))
print('Efficiency',len(logs),'historical run records, online conditions verified',flush=True)
