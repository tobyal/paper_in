"""SAGA instrumentation: exact KNN cache, checkpoints and loss logs only."""
import json,os,random,time
from pathlib import Path
import numpy as np,torch
ROOT=Path(__file__).resolve().parents[1]
_start=None

def initialize(model,gate,scene,opt,all_scales):
    global _start
    _start=time.time();folder=Path(scene.model_path);xyz=np.load(ROOT/'inputs/geometry/xyz_raw.npy',mmap_mode='r')
    assert np.array_equal(model.get_xyz.detach().cpu().numpy(),xyz),'Original Gaussian row order changed'
    knn=np.load(ROOT/'inputs/geometry/knn_16.npy');assert knn.shape==(len(xyz),opt.smooth_K)
    model.feature_smooth_map={'K':opt.smooth_K,'m':torch.from_numpy(knn.astype(np.int64)).cuda()}
    # Geometry is already excluded from the official feature optimizer. Avoid retaining unused gradients.
    for name in ['_xyz','_scaling','_rotation','_opacity']:getattr(model,name).requires_grad_(False)
    import pytorch3d.ops
    chosen=np.linspace(0,len(xyz)-1,64).astype(int);points=model.get_xyz
    official=pytorch3d.ops.knn_points(points[chosen][None],points[None],K=opt.smooth_K).dists[0].cpu().numpy()
    actual=((xyz[knn[chosen]]-xyz[chosen,None])**2).sum(-1);error=float(np.max(abs(np.sort(official,1)-np.sort(actual,1))));assert error<1e-5
    np.save(folder/'all_mask_scales.npy',all_scales.detach().cpu().numpy())
    (folder/'training_contract.json').write_text(json.dumps(dict(gaussian_count=len(xyz),geometry_frozen=True,original_row_order_exact=True,knn_squared_distance_max_error=error,loss_source='Official SAGA v2 train_contrastive_feature.py',official_random_seed=0),indent=2))
    return error

def record(iteration,model,gate,scene,opt,loss,pos,neg,norm,viewpoint_stack):
    assert bool(torch.isfinite(loss)),'Nonfinite official contrastive loss'
    folder=Path(scene.model_path)
    if iteration%10==0:
        with (folder/'training_metrics.csv').open('a') as f:
            if f.tell()==0:f.write('iteration,loss,positive_cosine,negative_cosine,feature_norm,elapsed_seconds,peak_allocated_bytes\n')
            f.write(','.join(map(str,[iteration,float(loss),float(pos),float(neg),float(norm),time.time()-_start,torch.cuda.max_memory_allocated()]))+'\n')
    wanted=json.loads((ROOT/'configs/experiment.json').read_text())['checkpoints']
    if iteration in wanted:
        scene.save_feature(iteration,target='contrastive_feature',smooth_type='traditional',smooth_K=opt.smooth_K)
        dest=folder/f'point_cloud/iteration_{iteration}';torch.save(gate.state_dict(),dest/'scale_gate.pt')
        torch.save(dict(iteration=iteration,point_features=model._point_features.detach().cpu(),optimizer=model.optimizer.state_dict(),scale_gate=gate.state_dict(),torch_rng=torch.get_rng_state(),cuda_rng=torch.cuda.get_rng_state(),numpy_rng=np.random.get_state(),python_rng=random.getstate(),remaining_cameras=[c.image_name for c in viewpoint_stack]),dest/'training_state.pt')
        print('SAGA_CHECKPOINT',iteration,str(dest),flush=True)

def restore(model,gate,scene):
    checkpoint=os.environ.get('SAGA_RESUME_CHECKPOINT')
    if not checkpoint:return 1,None
    state=torch.load(checkpoint,map_location='cuda');model._point_features.data.copy_(state['point_features']);model.optimizer.load_state_dict(state['optimizer']);gate.load_state_dict(state['scale_gate'])
    torch.set_rng_state(state['torch_rng'].cpu());torch.cuda.set_rng_state(state['cuda_rng'].cpu());np.random.set_state(state['numpy_rng']);random.setstate(state['python_rng'])
    cameras={c.image_name:c for c in scene.getTrainCameras()};stack=[cameras[name] for name in state['remaining_cameras']]
    return state['iteration']+1,stack
