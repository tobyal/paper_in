from pathlib import Path
import sys,json,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parents[1]
sys.path.insert(0,str(PROJECT))
def read(path):return json.loads(Path(path).read_text())
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def save(path,image):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);(Image.fromarray(image) if isinstance(image,np.ndarray) else image).save(path)
def norm(a):return a/np.maximum(np.linalg.norm(a,axis=-1,keepdims=True),1e-9)
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(8<<20),b''):h.update(b)
    return h.hexdigest()
def grid(paths,destination,labels=None,columns=4,tile=(360,260)):
    if not paths:return
    canvas=Image.new('RGB',(columns*tile[0],int(np.ceil(len(paths)/columns))*tile[1]),'#15212d');d=ImageDraw.Draw(canvas)
    for i,p in enumerate(paths):
        im=Image.open(p).convert('RGB');im.thumbnail((tile[0],tile[1]-35));x=i%columns*tile[0];y=i//columns*tile[1];canvas.paste(im,(x,y));d.text((x+5,y+tile[1]-28),(labels[i] if labels else Path(p).stem),fill='white')
    save(destination,canvas)
def scaled_camera(im,width=None,downsample=None):
    import copy
    c=copy.deepcopy(im);w=width or im['width']//downsample;h=round(im['height']*w/im['width']) if width else im['height']//downsample
    K=np.array(c['K'],float);K[0]*=w/im['width'];K[1]*=h/im['height'];c.update(width=w,height=h,K=K.tolist());return c
class NativeContext:
    def __init__(self):self.project=PROJECT;self.state=read(ROOT/'inputs/m0_state.json')
