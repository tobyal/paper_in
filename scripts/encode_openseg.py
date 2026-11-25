#!/usr/bin/env python3
"""Industry/COLMAP adapter around the unchanged official OpenSeg extraction function."""
import argparse,ast,hashlib,json,pathlib,os,time
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','1')
os.environ.setdefault('TF_FORCE_GPU_ALLOW_GROWTH','true')
os.environ.setdefault('OMP_NUM_THREADS','8')
ROOT=pathlib.Path(__file__).resolve().parents[1]
# Read-only use of the sibling project environment's Torch package; this env owns TensorFlow.
import sys
relags_site=ROOT/'envs/relags/lib/python3.10/site-packages'
if str(relags_site) not in sys.path:sys.path.append(str(relags_site))
import numpy as np
from PIL import Image
import cv2
import tensorflow as tf
import torch
for gpu in tf.config.list_physical_devices('GPU'):tf.config.experimental.set_memory_growth(gpu,True)
tf.config.threading.set_inter_op_parallelism_threads(4);tf.config.threading.set_intra_op_parallelism_threads(8)
source=ROOT/'ReLaGS/scene_graph/data_anno/scan3r_packer.py'
tree=ast.parse(source.read_text());nodes=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in ['read_bytes','extract_openseg_img_feature']]
assert len(nodes)==2
namespace={'tf':tf,'np':np,'torch':torch,'Image':Image}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),namespace)
extract=namespace['extract_openseg_img_feature']
p=argparse.ArgumentParser();p.add_argument('--probe',action='store_true');p.add_argument('--limit',type=int);p.add_argument('--follow',action='store_true',help='Wait for fresh SAM/CLIP frame outputs from the disjoint encoding jobs');a=p.parse_args()
OUT=ROOT/'outputs/relags_baseline/02_image_encoding';rawdir=OUT/'data/openseg_dense';featdir=OUT/'data/language_features_openseg'
rawdir.mkdir(parents=True,exist_ok=True);featdir.mkdir(parents=True,exist_ok=True)
model=tf.saved_model.load(str(ROOT/'models/openseg'),tags=[tf.saved_model.SERVING])
probe={'tensorflow':tf.__version__,'torch':torch.__version__,'visible_gpu_count':len(tf.config.list_physical_devices('GPU')),'official_extractor_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'serving_outputs':{k:str(v) for k,v in model.signatures['serving_default'].structured_outputs.items()},'resolution_policy':'Official scan3r_packer halves input height/width before mask pooling; industrial input is not rotated','regional_pool':True,'no_model_replacement':True}
assert 'ppixel_ave_feat' in model.signatures['serving_default'].structured_outputs
images=sorted((ROOT/'data/images').glob('*.jpg'))
if a.limit:images=images[:a.limit]
if a.probe:images=images[:1]
records=[]
for im_path in images:
    t=time.time();name=im_path.stem;dest=featdir/f'{name}_f_openseg.npy';rawpath=rawdir/f'{name}.npz';meta=rawdir/f'{name}.json'
    if a.follow and not a.probe:
        waited=0
        while not all((OUT/'data/language_features'/f'{name}_{suffix}.npy').is_file() for suffix in ['f','s']):
            states=[json.loads(x.read_text()).get('status') for x in (OUT/'metrics').glob('sam_clip_shard_*.json')]
            if len(states)>=3 and all(x!='running' for x in states):raise RuntimeError(f'Missing SAM frame after all encoders exited: {name}; states={states}')
            if waited%300==0:print('WAITING_FOR_FRESH_SAM',name,waited,flush=True)
            time.sleep(10);waited+=10
    if dest.exists() and rawpath.exists() and meta.exists() and not a.probe:
        rec=json.loads(meta.read_text());records.append(rec);print('REUSED',name,flush=True);continue
    with Image.open(im_path) as im:hw=[int(im.height/2),int(im.width/2)]
    if rawpath.exists():descriptors=torch.from_numpy(np.load(rawpath)['descriptors'])
    else:
        descriptors=extract(str(im_path),model,img_size=hw,regional_pool=True,r3scan=False)
        tmp=rawpath.with_suffix('.tmp.npz');np.savez_compressed(tmp,descriptors=descriptors.numpy());os.replace(tmp,rawpath)
    assert descriptors.shape==(768,*hw) and torch.isfinite(descriptors).all()
    if a.probe:
        probe.update(descriptor_shape=list(descriptors.shape),descriptor_dtype=str(descriptors.dtype),finite=True,elapsed_seconds=time.time()-t)
        (OUT/'metrics/openseg_probe.json').write_text(json.dumps(probe,indent=2));print(json.dumps(probe,indent=2));break
    masks=np.load(OUT/'data/language_features'/f'{name}_s.npy',mmap_mode='r')
    nf=np.load(OUT/'data/language_features'/f'{name}_f.npy',mmap_mode='r').shape[0]
    pooled=torch.zeros(nf,768,dtype=torch.float16);counts=np.zeros(nf,dtype=np.int64)
    # Same nearest mask resizing and per-mask mean as official scan3r_packer.py:290-295.
    for seg in masks:
        small=cv2.resize(np.asarray(seg,dtype=np.float32),(hw[1],hw[0]),interpolation=cv2.INTER_NEAREST).astype(np.int64)
        for idx in np.unique(small):
            if idx<0:continue
            obj_mask=torch.from_numpy(small==idx)
            obj_descriptors=descriptors[:,obj_mask].T
            pooled[idx]=obj_descriptors.mean(dim=0);counts[idx]=int(obj_mask.sum())
    assert torch.isfinite(pooled).all()
    tmp=dest.with_suffix('.tmp.npy');np.save(tmp,pooled.float().numpy());os.replace(tmp,dest);np.save(rawdir/f'{name}_mask_pixel_counts.npy',counts)
    rec={'image':im_path.name,'descriptor_shape':list(descriptors.shape),'pooled_shape':list(pooled.shape),'zero_pixel_masks':int((counts==0).sum()),'elapsed_seconds':time.time()-t,'official_extractor_sha256':probe['official_extractor_sha256']}
    meta.write_text(json.dumps(rec,indent=2));records.append(rec);print(json.dumps(rec),flush=True)
if not a.probe:
    link=ROOT/'data/language_features_openseg'
    if not link.exists():link.symlink_to(os.path.relpath(featdir,link.parent),target_is_directory=True)
    (OUT/'metrics/openseg_verification.json').write_text(json.dumps({'status':'verified' if len(records)==350 else 'partial','images':len(records),'feature_dim':768,'per_view':records,'interface':probe},indent=2))
