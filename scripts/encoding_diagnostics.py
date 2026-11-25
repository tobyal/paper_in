#!/usr/bin/env python3
"""Measure absent masks before/after the official resize; feature PCA is visualization only."""
import argparse,json,pathlib
import numpy as np
from PIL import Image,ImageDraw
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/relags_baseline/02_image_encoding'
p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args()
rows=[];refs=[pathlib.Path(x).stem for x in json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']]
for p in sorted((OUT/'data/openseg_dense').glob('*_mask_pixel_counts.npy')):
    name=p.name.split('_mask_pixel')[0];small=np.load(p);masks=np.load(OUT/'data/language_features'/f'{name}_s.npy',mmap_mode='r')
    keys,counts=np.unique(masks,return_counts=True);valid=keys>=0;original_counts=np.zeros(len(small),np.int64);original_counts[keys[valid].astype(int)]=counts[valid];original=original_counts>0;lost=(small==0)&original
    rows.append({'image':name,'masks':len(small),'already_absent_in_sam_map':int((~original).sum()),'additional_lost_after_half_resolution':int(lost.sum()),'lost_ids':np.where(lost)[0].tolist(),'lost_original_pixel_counts':original_counts[lost].tolist()})
    if name not in refs:continue
    lost_pixels=np.isin(masks,np.where(lost)[0]).any(0)
    im=np.asarray(Image.open(ROOT/'data/images'/f'{name}.jpg').convert('RGB')).copy();im[lost_pixels]=[255,0,0]
    Image.fromarray(im).save(OUT/'visualizations'/f'{name}_lost_small_mask_pixels.png')
    circled=Image.fromarray(im);draw=ImageDraw.Draw(circled)
    for idx in np.where(lost)[0]:
        yy,xx=np.where(np.any(masks==idx,axis=0));cx,cy=float(xx.mean()),float(yy.mean());draw.ellipse((cx-9,cy-9,cx+9,cy+9),outline='red',width=2)
    draw.rectangle((0,0,650,24),fill='white');draw.text((5,5),'Red circles mark tiny vanished mask regions (display only)',fill='black')
    circled.save(OUT/'visualizations'/f'{name}_lost_small_mask_locations.png')
    target=OUT/'visualizations'/f'{name}_openseg_pca.png'
    if not target.exists():
        from sklearn.decomposition import PCA
        desc=np.load(OUT/'data/openseg_dense'/f'{name}.npz')['descriptors'];flat=desc.reshape(768,-1).T
        samples=flat[np.linspace(0,len(flat)-1,min(8192,len(flat)),dtype=int)].astype(np.float32)
        pca=PCA(n_components=3,svd_solver='randomized',random_state=0).fit(samples)
        # Display transform only. It is never passed into ReLaGS or the GNN.
        rgb=np.empty((len(flat),3),np.float32)
        for start in range(0,len(flat),32768):rgb[start:start+32768]=pca.transform(flat[start:start+32768].astype(np.float32))
        lo=np.quantile(rgb,.02,axis=0);hi=np.quantile(rgb,.98,axis=0);rgb=np.clip((rgb-lo)/np.maximum(hi-lo,1e-8),0,1)
        Image.fromarray((rgb.reshape(*desc.shape[1:],3)*255).astype(np.uint8)).save(target)
        np.savez_compressed(OUT/'data/openseg_dense'/f'{name}_display_pca.npz',components=pca.components_,mean=pca.mean_,display_low=lo,display_high=hi)
if not a.partial:assert len(rows)==350,len(rows)
summary={'status':'partial' if a.partial else 'verified','images':len(rows),'masks_lost_to_half_resolution':sum(r['additional_lost_after_half_resolution'] for r in rows),'masks_already_absent':sum(r['already_absent_in_sam_map'] for r in rows),'per_view':rows,'interpretation':'These are mask-index losses, not ground-truth part recall; overlapping SAM masks may already have no pixels before OpenSeg resizing.'}
dest='encoding_diagnostics_partial.json' if a.partial else 'encoding_diagnostics.json'
(OUT/'metrics'/dest).write_text(json.dumps(summary,indent=2))
fig,ax=plt.subplots(figsize=(10,4));ax.plot([r['additional_lost_after_half_resolution'] for r in rows],label='Lost after half-resolution');ax.plot([r['already_absent_in_sam_map'] for r in rows],label='Already absent');ax.set(xlabel='Encoded frame index',ylabel='Mask count');ax.legend();fig.tight_layout();fig.savefig(OUT/'visualizations/mask_loss_counts.png',dpi=160);plt.close(fig)
print(json.dumps({k:v for k,v in summary.items() if k!='per_view'},indent=2))
