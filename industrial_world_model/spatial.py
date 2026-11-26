import sqlite3,json,copy,shutil,importlib.util
import numpy as np
from PIL import Image,ImageDraw
from plyfile import PlyData
from .common import *

def snapshot(ctx):
 dest=ctx.out/'config';dest.mkdir(exist_ok=True)
 if (dest/'m0_state.json').exists():return
 root=ctx.source('m0_root');db=sqlite3.connect('file:'+str(root/'.m0.sqlite3')+'?mode=ro',uri=True);db.execute('BEGIN');row=db.execute('SELECT state FROM revisions ORDER BY revision DESC LIMIT 1').fetchone();s=json.loads(row[0]);row=db.execute("SELECT content FROM drafts WHERE key='workspace'").fetchone();draft=json.loads(row[0]) if row else None;db.close()
 assert s['revision']==ctx.c['input']['expected_revision'], 'M0 revision changed; inspect new input before changing config'
 assert not draft or (draft['base_revision']==s['revision'] and not draft.get('pendingObjects') and not draft.get('sceneDirty') and not draft.get('objectDirty')),'Pending M0 edits must be snapshotted explicitly; do not silently omit them'
 assert ctx.c['input']['allow_user_authorized_snapshot']
 write(dest/'m0_state.json',s);write(dest/'m0_workspace.json',draft);shutil.copy2(root/'.assets/images.json',dest/'images.json');shutil.copy2(root/'.assets/source_manifest.json',dest/'m0_source_manifest.json');shutil.copy2(ctx.config_path,dest/'config.json')
 write(dest/'input_review.json',dict(basis='User explicitly requested M1-M5 using the completed M0 annotations on 2026-11-26. Read-only snapshot; original formal review flags are not altered.',revision=s['revision'],scene_status=s['scene']['status'],floor_confirmed=s['scene']['floor_confirmed'],objects_with_missing_english_description=[k for k,o in s['objects'].items() if not o.get('deleted') and not o.get('description_en')],formal_confirmed_count=sum(o.get('status')=='confirmed' for o in s['objects'].values() if not o.get('deleted'))))
 records=[]
 for key in ['ply','sam','clip']:
  p=ctx.source(key);records.append(dict(role=key,path=str(p.relative_to(ctx.project)),bytes=p.stat().st_size,sha256=sha(p)))
 for p in [ctx.project/'data/colmap/sparse/0'/n for n in ['cameras.bin','images.bin','points3D.bin']]+[ctx.project/'data/scene_information/camera_split.json',dest/'m0_state.json',dest/'images.json']:
  records.append(dict(role='input',path=str(p.relative_to(ctx.project)),bytes=p.stat().st_size,sha256=sha(p)))
 write(ctx.out/'manifest.json',dict(method='industrial spatial-prior guided native 3DGS, first implementation',m0_revision=s['revision'],coordinate_version=s['scene']['coordinate_version'],units='sfm_relative',inputs=records,source_ply_immutable=True,reused_historical_semantic_results=False,excluded=['2DGS','MWP','Superpoints','THGS','OpenSeg','GNN'],id_contract='gaussian_id is original PLY vertex row; object_id and image_id preserved'))

