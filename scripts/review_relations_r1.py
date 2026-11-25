"""Display-only localization crops and repeated-subject diagnostics."""
import json,pathlib
import numpy as np
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1];B=ROOT/'outputs/relags_obb_repair_r1/09_relational_query'
rows=json.loads((B/'metrics/relational_review.json').read_text())['queries'];stats=[]
canvas=Image.new('RGB',(1200,390*3),'white');draw=ImageDraw.Draw(canvas)
for i,r in enumerate(rows):
    frame=r['display_view'];mask=np.load(B/'data'/r['id']/f'{frame}_projection.npz')['alpha_weighted_selection']
    py,px=np.unravel_index(mask.argmax(),mask.shape)
    im=Image.open(B/'visualizations'/r['id']/f'{frame}.png').convert('RGB');w,h=im.size
    left=max(0,min(w-120,int(px)-60));top=max(0,min(h-120,int(py)-60));box=(left,top,left+120,top+120)
    crop=im.crop(box).resize((300,300));marked=im.copy();md=ImageDraw.Draw(marked);md.rectangle(box,outline='yellow',width=3)
    row={'id':r['id'],'frame':frame,'max_xy':[int(px),int(py)],'max_projected_selection':float(mask.max()),'mean_projected_selection':float(mask.mean()),'pixels_gt_0_5':int((mask>.5).sum()),'pixels_gt_0_1':int((mask>.1).sum()),'display_crop_box':list(box)}
    stats.append(row);x=i%2*600;y=i//2*390;canvas.paste(marked.resize((300,169)),(x,y));canvas.paste(crop,(x+300,y))
    q=r['query'];draw.text((x+4,y+309),f"{r['id']}: {q['subject']} | {q['relation']}",fill='black')
    draw.text((x+4,y+325),f"{frame}; {r['selected_gaussians']} Gaussians; selected subject only",fill='black')
    draw.text((x+4,y+341),f"max weight={mask.max():.3f}; pixels >0.5={row['pixels_gt_0_5']}",fill='black')
    draw.text((x+4,y+357),'Yellow box / crop are display aids, not new predictions.',fill='black')
same=[]
for i,a in enumerate(rows):
    ia=np.load(B/'data'/a['id']/'gaussian_indices.npy')
    for b in rows[i+1:]:
        ib=np.load(B/'data'/b['id']/'gaussian_indices.npy')
        if np.array_equal(ia,ib):same.append([a['id'],b['id']])
(B/'metrics/relational_localization_diagnostics.json').write_text(json.dumps({'per_query':stats,'identical_selected_gaussian_sets':same,'interpretation':'Projection size and agreement between predictions are not accuracy or ground-truth IoU.'},indent=2))
canvas.save(B/'visualizations/relational_query_crops.jpg',quality=95)
print(json.dumps({'identical_selected_gaussian_sets':same,'queries':6}))
