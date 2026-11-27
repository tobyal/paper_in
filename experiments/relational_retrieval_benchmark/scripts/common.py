from pathlib import Path
import sys,json,hashlib,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[1];ELI=PROJECT.parent/'paper_eli';V2=ROOT.parent/'saga_relags_v2'
sys.path.insert(0,str(PROJECT))
def read(path):return json.loads(Path(path).read_text())
def write(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(16<<20),b''):h.update(chunk)
    return h.hexdigest()
def save(path,image):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);(Image.fromarray(image) if isinstance(image,np.ndarray) else image).save(path)
def scaled_camera(camera,width=938,height=528):
    import copy
    c=copy.deepcopy(camera);k=np.array(c['K']);k[0]*=width/c['width'];k[1]*=height/c['height'];c.update(K=k.tolist(),width=width,height=height);return c
def sync():
    import torch
    if torch.cuda.is_available():torch.cuda.synchronize()
def check_frozen():
    frozen=read(ROOT/'configs/FROZEN.json')
    assert all(sha(ROOT/'configs'/name)==digest for name,digest in frozen['sha256'].items())
def plain(value):
    import torch
    if torch.is_tensor(value):return value.detach().cpu().tolist()
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,np.generic):return value.item()
    if isinstance(value,dict):return {str(k):plain(v) for k,v in value.items()}
    if isinstance(value,(tuple,list)):return [plain(v) for v in value]
    return value
def local_clip_weights():
    import open_clip
    factory=open_clip.create_model_and_transforms
    def local(model_name,*args,**kwargs):
        kwargs['pretrained']=str(PROJECT/('models/openclip_text/ViT-L-14-336px.pt' if model_name=='ViT-L-14-336' else 'models/openclip_vit_b16/open_clip_pytorch_model.bin'))
        kwargs['cache_dir']=str(ROOT/'cache/openclip');return factory(model_name,*args,**kwargs)
    open_clip.create_model_and_transforms=local
def timed(fn,repetitions=3,warmup=True):
    if warmup:fn();sync()
    samples=[];result=None
    for _ in range(repetitions):
        sync();t=time.perf_counter();result=fn();sync();samples.append(time.perf_counter()-t)
    return result,dict(samples_seconds=samples,median_seconds=float(np.median(samples)),mean_seconds=float(np.mean(samples)),warmup=warmup,repetitions=repetitions)
def timed_pipeline(query_fn,render_fn):
    value=query_fn();render_fn(value);sync();samples=[]
    for _ in range(3):
        sync();start=time.perf_counter();value=query_fn();sync();middle=time.perf_counter();views=render_fn(value);sync();end=time.perf_counter()
        samples.append(dict(query=middle-start,render=end-middle,end_to_end=end-start))
    timing={k:dict(samples_seconds=[s[k] for s in samples],median_seconds=float(np.median([s[k] for s in samples]))) for k in samples[0]}
    timing.update(warmup=1,repetitions=3,export_io_excluded=True)
    return value,views,timing
def camera_native(c):
    """Camera attributes for the existing native renderers, with exact K and extrinsics."""
    from types import SimpleNamespace
    import torch,math
    R=np.array(c['world_to_camera_R']);t=np.array(c['world_to_camera_t']);K=np.array(c['K']);w=c['width'];h=c['height'];znear=.01;zfar=100.
    V=np.eye(4);V[:3,:3]=R;V[:3,3]=t;P=np.zeros((4,4));P[0,0]=2*K[0,0]/w;P[1,1]=2*K[1,1]/h;P[0,2]=2*(K[0,2]+.5)/w-1;P[1,2]=2*(K[1,2]+.5)/h-1;P[2,2]=zfar/(zfar-znear);P[2,3]=-zfar*znear/(zfar-znear);P[3,2]=1
    v=torch.tensor(V,dtype=torch.float32,device='cuda').T;p=torch.tensor(P,dtype=torch.float32,device='cuda').T
    return SimpleNamespace(image_width=w,image_height=h,FoVx=2*math.atan(w/(2*K[0,0])),FoVy=2*math.atan(h/(2*K[1,1])),world_view_transform=v,full_proj_transform=v@p,projection_matrix=p,camera_center=v.inverse()[3,:3],znear=znear,zfar=zfar,image_name=c['image_id'])
def export_view(method,q,c,soft,mask,metadata=None):
    dest=ROOT/'outputs'/method/q['query_id']/c['image_id'];dest.mkdir(parents=True,exist_ok=True);rgb=np.array(Image.open(PROJECT/'data/images'/c['filename']).convert('RGB').resize((c['width'],c['height'])));mask=np.asarray(mask,bool);soft=np.asarray(soft,np.float32)
    assert soft.shape==mask.shape==(c['height'],c['width']);assert np.isfinite(soft).all()
    overlay=rgb.copy();overlay[mask]=(rgb[mask]*.45+np.array([255,30,15])*.55).clip(0,255).astype(np.uint8)
    np.savez_compressed(dest/'response.npz',response=soft);save(dest/'mask.png',mask.astype(np.uint8)*255);save(dest/'overlay.jpg',overlay);write(dest/'camera.json',c);write(dest/'metadata.json',dict(mask_pixels=int(mask.sum()),**(metadata or {})))
    pred=ROOT/'evaluation/predictions'/method/q['query_id'];pred.mkdir(parents=True,exist_ok=True);link=pred/(c['image_id']+'.png')
    if not link.exists():link.symlink_to(dest/'mask.png')
    return dict(camera_id=c['image_id'],mask_pixels=int(mask.sum()),directory=str(dest.relative_to(ROOT)))
