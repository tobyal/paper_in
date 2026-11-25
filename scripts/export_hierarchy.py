#!/usr/bin/env python3
"""Read-only exports of actual official labels; no relabeling or semantic correction."""
import argparse,json,pathlib,sys,os
import numpy as np
from PIL import Image,ImageDraw
from plyfile import PlyData,PlyElement
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--model',required=True);p.add_argument('--labels',required=True);p.add_argument('--output',required=True);p.add_argument('--iteration',type=int,default=0);a=p.parse_args()
sys.path.insert(0,str(ROOT/'ReLaGS'));os.chdir(ROOT/'ReLaGS')
import torch
from scene import Scene,GaussianModel
from gaussian_renderer import render
from arguments import PipelineParams
model=pathlib.Path(a.model);output=pathlib.Path(a.output)
for d in ['data','visualizations','metrics']:(output/d).mkdir(parents=True,exist_ok=True)
raw=torch.load(a.labels,map_location='cpu')
labels=raw['nag'] if isinstance(raw,dict) else [raw]
labels=[x.detach().cpu().numpy().astype(np.int64).reshape(-1) for x in labels]
np.savez_compressed(output/'data/hierarchy_labels.npz',**{f'level_{i}':x for i,x in enumerate(labels)})
args=argparse.Namespace(source_path=str(ROOT/'data'),model_path=str(model),images='images',eval=True,resolution=2,white_background=False,data_device='cpu',sh_degree=3)
g=GaussianModel(3);scene=Scene(args,g,load_iteration=a.iteration,shuffle=False,load_img=True,load_sem=False)
xyz=g.get_xyz.detach().cpu().numpy();assert all(len(x)==len(xyz) for x in labels)
pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda')
refs=[pathlib.Path(x).stem for x in json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']]
views=[v for v in scene.getTestCameras()+scene.getTrainCameras() if v.image_name in refs]
catalog=[];stats=[]
for level,lab in enumerate(labels):
    unique,counts=np.unique(lab,return_counts=True);rng=np.random.default_rng(3107)
    palette=rng.integers(40,256,size=(int(max(lab.max()+1,1)),3),dtype=np.uint8)
    colors=palette[np.maximum(lab,0)];colors[lab<0]=0
    verts=np.empty(len(xyz),dtype=[('x','f4'),('y','f4'),('z','f4'),('red','u1'),('green','u1'),('blue','u1'),('cluster_id','i4')])
    for j,n in enumerate(['x','y','z']):verts[n]=xyz[:,j]
    for j,n in enumerate(['red','green','blue']):verts[n]=colors[:,j]
    verts['cluster_id']=lab
    PlyData([PlyElement.describe(verts,'vertex')]).write(output/'visualizations'/f'level_{level}_colored_points.ply')
    parent_conflicts=0
    for cid,count in zip(unique,counts):
        mask=lab==cid;pts=xyz[mask];rec={'level':level,'id':int(cid),'gaussians':int(count),'center':pts.mean(0).tolist(),'bbox_min':pts.min(0).tolist(),'bbox_max':pts.max(0).tolist()}
        if level+1<len(labels):
            parents=np.unique(labels[level+1][mask]);rec['parent_ids']=parents.tolist();parent_conflicts+=int(len(parents)!=1)
        catalog.append(rec)
    stat={'level':level,'clusters':len(unique),'gaussians':len(lab),'cluster_size_quantiles':np.quantile(counts,[0,.25,.5,.75,.95,1]).tolist(),'clusters_under_20':int((counts<20).sum()),'clusters_under_300':int((counts<300).sum()),'non_unique_parent_count':parent_conflicts}
    if isinstance(raw,dict) and level>0:
        f=raw['nag_feat'][level-1].float().cpu();stat.update(feature_shape=list(f.shape),finite=bool(torch.isfinite(f).all()),zero_features=int((f.norm(dim=1)==0).sum()))
    stats.append(stat);print(json.dumps(stat),flush=True)
    folder=output/'visualizations'/f'level_{level}';folder.mkdir(exist_ok=True)
    c=torch.from_numpy(colors.astype(np.float32)/255).cuda()
    with torch.no_grad():
        for v in views:
            rgb=render(v,g,pipe,bg,override_color=c)['render'].clamp(0,1)
            Image.fromarray((rgb.permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8)).save(folder/f'{v.image_name}.png')
    sheet=Image.new('RGB',(1536,488),'white');draw=ImageDraw.Draw(sheet)
    for i,name in enumerate(refs):
        with Image.open(folder/f'{name}.png') as im:sheet.paste(im.resize((384,216)),(i%4*384,i//4*244))
        draw.text((i%4*384+5,i//4*244+220),f'{name} | level {level}',fill='black')
    sheet.save(output/'visualizations'/f'level_{level}_contact.jpg',quality=95)
(output/'data/cluster_catalog.json').write_text(json.dumps({'source':a.labels,'coordinates':'Original COLMAP frame, unknown metric scale and gravity','clusters':catalog},indent=2))
(output/'metrics/hierarchy_statistics.json').write_text(json.dumps({'levels':stats,'view_count':len(views),'visualization':'Gaussian colors are deterministic cluster colors; alpha compositing may blend colors at boundaries','semantic_accuracy':'No ground-truth annotation; cluster counts are diagnostics, not accuracy'},indent=2))
