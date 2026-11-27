from pathlib import Path
import sys,json,hashlib,time,csv,importlib.util
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT.parents[1];V1=ROOT.parent/'saga_relags_v1';V2=ROOT.parent/'saga_relags_v2';BENCH=ROOT.parent/'relational_retrieval_benchmark'
sys.path.insert(0,str(PROJECT))
def read(p):return json.loads(Path(p).read_text())
def write(p,d):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def save(p,im):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);(Image.fromarray(im) if isinstance(im,np.ndarray) else im).save(p)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(16<<20),b''):h.update(b)
    return h.hexdigest()
def csvwrite(p,rows):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows)
def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def world_model():return load_module('frozen_query',V2/'world_model/query.py').WorldModel(V2/'world_model')
def candidates(oid):return np.load(V1/'inputs/geometry/object_candidates'/oid/'gaussian_ids.npy')
def fine(oid):return np.load(V2/'outputs/A/extractions/refined/objects'/oid/'gaussian_indices.npy')
def union(arr):return np.unique(np.concatenate(arr)) if arr else np.zeros(0,np.int64)
def sync():
    import torch
    if torch.cuda.is_available():torch.cuda.synchronize()
class Context:project=PROJECT;state=read(V2/'inputs/m0_state.json')
def renderer():
    from industrial_world_model.render import Renderer
    return Renderer(Context())
def overlay(rgb,mask,color=(235,60,40)):
    result=np.array(rgb).copy();result[mask]=(result[mask]*.45+np.array(color)*.55).clip(0,255).astype(np.uint8);return result
def rgb(c):return np.array(Image.open(PROJECT/'data/images'/c['filename']).convert('RGB').resize((c['width'],c['height'])))
def scaled(c,width=1200):
    import copy
    c=copy.deepcopy(c);h=round(c['height']*width/c['width']);K=np.array(c['K']);K[0]*=width/c['width'];K[1]*=h/c['height'];c.update(width=width,height=h,K=K.tolist());return c
def verify_locks():
    for root,lock in [(BENCH/'configs',BENCH/'configs/FROZEN.json'),(BENCH,BENCH/'evaluation/pseudo_ground_truth/REFERENCE_FROZEN.json')]:
        assert all(sha(root/p)==h for p,h in read(lock)['sha256'].items()),str(lock)
    if (ROOT/'configs/FROZEN.json').exists():
        assert all(sha(PROJECT/p)==h for p,h in read(ROOT/'configs/FROZEN.json')['sha256'].items())

