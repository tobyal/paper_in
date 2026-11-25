#!/usr/bin/env python3
"""Track the two previously selected diagnostic pixels through official 3D labels."""
import json, pathlib
import numpy as np
from PIL import Image, ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1]
base=ROOT/'outputs/relags_baseline/05_hierarchical_grouping'
source=ROOT/'outputs/relags_baseline/02_image_encoding/metrics/foreground_pair_mask_probe.json'
probe=json.loads(source.read_text());stem=pathlib.Path(probe['image']).stem
maps=np.load(base/'data/id_projections'/f'{stem}.npz')
height,width=maps['gaussian_id'].shape
with Image.open(ROOT/'data/images'/probe['image']) as im:
    native_size=im.size;rgb=im.convert('RGB').resize((width,height))
points=[(int(x*width/native_size[0]),int(y*height/native_size[1])) for x,y in probe['pixel_xy']]
records=[]
for key in maps.files:
    ids=[int(maps[key][y,x]) for x,y in points]
    neighborhoods=[]
    for x,y in points:
        labels,counts=np.unique(maps[key][y-2:y+3,x-2:x+3],return_counts=True)
        neighborhoods.append(dict(zip(map(str,labels.tolist()),counts.tolist())))
    records.append({'map':key,'center_ids':ids,'same_center_id':ids[0]==ids[1],'five_by_five_pixel_counts':neighborhoods})
summary={'source_manual_probe':str(source.relative_to(ROOT)),'native_xy':probe['pixel_xy'],
         'render_xy':points,'coordinate_mapping':'floor(native_x * render_width / native_width), likewise y',
         'levels':records,'interpretation':'The two diagnostic pixels have different level-2 groups but the same level-3 parent. This is a candidate coarse-merge issue, not a GT instance metric. Maximum-contribution ID projection has local boundary ambiguity; 5x5 counts are retained.'}
(base/'metrics/reference_pair_analysis.json').write_text(json.dumps(summary,indent=2))
canvas=Image.new('RGB',(width*3,height+26),'white');draw=ImageDraw.Draw(canvas)
panels=[('Copied RGB',rgb)]
for level in [2,3]:
    path=base/'visualizations/id_projections'/f'{stem}_level_{level}_overlay.png'
    with Image.open(path) as im:panels.append((f'Official 3D hierarchy level {level}',im.convert('RGB').copy()))
for i,(title,im) in enumerate(panels):
    d=ImageDraw.Draw(im)
    for label,(x,y) in zip(['A','B'],points):
        d.ellipse([x-8,y-8,x+8,y+8],outline='yellow',width=3)
        d.text((x+10,y-10),label,fill='yellow',stroke_width=1,stroke_fill='black')
    canvas.paste(im,(i*width,0));draw.text((i*width+5,height+5),title,fill='black')
canvas.save(base/'visualizations/reference049_pair_levels.jpg',quality=95)
print(json.dumps(summary,indent=2))