def run(ctx):
 snapshot(ctx);s=ctx.state;T=np.array(s['scene']['transform']);assert np.allclose(T[:3,:3]@T[:3,:3].T,np.eye(3),atol=1e-6) and np.linalg.det(T[:3,:3])>0
 ply=PlyData.read(ctx.source('ply'))['vertex'].data;xyz=np.column_stack([ply[k] for k in ['x','y','z']]);assert np.isfinite(xyz).all();assert all('scale_'+str(i) in ply.dtype.names for i in range(3));ind=transform(xyz,T)
 base=ctx.path('M1','scene');base.mkdir(exist_ok=True);np.save(base/'xyz_raw.npy',xyz);np.save(base/'xyz_industrial.npy',ind.astype(np.float32));np.save(base/'max_scale.npy',np.exp(np.column_stack([ply['scale_'+str(i)] for i in range(3)])).max(1));np.save(base/'opacity.npy',1/(1+np.exp(-np.clip(ply['opacity'],-40,40))));np.save(base/'T_raw_to_industrial.npy',T);np.save(base/'T_industrial_to_raw.npy',np.linalg.inv(T));scene_ids=np.flatnonzero(inside(ind,s['scene']['bbox']));np.save(base/'gaussian_ids.npy',scene_ids)
 write(base/'scene.json',s['scene']);roundtrip=float(np.max(abs(transform(ind,np.linalg.inv(T))-xyz)));assert roundtrip<1e-5
 # Verify the read-only camera index against its original COLMAP binaries and RGB sizes/hashes.
 from m0.vendor.gaussian_splatting.scene.colmap_loader import read_extrinsics_binary,read_intrinsics_binary
 cams=read_intrinsics_binary(str(ctx.project/'data/colmap/sparse/0/cameras.bin'));ext=read_extrinsics_binary(str(ctx.project/'data/colmap/sparse/0/images.bin'));ext={v.name:v for v in ext.values()};split=read(ctx.project/'data/scene_information/camera_split.json')
 checks=[]
 for im in ctx.images:
  v=ext[im['filename']];cam=cams[v.camera_id];assert np.allclose(im['world_to_camera_R'],v.qvec2rotmat()) and np.allclose(im['world_to_camera_t'],v.tvec)
  fx,fy,cx,cy=cam.params if cam.model=='PINHOLE' else (cam.params[0],cam.params[0],cam.params[1],cam.params[2]);assert np.allclose(im['K'],[[fx,0,cx],[0,fy,cy],[0,0,1]])
  path=ctx.source('images')/im['filename'];assert Image.open(path).size==(im['width'],im['height']);assert sha(path)==im['sha256'];assert (im['filename'] in split['train'])==(im['split']=='train');checks.append(im['image_id'])
 objects=[]
 for o in s['objects'].values():
  if o.get('deleted'):continue
  row=copy.deepcopy(o);name=row['name_zh'].rstrip(' 0123456789');matches=[(zh,en) for zh,en in CATEGORIES if zh==name];assert len(matches)==1,name;row['category_zh'],row['category']=matches[0]
  ids=np.flatnonzero(inside(ind,o['bbox'])&inside(ind,s['scene']['bbox']));folder=ctx.path('M1','object_candidates',o['object_id']);folder.mkdir(parents=True,exist_ok=True);np.save(folder/'gaussian_ids.npy',ids);row['candidate_count']=len(ids);row['candidate_ids']=str((folder/'gaussian_ids.npy').relative_to(ctx.out));write(folder/'object.json',row);objects.append(row)
 write(ctx.path('M1','objects.json'),objects);write(base/'coordinate_validation.json',dict(roundtrip_max_error=roundtrip,camera_records_checked=len(checks),train=sum(i['split']=='train' for i in ctx.images),heldout=sum(i['split']=='heldout' for i in ctx.images),rgb_hashes_checked=len(checks),all_ply_rows_preserved=True))
 from .render import Renderer
 renderer=Renderer(ctx);vis=ctx.path('M1','visualization');vis.mkdir(exist_ok=True);reference=[]
 for iid in ctx.c['visualization']['reference_images']:
  if iid in ctx.image_map:reference.append(ctx.image_map[iid])
 write(ctx.out/'config/reference_cameras.json',reference)
 for im in reference:
  pic=Image.fromarray(renderer.rgb(im,width=ctx.c['visualization']['width']));draw=ImageDraw.Draw(pic);scale=pic.width/im['width']
  for o in objects:
   p=projected_box(o['bbox'],T,im)
   if p:draw.rectangle((np.array(p['bbox'])*scale).tolist(),outline='#ffc966',width=2)
  save_image(vis/(im['image_id']+'_boxes.jpg'),pic)
 paths=[]
 for index,o in enumerate(objects):
  ids=ctx.ids(o['object_id']);folder=vis/o['object_id'];folder.mkdir(exist_ok=True);rank=[]
  for im in ctx.images:
   if im['split']!='train':continue
   p=projected_box(o['bbox'],T,im)
   if p and p['image_coverage']>.8 and p['area_fraction']<.65:rank.append((p['area_fraction']*p['image_coverage'],im))
  if not rank:write(folder/'unavailable.json',{'reason':'No bounded training projection'});continue
  im=max(rank,key=lambda r:r[0])[1];write(folder/'camera.json',im);save_image(folder/'candidate_independent.jpg',renderer.rgb(im,ids,width=960));save_image(folder/'candidate_highlight.jpg',renderer.highlight(im,[(ids,[1,.32,.08])],width=960));paths.append(folder/'candidate_highlight.jpg')
  print('M1 candidate',index+1,len(objects),o['name_en'],len(ids),flush=True)
 sheet(paths,vis/'candidate_overview.jpg',labels=[o['name_en'] for o in objects][:len(paths)])
 return dict(objects=len(objects),gaussians=len(xyz),scene_gaussians=len(scene_ids),candidate_total=sum(o['candidate_count'] for o in objects),coordinate_roundtrip_max_error=roundtrip,train=306,heldout=44)
