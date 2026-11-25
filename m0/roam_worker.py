"""Arbitrary-view native 3DGS rendering; no semantic inference or source writes."""
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
from .settings import ROOT


def main():
    out=sys.stdout
    with contextlib.redirect_stdout(sys.stderr):
        import torch
        from .native_3dgs import load_model,subset_model,camera,render_rgb
        base=load_model()
        subset=None;subset_key=None
    for line in sys.stdin:
        try:
            with contextlib.redirect_stdout(sys.stderr),torch.inference_mode():
                request=json.loads(line);start=time.perf_counter();scene=request['scene']
                # Three camera: right/up/back. Official camera: right/down/forward.
                pose=np.linalg.inv(scene['transform'])@np.asarray(request['camera_world'])
                rotation=np.diag([1.,-1.,-1.])@pose[:3,:3].T;translation=-rotation@pose[:3,3]
                w,h=request['width'],request['height'];fy=math.radians(request['fov']);fx=2*math.atan(math.tan(fy/2)*w/h)
                view=camera(w,h,rotation,translation,fx,fy)
                model=base
                if not request.get('show_outside',False) and scene.get('artifacts',{}).get('scene_gaussian_indices.npy'):
                    key=scene['artifacts']['scene_gaussian_indices.npy']
                    if key!=subset_key:
                        subset=subset_model(base,np.load(ROOT/key))
                        subset_key=key
                    model=subset
                result=render_rgb(view,model)
                pixels=(result['render'].clamp(0,1).permute(1,2,0).cpu().numpy()*255+.5).astype('uint8')
                buffer=io.BytesIO();Image.fromarray(pixels).save(buffer,format='JPEG',quality=90)
                response=dict(jpeg=base64.b64encode(buffer.getvalue()).decode(),seconds=time.perf_counter()-start,
                    gaussians=len(model.get_xyz),gpu_bytes=torch.cuda.memory_allocated())
        except Exception as e:
            traceback.print_exc(file=sys.stderr);response=dict(error=str(e))
        out.write(json.dumps(response)+'\n');out.flush()


if __name__=='__main__':main()
