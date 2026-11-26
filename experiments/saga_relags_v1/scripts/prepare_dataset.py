import json,sys,shutil,hashlib,collections
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation
from plyfile import PlyData
ROOT=Path(__file__).resolve().parents[1];PROJECT=ROOT.parents[1];sys.path.insert(0,str(PROJECT))
from m0.spatial import transform,inside

def read(p):return json.loads(Path(p).read_text())
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
cfg=read(ROOT/'configs/experiment.json');inputs=read(ROOT/'inputs/manifest.json');assert inputs['hybrid_compatible_with_latest_m0']
hybrid=PROJECT/inputs['hybrid_observations'];selected=read(hybrid/'selected_views.json');hybrid_images={im['image_id']:im for im in read(hybrid/'selected_cameras.json')}
original=read(ROOT/'inputs/cameras.json');train=[im for im in original if im['split']=='train'];imap={im['image_id']:im for im in train}
objects=read(ROOT/'inputs/objects.json');by_id={o['object_id']:o for o in objects};focus=[by_id[oid] for oid in cfg['focus_object_ids']];write(ROOT/'inputs/focus_objects.json',focus)
reasons=collections.defaultdict(list)
for obj in focus:
    views=selected[obj['object_id']]
    for source,limit in [('real',cfg['real_views_per_focus']),('virtual',cfg['virtual_views_per_focus'])]:
        matching=[v for v in views if (v['source_type']=='real')==(source=='real')][:limit]
        for v in matching:reasons[v['image_id']].append(dict(object_id=obj['object_id'],purpose='Representative '+source+' observation'))
for i in np.linspace(0,len(train)-1,cfg['uniform_real_views']).round().astype(int):reasons[train[i]['image_id']].append(dict(purpose='Trajectory coverage for shared scene affinity field'))
dataset=ROOT/'inputs/saga_dataset';(dataset/'images').mkdir(parents=True,exist_ok=True);sparse=dataset/'sparse/0';sparse.mkdir(parents=True,exist_ok=True)
records=[];cameras_text=['# PINHOLE cameras for selected original and existing full-scene virtual observations'];images_text=['# IMAGE_ID QW QX QY QZ TX TY TZ CAMERA_ID NAME; no 2D feature tracks required']
for index,iid in enumerate(sorted(reasons),1):
    if iid in imap:
        im=dict(imap[iid]);source=PROJECT/inputs['images']/im['filename'];im['source_type']='real'
    else:
        im=dict(hybrid_images[iid]);source=hybrid/read(hybrid/'manifest.json')['image_root']/im['filename'];assert im['source_type']!='real'
    assert im['split']=='train'
    filename=iid+source.suffix;dest=dataset/'images'/filename
    if not dest.exists():shutil.copy2(source,dest)
    original_path=str(source.relative_to(PROJECT));im.update(filename=filename,input_path=str(dest.relative_to(ROOT)),source_path=original_path,selection_reasons=reasons[iid],saga_colmap_id=index)
    K=np.array(im['K']);q=Rotation.from_matrix(im['world_to_camera_R']).as_quat();q=q[[3,0,1,2]]
    cameras_text.append(f'{index} PINHOLE {im["width"]} {im["height"]} '+ ' '.join(f'{float(v):.17g}' for v in [K[0,0],K[1,1],K[0,2],K[1,2]]))
    images_text.append(f'{index} '+ ' '.join(f'{float(v):.17g}' for v in [*q,*im['world_to_camera_t']])+f' {index} {filename}');images_text.append('')
    records.append(im)
(sparse/'cameras.txt').write_text('\n'.join(cameras_text)+'\n');(sparse/'images.txt').write_text('\n'.join(images_text)+'\n')
shutil.copy2(PROJECT/inputs['colmap']/'points3D.bin',sparse/'points3D.bin')
write(ROOT/'inputs/training_cameras.json',records)
model=ROOT/'outputs/A/saga_model';pc=model/'point_cloud/iteration_30000';pc.mkdir(parents=True,exist_ok=True)
native=PROJECT/inputs['ply'];target=pc/'scene_point_cloud.ply'
if not target.exists():shutil.copy2(native,target)
args=dict(sh_degree=3,feature_dim=32,init_from_3dgs_pcd=False,source_path=str(dataset),model_path=str(model),feature_model_path='',images='images',resolution=cfg['training_resolution'],white_background=False,data_device='cpu',eval=False,need_features=False,need_masks=False,allow_principle_point_shift=True)
(model/'cfg_args').write_text('Namespace('+', '.join(f'{k}={v!r}' for k,v in args.items())+')')
ply=PlyData.read(native)['vertex'].data;xyz=np.column_stack([ply[k] for k in ['x','y','z']]);T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform']);industrial=transform(xyz,T)
geo=ROOT/'inputs/geometry';geo.mkdir(exist_ok=True)
np.save(geo/'xyz_raw.npy',xyz);np.save(geo/'xyz_industrial.npy',industrial.astype(np.float32));np.save(geo/'max_scale.npy',np.exp(np.column_stack([ply['scale_'+str(i)] for i in range(3)])).max(1));np.save(geo/'original_gaussian_ids.npy',np.arange(len(xyz),dtype=np.int64))
scene=read(ROOT/'inputs/m0_state.json')['scene'];in_scene=inside(industrial,scene['bbox'])
for obj in objects:
    folder=geo/'object_candidates'/obj['object_id'];folder.mkdir(parents=True,exist_ok=True)
    ids=np.flatnonzero(inside(industrial,obj['bbox'])&in_scene);np.save(folder/'gaussian_ids.npy',ids)
knn=geo/'knn_16.npy'
if not knn.exists():
    tree=cKDTree(xyz);neighbors=np.lib.format.open_memmap(knn,mode='w+',dtype=np.uint32,shape=(len(xyz),cfg['smooth_K']))
    for start in range(0,len(xyz),100000):
        _,idx=tree.query(xyz[start:start+100000],k=cfg['smooth_K'],eps=0,workers=12);neighbors[start:start+len(idx)]=idx;print('Exact KNN',start+len(idx),'/',len(xyz),flush=True)
    neighbors.flush();del neighbors
write(ROOT/'inputs/dataset_summary.json',dict(training_cameras=len(records),real=sum(im['source_type']=='real' for im in records),virtual=sum(im['source_type']!='real' for im in records),heldout_cameras_used=0,native_gaussians=len(xyz),focus_objects=[dict(object_id=o['object_id'],name_zh=o['name_zh'],category_id=o['category_id']) for o in focus],geometry_retrained=False,prior_semantic_masks_reused=False,nearest_neighbors='Exact Euclidean K=16; cKDTree computation only, official local feature smoothing unchanged'))
print(json.dumps(read(ROOT/'inputs/dataset_summary.json'),ensure_ascii=False,indent=2))
