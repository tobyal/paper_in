"""Unmodified native rasterizer, with color overrides for depth moments and membership.

Depth is an opacity-normalized expected camera-space Z, not a surfel depth.
All occlusion/membership passes contain the complete source scene.
"""
import math,numpy as np,torch
from m0.native_3dgs import load_model,subset_model,PIPELINE,MiniCam,getWorld2View2,getProjectionMatrix,render
from m0.native_3dgs import render_rgb
from utils.sh_utils import eval_sh

class Renderer:
 def __init__(self,ctx,model=None):self.ctx=ctx;self.model=model if model is not None else load_model();self.model.active_sh_degree=3
 def camera(self,im,width=None):
  width=width or im['width'];scale=width/im['width'];height=round(im['height']*scale);K=np.array(im['K'],dtype=float);K[0]*=width/im['width'];K[1]*=height/im['height'];fx,fy=K[0,0],K[1,1]
  fovx=2*math.atan(width/(2*fx));fovy=2*math.atan(height/(2*fy));view=torch.tensor(getWorld2View2(np.array(im['world_to_camera_R']).T,np.array(im['world_to_camera_t'])),device='cuda').T
  p=getProjectionMatrix(.01,100.,fovx,fovy);p[0,2]=2*(K[0,2]+.5)/width-1;p[1,2]=2*(K[1,2]+.5)/height-1;p=p.T.cuda()
  return MiniCam(width,height,fovy,fovx,.01,100,view,view@p)
 @torch.inference_mode()
 def pass_colors(self,im,colors,width=None,model=None):return render(self.camera(im,width),model or self.model,PIPELINE,torch.zeros(3,device='cuda'),override_color=colors)['render']
 @torch.inference_mode()
 def rgb(self,im,ids=None,width=None):
  model=self.model if ids is None else subset_model(self.model,ids)
  if ids is not None and len(ids)==0:return np.zeros((round(im['height']*(width or im['width'])/im['width']),width or im['width'],3),np.uint8)
  return (render_rgb(self.camera(im,width),model)['render'].permute(1,2,0).clamp(0,1).cpu().numpy()*255+.5).astype(np.uint8)
 @torch.inference_mode()
 def moments(self,im):
  R=torch.tensor(im['world_to_camera_R'],device='cuda',dtype=torch.float32);t=torch.tensor(im['world_to_camera_t'],device='cuda',dtype=torch.float32);z=self.model.get_xyz@R[2]+t[2]
  # Rasterizer blends arbitrary precomputed channels without RGB clamping.
  out=self.pass_colors(im,torch.stack([z,z*z,torch.ones_like(z)],dim=1)).cpu().numpy();alpha=np.clip(out[2],0,1);depth=out[0]/np.maximum(alpha,1e-8);std=np.sqrt(np.maximum(out[1]/np.maximum(alpha,1e-8)-depth*depth,0));depth[alpha<1e-4]=0;std[alpha<1e-4]=0
  return dict(depth=depth.astype(np.float32),std=std.astype(np.float32),alpha=alpha.astype(np.float32))
 @torch.inference_mode()
 def contribution(self,im,ids,width=None):
  colors=torch.zeros((len(self.model.get_xyz),3),device='cuda');colors[torch.as_tensor(ids,device='cuda',dtype=torch.long)]=1
  return self.pass_colors(im,colors,width)[0].cpu().numpy()
 @torch.inference_mode()
 def highlight(self,im,groups,width=None):
  view=self.camera(im,width);pc=self.model;directions=pc.get_xyz-view.camera_center;directions/=directions.norm(dim=1,keepdim=True)
  colors=torch.clamp_min(eval_sh(pc.active_sh_degree,pc.get_features.transpose(1,2),directions)+.5,0)
  for ids,color in groups:colors[torch.as_tensor(ids,device='cuda',dtype=torch.long)]=torch.tensor(color,device='cuda',dtype=torch.float32)
  return (self.pass_colors(im,colors,width).permute(1,2,0).clamp(0,1).cpu().numpy()*255+.5).astype(np.uint8)
 def virtual(self,center,size,axis='oblique',width=640):
  center=np.asarray(center);dist=max(float(np.max(size)),.1)*2.5;direction={'oblique':[1,-1.5,1.1],'side':[1.5,0,.5],'top':[0,0,2]}[axis];eye=center+np.array(direction)/np.linalg.norm(direction)*dist;f=center-eye;f/=np.linalg.norm(f);up=np.array([0,1,0]) if axis=='top' else np.array([0,0,1]);right=np.cross(f,up);right/=np.linalg.norm(right);up=np.cross(right,f);pose=np.eye(4);pose[:3,:3]=np.stack([right,up,-f],1);pose[:3,3]=eye;raw=np.linalg.inv(np.array(self.ctx.state['scene']['transform']))@pose;R=np.diag([1,-1,-1])@raw[:3,:3].T;t=-R@raw[:3,3];focal=width/(2*np.tan(np.deg2rad(45)/2))
  return dict(image_id='virtual_'+axis,width=width,height=width,K=[[focal,0,width/2],[0,focal,width/2],[0,0,1]],world_to_camera_R=R.tolist(),world_to_camera_t=t.tolist(),center=raw[:3,3].tolist())
