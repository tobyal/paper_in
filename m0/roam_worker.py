"""Arbitrary-view official 2DGS rendering; no semantic inference or source writes."""
import argparse
import base64
import contextlib
import io
import json
import math
import sys
import time
import traceback
import numpy as np
from PIL import Image
from .settings import PROJECT,ROOT,GAUSSIANS


def main():
    out=sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        sys.path.insert(0,str(PROJECT/'ReLaGS'))
        import torch
        from scene import GaussianModel
        from scene.cameras import Camera
        from gaussian_renderer import render
        from arguments import PipelineParams
        base=GaussianModel(3);base.load_ply(str(GAUSSIANS));base.active_sh_degree=3
        # Native RGB rasterizer requires a CUDA semantics buffer, even for geometry-only views.
        # Supply zeros explicitly; no inherited semantic features enter M0.
        base._semantics=torch.zeros((len(base.get_xyz),base.embedding_dim),device='cuda')
        pipeline=PipelineParams(argparse.ArgumentParser());background=torch.zeros(3,device='cuda')
        subset=None;subset_key=None
    for line in sys.stdin:
        try:
            with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
                request=json.loads(line);start=time.perf_counter();scene=request['scene']
                # Three camera: right/up/back. Official camera: right/down/forward.
                pose=np.linalg.inv(scene['transform'])@np.asarray(request['camera_world'])
                rotation=np.diag([1.,-1.,-1.])@pose[:3,:3].T;translation=-rotation@pose[:3,3]
                w,h=request['width'],request['height'];fy=math.radians(request['fov']);fx=2*math.atan(math.tan(fy/2)*w/h)
                camera=Camera(colmap_id=0,R=rotation.T,T=translation,FoVx=fx,FoVy=fy,image=None,gt_alpha_mask=None,
                    image_name='m0_roam',uid=0,width=w,height=h,data_device='cpu')
                model=base
                if not request.get('show_outside',False) and scene.get('artifacts',{}).get('scene_gaussian_indices.npy'):
                    key=scene['artifacts']['scene_gaussian_indices.npy']
                    if key!=subset_key:
                        ids=torch.as_tensor(np.load(ROOT/key).astype('int64'),device='cuda')
                        subset=GaussianModel(3);subset.active_sh_degree=3
                        for name in ('_xyz','_features_dc','_features_rest','_opacity','_scaling','_rotation','_semantics'):
                            setattr(subset,name,getattr(base,name)[ids])
                        subset_key=key
                    model=subset
                result=render(camera,model,pipeline,background)
                pixels=(result['render'].clamp(0,1).permute(1,2,0).cpu().numpy()*255+.5).astype('uint8')
                buffer=io.BytesIO();Image.fromarray(pixels).save(buffer,format='JPEG',quality=90)
                response=dict(jpeg=base64.b64encode(buffer.getvalue()).decode(),seconds=time.perf_counter()-start,
                    gaussians=len(model.get_xyz),gpu_bytes=torch.cuda.memory_allocated())
        except Exception as e:
            traceback.print_exc(file=sys.stderr);response=dict(error=str(e))
        out.write(json.dumps(response)+'\n');out.flush()


if __name__=='__main__':main()
