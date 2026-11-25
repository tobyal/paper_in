#!/usr/bin/env python3
"""Contact sheets from real fixed-camera query outputs; display selection only."""
import json,pathlib
import numpy as np
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1]
b=ROOT/'outputs/relags_baseline/09_relational_query'
summary=json.loads((b/'metrics/query_summary.json').read_text())
refs=[pathlib.Path(x).stem for x in json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']]
records=[];sheet=Image.new('RGB',(1280,228*((len(summary['queries'])+3)//4)),'white');draw=ImageDraw.Draw(sheet)
for i,q in enumerate(summary['queries']):
    views=[]
    for name in refs:
        mask=np.load(b/'data'/q['id']/f'{name}_projection.npz')['alpha_weighted_selection']
        views.append({'image':name,'mean_alpha_weighted_selection':float(mask.mean()),'pixels_above_0_5':int((mask>.5).sum())})
    best=max(views,key=lambda x:x['mean_alpha_weighted_selection'])
    with Image.open(b/'visualizations'/q['id']/f'{best["image"]}.png') as im:tile=im.convert('RGB').resize((320,180))
    x=i%4*320;y=i//4*228;sheet.paste(tile,(x,y))
    draw.text((x+4,y+183),q['query'] if isinstance(q['query'],str) else str(q['query']),fill='black')
    draw.text((x+4,y+199),f'{best["image"]}; {q["selected_gaussians"]} Gaussians',fill='black')
    draw.text((x+4,y+214),f'mean projected weight {best["mean_alpha_weighted_selection"]:.4f}',fill='black')
    records.append({'id':q['id'],'query':q['query'],'display_view':best['image'],'per_view':views})
sheet.save(b/'visualizations/query_overview.jpg',quality=95)
(b/'metrics/query_visibility.json').write_text(json.dumps({'definition':'For display choose the fixed reference camera with greatest mean alpha-weighted selection. No change to queries or selection. Pixel threshold is a display statistic, not an accuracy metric.','queries':records},indent=2))
print(json.dumps({'queries':len(records),'visualization':'visualizations/query_overview.jpg'}))
