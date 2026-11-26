"""Portable native 3DGS projection using the bundled official SAGA RGB renderer."""
import sys,math
from pathlib import Path
import numpy as np,torch

class Renderer:
    def __init__(self,model_root):
        self.root=Path(model_root);sys.path.insert(0,str(self.root/'vendor/SegAnyGAussians'))
        from scene.gaussian_model import GaussianModel
        from gaussian_renderer import render
        from argparse import Namespace
        self.GaussianModel=GaussianModel;self.render=render;self.pipe=Namespace(debug=False,compute_cov3D_python=False,convert_SHs_python=False);self.model=GaussianModel(3);self.model.load_ply(str(self.root/'scene/scene.ply'));self.model.active_sh_degree=3
    def camera(self,c):
        from scene.cameras import MiniCam
        from utils.graphics_utils import getWorld2View2,getProjectionMatrix
        w,h=c['width'],c['height'];K=np.asarray(c['K']);fovx=2*math.atan(w/(2*K[0,0]));fovy=2*math.atan(h/(2*K[1,1]));view=torch.tensor(getWorld2View2(np.asarray(c['world_to_camera_R']).T,np.asarray(c['world_to_camera_t'])),device='cuda').T;p=getProjectionMatrix(.01,100,fovx,fovy);p[0,2]=2*(K[0,2]+.5)/w-1;p[1,2]=2*(K[1,2]+.5)/h-1;p=p.T.cuda();return MiniCam(w,h,fovy,fovx,.01,100,view,view@p)
    @torch.inference_mode()
    def contribution(self,c,ids):
        colors=torch.zeros((len(self.model.get_xyz),3),device='cuda');colors[torch.as_tensor(ids,device='cuda',dtype=torch.long)]=1
        return self.render(self.camera(c),self.model,self.pipe,torch.zeros(3,device='cuda'),override_color=colors)['render'][0].cpu().numpy()
    @torch.inference_mode()
    def rgb(self,c):return (self.render(self.camera(c),self.model,self.pipe,torch.zeros(3,device='cuda'))['render'].permute(1,2,0).clamp(0,1).cpu().numpy()*255+.5).astype(np.uint8)

if __name__=='__main__':
    import json,argparse
    from PIL import Image
    p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--camera',required=True);p.add_argument('--indices',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();c=next(c for c in json.loads((a.model/'cameras.json').read_text()) if c['image_id']==a.camera);r=Renderer(a.model);m=r.contribution(c,np.load(a.indices));a.output.mkdir(parents=True,exist_ok=True);np.save(a.output/'contribution.npy',m);Image.fromarray((m>.5).astype(np.uint8)*255).save(a.output/'mask.png');Image.fromarray(r.rgb(c)).save(a.output/'scene_render.jpg')
