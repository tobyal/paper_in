#!/usr/bin/env python3
"""Read-only visualization/evaluation via the official renderer on fixed cameras."""
import argparse,json,pathlib,sys,os
import numpy as np
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--iteration',type=int,required=True);p.add_argument('--output',required=True);p.add_argument('--repo',default='ReLaGS');p.add_argument('--all-test',action='store_true');a=p.parse_args()
sys.path.insert(0,str(ROOT/a.repo));os.chdir(ROOT/a.repo)
import torch
from scene import Scene,GaussianModel
from gaussian_renderer import render
from arguments import PipelineParams
from utils.loss_utils import ssim
from utils.image_utils import psnr
model=pathlib.Path(a.model);model=model if model.is_absolute() else ROOT/model
out=pathlib.Path(a.output);out=out if out.is_absolute() else ROOT/out
for s in ['rgb','gt','depth','normal','alpha','raw']: (out/s).mkdir(parents=True,exist_ok=True)
args=argparse.Namespace(source_path=str(ROOT/'data'),model_path=str(model),images='images',eval=True,resolution=2,white_background=False,data_device='cpu',sh_degree=3)
g=GaussianModel(3)
kw={'load_img':True,'load_sem':False} if a.repo=='ReLaGS' else {}
scene=Scene(args,g,load_iteration=a.iteration,shuffle=False,**kw)
pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda')
refs=json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']
refs=[pathlib.Path(x).stem for x in refs]
views=scene.getTestCameras() if a.all_test else [v for v in scene.getTestCameras()+scene.getTrainCameras() if v.image_name in refs]
records=[]
def png(t,path):
    x=(t.detach().clamp(0,1).cpu().permute(1,2,0).numpy()*255+.5).astype(np.uint8)
    if x.shape[-1]==1:x=x[:,:,0]
    Image.fromarray(x).save(path)
with torch.no_grad():
    for v in views:
        r=render(v,g,pipe,bg);rgb=r['render'].clamp(0,1);gt=v.original_image[:3].cuda()
        rec={'image':v.image_name,'psnr':float(psnr(rgb,gt).mean()),'ssim':float(ssim(rgb,gt))};records.append(rec)
        png(rgb,out/'rgb'/f'{v.image_name}.png');png(gt,out/'gt'/f'{v.image_name}.png')
        if v.image_name in refs:
            dep=r['surf_depth'].cpu().numpy();alpha=r['rend_alpha'].cpu().numpy();normal=r['rend_normal'].cpu().numpy()
            np.savez_compressed(out/'raw'/f'{v.image_name}.npz',depth=dep,alpha=alpha,normal=normal)
            png(r['rend_normal']*.5+.5,out/'normal'/f'{v.image_name}.png');png(r['rend_alpha'],out/'alpha'/f'{v.image_name}.png')
            valid=(alpha[0]>.5)&np.isfinite(dep[0])&(dep[0]>0)
            lo,hi=np.quantile(dep[0][valid],[.02,.98]) if valid.any() else (0,1)
            depth_vis=np.clip((dep[0]-lo)/max(hi-lo,1e-8),0,1);depth_vis[~valid]=0
            from matplotlib import colormaps
            Image.fromarray((colormaps['viridis'](depth_vis)[:,:,:3]*255).astype(np.uint8)).save(out/'depth'/f'{v.image_name}.png')
        print(json.dumps(rec),flush=True)
summary={'views':len(records),'gaussians':len(g.get_xyz),'mean_psnr':float(np.mean([r['psnr'] for r in records])),'mean_ssim':float(np.mean([r['ssim'] for r in records])),'per_view':records,'renderer':a.repo,'resolution':[938,528],'depth_units':'original COLMAP units; not calibrated meters'}
(out/'metrics.json').write_text(json.dumps(summary,indent=2))
sheet=Image.new('RGB',(384*4,244*2),'white');draw=ImageDraw.Draw(sheet)
for i,name in enumerate(refs):
    f=out/'rgb'/f'{name}.png'
    if not f.exists():continue
    with Image.open(f) as im:tile=im.resize((384,216))
    x=i%4*384;y=i//4*244;sheet.paste(tile,(x,y));draw.text((x+5,y+220),name,fill='black')
sheet.save(out/'reference_contact_sheet.jpg',quality=95)
print(json.dumps(summary,indent=2))
