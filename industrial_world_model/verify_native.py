"""CUDA integration check of exact K and full-scene occlusion semantics."""
import argparse
from types import SimpleNamespace
import numpy as np
import torch
from .common import Context,write,project


def run(ctx):
    from m0.native_3dgs import GaussianModel
    from .render import Renderer
    model=GaussianModel(3);model.active_sh_degree=3
    arrays={'_xyz':[[0,0,3.],[0,0,3.6]],'_scaling':np.full((2,3),np.log(.005)),
            '_rotation':[[1,0,0,0],[1,0,0,0]],'_opacity':[[20.],[20.]],
            '_features_dc':np.zeros((2,1,3)),'_features_rest':np.zeros((2,15,3))}
    for name,value in arrays.items():setattr(model,name,torch.nn.Parameter(torch.tensor(value,device='cuda',dtype=torch.float32),requires_grad=False))
    im=dict(image_id='synthetic_offcenter_K',width=320,height=240,K=[[220,0,117],[0,200,83],[0,0,1]],world_to_camera_R=np.eye(3).tolist(),world_to_camera_t=[0,0,0])
    renderer=Renderer(SimpleNamespace(state={'scene':{'transform':np.eye(4).tolist()}}),model=model)
    moments=renderer.moments(im);peak=np.unravel_index(moments['alpha'].argmax(),moments['alpha'].shape)
    uv,z=project(np.array(arrays['_xyz']),im);assert peak==(83,117),(peak,uv)
    folder=ctx.out/'verification';folder.mkdir(exist_ok=True);np.savez_compressed(folder/'synthetic_offcenter_K.npz',**moments)
    fake=SimpleNamespace(xyz=np.array(arrays['_xyz']),scales=np.full(2,.005),c=ctx.c,path=lambda *args:folder/'synthetic_offcenter_K.npz')
    local,pixels,weights=Context.visibility(fake,np.array([0,1]),im)
    assert local.tolist()==[0],f'Front center should be visible, back center occluded: {local}'
    result=dict(passed=True,projected_center=uv.tolist(),raster_peak_yx=list(map(int,peak)),front_depth=3.,back_depth=3.6,
                composed_depth=float(moments['depth'][peak]),composed_std=float(moments['std'][peak]),alpha=float(moments['alpha'][peak]),
                visible_local_ids=local.tolist(),occluded_back_excluded_from_votes=True,full_two_gaussian_scene=True)
    write(folder/'native_projection_occlusion.json',result);return result


if __name__=='__main__':
    import os
    p=argparse.ArgumentParser();p.add_argument('--config',default='configs/industrial_world_model.json');a=p.parse_args();ctx=Context(a.config);os.environ['CUDA_VISIBLE_DEVICES']=str(ctx.c['gpu']);print(run(ctx))
