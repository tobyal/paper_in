from common import *
import collections
split=read(ROOT/'inputs/camera_split.json');test={Path(p).stem for p in split['test']};train={Path(p).stem for p in split['train']};cameras=read(V2/'inputs/training_cameras.json');real=[c for c in cameras if c.get('source_type')=='real'];virtual=[c for c in cameras if c.get('source_type')!='real'];assert all(c['split']=='train' for c in cameras);assert not {c['image_id'] for c in real}&test
relags_train=[c['image_id'] for c in sorted(read(ROOT/'inputs/cameras.json'),key=lambda c:c['filename']) if c['split']=='train'];assert set(relags_train)==train
evidence={}
for stage in ['01_gaussian_scene','05_hierarchical_grouping','06_semantic_aggregation']:
    cfg=PROJECT/'outputs/relags_baseline'/stage/'data/model/cfg_args';content=cfg.read_text();assert 'eval=True' in content;evidence[stage]=dict(config_path=str(cfg),config=content)
result=dict(shared_original_train=306,shared_original_heldout=44,ours_affinity_training_cameras=len(cameras),ours_training_real=len(real),ours_training_virtual=len(virtual),ours_heldout_overlap=sorted({c['image_id'] for c in real}&test),ours_all_split_train=True,relags_config_evidence=evidence,relags_semantics_evidence='merge_proj.py uses getTrainCameras(); Stage05/06 logs report views num:306. Sorted COLMAP holdout every 8 frames matches shared split.',thgs_scene='306 train-only images/COLMAP; existing LangSplat features; no heldout images supplied',langsplat='Original 306/44 record checked by initialize.py',ours_extra_information='Frozen SAGA affinity uses selected real and native full-scene virtual training observations plus M0 priors. Not equal data/priors to external methods.')
write(ROOT/'inputs/split_usage_audit.json',result);print(result)
