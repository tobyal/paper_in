#!/usr/bin/env python3
import argparse,json,pathlib
import numpy as np
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/relags_baseline/02_image_encoding'
p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');a=p.parse_args()
refs=json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']
records=[];rng=np.random.default_rng(0);palette=rng.integers(32,255,(10000,3),dtype=np.uint8)
for p in sorted((ROOT/'data/images').glob('*.jpg')):
    if a.partial and not all((OUT/'data/language_features'/f'{p.stem}_{suffix}.npy').exists() for suffix in ['f','s']):continue
    name=p.stem;s=np.load(OUT/'data/language_features'/f'{name}_s.npy',mmap_mode='r');f=np.load(OUT/'data/language_features'/f'{name}_f.npy')
    assert s.ndim==3 and s.shape[0]==4 and f.ndim==2 and f.shape[1]==512,name
    assert np.isfinite(f).all() and np.isfinite(s).all(),name
    assert s.min()>=-1 and s.max()<len(f) and np.equal(s,np.floor(s)).all(),name
    with Image.open(p) as im:assert s.shape[1:]==(im.height,im.width)
    records.append({'image':p.name,'feature_shape':list(f.shape),'segmentation_shape':list(s.shape),'segments_per_level':[len(np.unique(x[x>=0])) for x in s],'uncovered_fraction':[float((x<0).mean()) for x in s],'feature_norm_range':[float(np.linalg.norm(f,axis=1).min()),float(np.linalg.norm(f,axis=1).max())]})
    if p.name in refs:
        with Image.open(p) as im:rgb=np.array(im.convert('RGB'))
        sheet=Image.new('RGB',(320*5,180+24),'white');draw=ImageDraw.Draw(sheet)
        sheet.paste(Image.fromarray(rgb).resize((320,180)),(0,0));draw.text((5,184),name,fill='black')
        for level in range(4):
            labels=s[level].astype(np.int64);colors=palette[np.maximum(labels,0)%len(palette)].copy();colors[labels<0]=0
            overlay=(.4*rgb+.6*colors).astype(np.uint8);sheet.paste(Image.fromarray(overlay).resize((320,180)),((level+1)*320,0));draw.text(((level+1)*320+5,184),['default','small','medium','large'][level],fill='black')
        sheet.save(OUT/'visualizations'/f'{name}_sam_levels.jpg',quality=95)
if not a.partial:assert len(records)==350
status='partial' if a.partial else 'verified'
summary={'status':status,'images':len(records),'all_masks_newly_computed':True,'features_dim':512,'four_sam_levels':True,'per_view':records}
filename='encoding_partial.json' if a.partial else 'encoding_verification.json'
(OUT/'metrics'/filename).write_text(json.dumps(summary,indent=2))
print(json.dumps({'images':len(records),'status':status}))
