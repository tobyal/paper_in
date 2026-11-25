#!/usr/bin/env python3
"""ROFA retention diagnostics from saved official decisions, with the fixed cameras."""
import argparse,json,pathlib,os,sys
import numpy as np
from PIL import Image
from plyfile import PlyData,PlyElement
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/relags_baseline/06_semantic_aggregation'
sys.path.insert(0,str(ROOT/'ReLaGS'));os.chdir(ROOT/'ReLaGS')
import torch
from scene import Scene,GaussianModel
from gaussian_renderer import render
from arguments import PipelineParams
p=argparse.ArgumentParser();p.add_argument('--model',required=True);a=p.parse_args()
args=argparse.Namespace(source_path=str(ROOT/'data'),model_path=a.model,images='images',eval=True,resolution=2,white_background=False,data_device='cpu',sh_degree=3)
g=GaussianModel(3);scene=Scene(args,g,load_iteration=0,shuffle=False,load_img=False,load_sem=False);xyz=g.get_xyz.detach().cpu().numpy()
pipe=PipelineParams(argparse.ArgumentParser());bg=torch.zeros(3,device='cuda');refs=[pathlib.Path(x).stem for x in json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']]
views=[v for v in scene.getTestCameras()+scene.getTrainCameras() if v.image_name in refs];summary=[]
for vlm in ['clip','openseg']:
    source=sorted((OUT/'data').glob(f'*/{vlm}_level_3_raw_observations.pt'))[-1].parent
    for level in [1,2,3]:
        raw=torch.load(source/f'{vlm}_level_{level}_raw_observations.pt',map_location='cpu');rofa=torch.load(source/f'{vlm}_level_{level}_rofa.pt',map_location='cpu')
        counts=np.array([len(x) for x in raw['features']]);kept=np.zeros(len(counts),np.int64)
        for d in rofa['decisions']:kept[d['cluster']]=int(d['keep_mask'].sum())
        ratio=kept/np.maximum(counts,1);lab=raw['gaussian_to_cluster'].cpu().numpy().reshape(-1);colors=plt.colormaps['viridis'](ratio[lab])[:,:3];colors[counts[lab]==0]=[1,0,1]
        target=OUT/'visualizations'/f'{vlm}_level_{level}';target.mkdir(parents=True,exist_ok=True)
        np.savez_compressed(OUT/'data'/f'{vlm}_level_{level}_retention.npz',gaussian_to_cluster=lab,observations=counts,retained=kept,retained_fraction=ratio)
        v=np.empty(len(xyz),dtype=[('x','f4'),('y','f4'),('z','f4'),('red','u1'),('green','u1'),('blue','u1')])
        for j,n in enumerate(['x','y','z']):v[n]=xyz[:,j]
        for j,n in enumerate(['red','green','blue']):v[n]=(colors[:,j]*255).astype(np.uint8)
        PlyData([PlyElement.describe(v,'vertex')]).write(target/'retained_observation_fraction.ply')
        with torch.no_grad():
            c=torch.from_numpy(colors.astype(np.float32)).cuda()
            for camera in views:
                rgb=render(camera,g,pipe,bg,override_color=c)['render'].clamp(0,1)
                Image.fromarray((rgb.permute(1,2,0).cpu().numpy()*255+.5).astype(np.uint8)).save(target/f'{camera.image_name}.png')
        fig,axs=plt.subplots(1,2,figsize=(10,4));axs[0].hist(counts,bins=40);axs[0].set(xlabel='Views with observations',ylabel='Cluster count');axs[1].hist(ratio[counts>0],bins=40,range=(0,1));axs[1].set(xlabel='ROFA retained fraction',ylabel='Cluster count');fig.tight_layout();fig.savefig(target/'retention_histograms.png',dpi=160);plt.close(fig)
        summary.append({'vlm':vlm,'level':level,'clusters':len(counts),'empty_clusters':int((counts==0).sum()),'observations':int(counts.sum()),'retained':int(kept.sum()),'rejected':int((counts-kept).sum()),'observations_quantiles':np.quantile(counts,[0,.25,.5,.75,.95,1]).tolist(),'color_key':'viridis 0..1 retention; magenta = no observations'})
(OUT/'metrics/rofa_summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
