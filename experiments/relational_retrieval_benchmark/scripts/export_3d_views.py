"""Supplementary isolated RGB renders, never used as evaluation masks."""
from common import *
import argparse,torch,copy
p=argparse.ArgumentParser();p.add_argument('--method',choices=['relags','thgs','ours'],required=True);a=p.parse_args();check_frozen()
virtual_file=ROOT/'configs/virtual_display_views.json'
if not virtual_file.exists():
    objects=read(ROOT/'inputs/objects.json');centers=np.array([o['bbox']['center'] for o in objects]);sizes=np.array([o['bbox']['size'] for o in objects]);lo=(centers-np.linalg.norm(sizes,axis=1)[:,None]/2).min(0);hi=(centers+np.linalg.norm(sizes,axis=1)[:,None]/2).max(0);center=(lo+hi)/2;distance=(hi-lo).max()*1.8;T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform']);views=[]
    for name,direction,up in [('oblique',[1,-1.5,1.1],[0,0,1]),('top',[0,0,1],[0,1,0])]:
        eye=center+np.array(direction)/np.linalg.norm(direction)*distance;forward=center-eye;forward/=np.linalg.norm(forward);right=np.cross(forward,up);right/=np.linalg.norm(right);vertical=np.cross(right,forward);pose=np.eye(4);pose[:3,:3]=np.stack([right,vertical,-forward],1);pose[:3,3]=eye;raw=np.linalg.inv(T)@pose;R=np.diag([1,-1,-1])@raw[:3,:3].T;t=-R@raw[:3,3];focal=768/(2*np.tan(np.deg2rad(45)/2))
        views.append(dict(image_id=name,width=768,height=768,K=[[focal,0,384],[0,focal,384],[0,0,1]],world_to_camera_R=R.tolist(),world_to_camera_t=t.tolist(),center=raw[:3,3].tolist()))
    write(virtual_file,dict(cameras=views,selection='Single fixed whole-workshop frame from M0 scene extent; all methods/queries same pose/FOV/scale; visualization only'))
views=read(virtual_file)['cameras']
real=read(ROOT/'configs/evaluation_views.json')['cameras']['frame_000329']
if a.method=='ours':
    from industrial_world_model.render import Renderer
    class Ctx:project=PROJECT;state=read(ROOT/'inputs/m0_state.json')
    renderer=Renderer(Ctx())
    sanity=renderer.rgb(real)
    def images(dest):
        ids=np.load(dest/'gaussian_indices.npy');return [renderer.rgb(c,ids=ids) for c in views]
else:
    source=PROJECT/'ReLaGS' if a.method=='relags' else ROOT/'third_party/THGS';sys.path.insert(0,str(source))
    from gaussian_renderer import render,GaussianModel
    from arguments import PipelineParams
    pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda')
    full=ROOT/'outputs'/a.method/'model/point_cloud'/('iteration_0' if a.method=='relags' else 'iteration_30000')/'point_cloud.ply';g=GaussianModel(3,20);g.load_ply(str(full));g.active_sh_degree=3
    with torch.no_grad():sanity=(render(camera_native(real),g,pipe,bg)['render'].permute(1,2,0).clamp(0,1).cpu().numpy()*255+.5).astype(np.uint8)
    del g
    def images(dest):
        ply=dest/'selected_gaussians.ply'
        if not ply.exists():return [np.zeros((768,768,3),np.uint8) for c in views]
        g=GaussianModel(3,20);g.load_ply(str(ply));g.active_sh_degree=3
        with torch.no_grad():return [(render(camera_native(c),g,pipe,bg)['render'].permute(1,2,0).clamp(0,1).cpu().numpy()*255+.5).astype(np.uint8) for c in views]
save(ROOT/'outputs'/a.method/'camera_sanity/frame_000329_render.jpg',sanity);original=np.array(Image.open(PROJECT/'data/images'/real['filename']).convert('RGB').resize((938,528)));mse=float(np.mean((original.astype(float)-sanity.astype(float))**2));write(ROOT/'outputs'/a.method/'camera_sanity/record.json',dict(camera=real,rgb_psnr=10*np.log10(255**2/max(mse,1e-10)),purpose='Projection alignment diagnostic, not segmentation accuracy'))
for q in read(ROOT/'configs/benchmark_queries.json'):
    dest=ROOT/'outputs'/a.method/q['query_id']
    if not (dest/'gaussian_indices.npy').exists():continue
    for c,im in zip(views,images(dest)):save(dest/('isolated_'+c['image_id']+'.jpg'),im)
    print(a.method,q['query_id'],'3D display',flush=True)
