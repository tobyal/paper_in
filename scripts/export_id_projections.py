#!/usr/bin/env python3
"""Read-only hard label maps using the official maximum-contribution ID renderer."""
import argparse,json,pathlib,os,sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'ReLaGS'));os.chdir(ROOT/'ReLaGS')
import torch
from scene import Scene,GaussianModel
from gaussian_renderer import render_2d_with_ids
from arguments import PipelineParams
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--labels',required=True);p.add_argument('--output',required=True);a=p.parse_args()
out=pathlib.Path(a.output);data=out/'data/id_projections';vis=out/'visualizations/id_projections';data.mkdir(parents=True,exist_ok=True);vis.mkdir(parents=True,exist_ok=True)
raw=torch.load(a.labels,map_location='cpu');labels=raw['nag'] if isinstance(raw,dict) else [raw];labels=[x.cpu().numpy().reshape(-1).astype(np.int32) for x in labels]
args=argparse.Namespace(source_path=str(ROOT/'data'),model_path=a.model,images='images',eval=True,resolution=2,white_background=False,data_device='cpu',sh_degree=3)
g=GaussianModel(3);scene=Scene(args,g,load_iteration=0,shuffle=False,load_img=True,load_sem=False);pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda')
refs=[pathlib.Path(x).stem for x in json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']];views=[v for v in scene.getTestCameras()+scene.getTrainCameras() if v.image_name in refs]
palettes=[np.random.default_rng(3107).integers(40,256,size=(max(int(x.max()+1),1),3),dtype=np.uint8) for x in labels];records=[]
with torch.no_grad():
    for view in views:
        r=render_2d_with_ids(view,g,pipe,bg,None);ids=r['impact_id'].squeeze(0).cpu().numpy().astype(np.int32);valid=ids>=0;assert ids[valid].max()<len(g.get_xyz)
        maps={f'level_{i}':np.where(valid,lab[np.maximum(ids,0)],-1) for i,lab in enumerate(labels)}
        np.savez_compressed(data/f'{view.image_name}.npz',gaussian_id=ids,**maps)
        gt=(view.original_image[:3].permute(1,2,0).numpy().clip(0,1)*255).astype(np.uint8)
        for i,lab in enumerate(labels):
            pix=maps[f'level_{i}'];color=palettes[i][np.maximum(pix,0)];color[~valid]=0
            Image.fromarray(color).save(vis/f'{view.image_name}_level_{i}_labels.png')
            Image.fromarray((gt*.25+color*.75).astype(np.uint8)).save(vis/f'{view.image_name}_level_{i}_overlay.png')
        records.append({'image':view.image_name,'mapped_pixels':int(valid.sum()),'unmapped_pixels':int((~valid).sum()),'visible_groups_per_level':[int(len(np.unique(x[valid]))) for x in maps.values()]})
for i in range(len(labels)):
    sheet=Image.new('RGB',(1536,488),'white');draw=ImageDraw.Draw(sheet)
    for j,name in enumerate(refs):
        with Image.open(vis/f'{name}_level_{i}_labels.png') as im:sheet.paste(im.resize((384,216)),(j%4*384,j//4*244))
        draw.text((j%4*384+5,j//4*244+220),f'{name} | level {i}',fill='black')
    sheet.save(vis/f'level_{i}_contact.jpg',quality=95)
(out/'metrics/id_projection_summary.json').write_text(json.dumps({'renderer':'official gaussian_renderer.render_2d_with_ids','definition':'Cluster label of the maximum alpha-contribution Gaussian per pixel, background -1; diagnostic export only, not fed into grouping or query selection','per_view':records},indent=2));print(json.dumps(records,indent=2))
