#!/usr/bin/env python3
import json,pathlib
import numpy as np
from PIL import Image,ImageDraw
import torch
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[1];BASE=ROOT/'outputs/relags_baseline'
before=BASE/'01_gaussian_scene/visualizations/reconstruction';stage=BASE/'03_gaussian_pruning';after=stage/'visualizations/pruned';out=stage/'visualizations/comparison';out.mkdir(parents=True,exist_ok=True)
audit=pathlib.Path(json.loads((stage/'data/audit_latest.json').read_text())['directory']);raw=torch.load(audit/'max_contribution_and_indices.pt',map_location='cpu')
keep=raw['keep_mask'].numpy().reshape(-1);weights=raw['max_contribution'].numpy().reshape(-1)
refs=json.loads((ROOT/'configs/reference_views.json').read_text())['image_names'];records=[]
for p in sorted((before/'rgb').glob('*.png')):
    b=np.asarray(Image.open(p).convert('RGB'),dtype=np.float32)/255;a=np.asarray(Image.open(after/'rgb'/p.name).convert('RGB'),dtype=np.float32)/255
    diff=np.abs(a-b);records.append({'image':p.stem,'mean_abs_rgb_delta':float(diff.mean()),'max_abs_rgb_delta':float(diff.max()),'fraction_pixels_max_channel_delta_above_0_05':float((diff.max(2)>.05).mean())})
    np.savez_compressed(out/f'{p.stem}_delta.npz',absolute_rgb_delta=diff.astype(np.float16))
    if p.stem+'.jpg' in refs:
        sheet=Image.new('RGB',(b.shape[1]*3,b.shape[0]+25),'white');draw=ImageDraw.Draw(sheet)
        for i,(im,title) in enumerate([(b,'Before MWP'),(a,'After MWP'),(np.minimum(diff*5,1),'Absolute delta x5')]):
            sheet.paste(Image.fromarray((im*255+.5).astype(np.uint8)),(i*b.shape[1],0));draw.text((i*b.shape[1]+5,b.shape[0]+5),title,fill='black')
        sheet.save(out/f'{p.stem}.jpg',quality=95)
bm=json.loads((before/'metrics.json').read_text());am=json.loads((after/'metrics.json').read_text())
summary={'gaussians_before':len(keep),'kept':int(keep.sum()),'removed':int((~keep).sum()),'removed_fraction':float((~keep).mean()),'threshold':raw['threshold'],'contribution_quantiles':np.quantile(weights,[0,.01,.25,.5,.75,.95,.99,1]).tolist(),'before_psnr':bm['mean_psnr'],'after_psnr':am['mean_psnr'],'psnr_delta':am['mean_psnr']-bm['mean_psnr'],'before_ssim':bm['mean_ssim'],'after_ssim':am['mean_ssim'],'per_view':records,'limitation':'RGB differences and reconstruction metrics do not establish preservation of individual thin equipment structures; inspect paired views and removed Gaussian PLY.'}
(stage/'metrics/pruning_comparison.json').write_text(json.dumps(summary,indent=2))
fig,ax=plt.subplots(figsize=(8,4));ax.hist(np.log10(np.maximum(weights,1e-12)),bins=100);ax.axvline(np.log10(raw['threshold']),color='red');ax.set(xlabel='log10 maximum contribution',ylabel='Gaussian count');fig.tight_layout();fig.savefig(out/'contribution_histogram.png',dpi=160);plt.close(fig)
print(json.dumps({k:v for k,v in summary.items() if k!='per_view'},indent=2))
