"""Make compact figure layouts from unchanged saved native renderings."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *

fig=ROOT/'docs/figures';objects=read(ROOT/'outputs/A/final_summary.json')['objects'];paths=[];labels=[]
for i,o in enumerate(objects,1):
    source=ROOT/'outputs/A/extractions/refined/objects'/o['object_id']/'visualizations/oblique.jpg';im=Image.open(source).convert('RGB');a=np.asarray(im);y,x=np.where(a.max(2)>20)
    if len(x):
        pad=20;box=[max(int(x.min())-pad,0),max(int(y.min())-pad,0),min(int(x.max())+pad+1,im.width),min(int(y.max())+pad+1,im.height)];im=im.crop(box)
    target=ROOT/'outputs/A/final_gallery'/(o['object_id']+'_compact.jpg');save(target,im);paths.append(target);labels.append(f'O{i:02d} '+o['name_en']+'\n'+o['extraction_status'])
grid(paths,fig/'all_33_compact.jpg',labels=labels,columns=5,tile=(400,340))
# The full-resolution figure and original camera remain available. This is only a page crop.
im=Image.open(fig/'instance_graph_oblique.jpg');image=im.crop((0,0,1800,1800));a=np.array(image);y,x=np.where(a.max(2)>20);box=[max(int(x.min())-45,0),max(int(y.min())-45,0),min(int(x.max())+46,1800),min(int(y.max())+46,1800)];crop=image.crop(box);crop.thumbnail((1800,1200));legend=im.crop((0,1800,1800,2500));canvas=Image.new('RGB',(1800,crop.height+700),'#14212b');canvas.paste(crop,((1800-crop.width)//2,0));canvas.paste(legend,(0,crop.height));save(fig/'instance_graph_compact.jpg',canvas);write(ROOT/'outputs/C/visualizations/compact_figure_crop.json',dict(source='docs/figures/instance_graph_oblique.jpg',crop_xyxy=box,original_projection_unchanged=True))
print('Compact layouts saved; native data and camera renderings unchanged')
