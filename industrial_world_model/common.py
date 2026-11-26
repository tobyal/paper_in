import hashlib,json,os,time,copy
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from m0.spatial import transform,corners,inside

CATEGORIES=[('物料车','material_cart'),('装配夹具台','assembly_fixture'),('带黑色工件的夹具台','loaded_fixture'),('多层料架','multi_tier_rack'),('蓝色箱组','blue_bins'),('立式移动冷风机','air_cooler'),('工作台','workbench'),('分隔式料架','compartment_rack')]
STAGES={'M1':'M1_spatial_constraint','M2.1':'M2_object_modeling/M2_1_view_selection','M2.2':'M2_object_modeling/M2_2_sam_segmentation','M2.3':'M2_object_modeling/M2_3_gaussian_association','M2.4':'M2_object_modeling/M2_4_instance_extraction','M2.5':'M2_object_modeling/M2_5_reprojection','M2.6':'M2_object_modeling/M2_6_semantic_map','M3.1':'M3_semantic_fusion/M3_1_visual_encoding','M3.2':'M3_semantic_fusion/M3_2_feature_aggregation','M3.3':'M3_semantic_fusion/M3_3_text_encoding','M3.4':'M3_semantic_fusion/M3_4_object_semantics','M4':'M4_scene_graph','M5':'M5_relational_query','package':'final_world_model'}
def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))
def write(path,data):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');os.replace(tmp,p)
def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()
def normalize(a):return a/np.maximum(np.linalg.norm(a,axis=-1,keepdims=True),1e-12)
def save_image(path,array):
 p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
 if isinstance(array,Image.Image):im=array
 else:im=Image.fromarray(np.uint8(np.clip(array,0,1)*255+.5) if array.dtype.kind=='f' else array)
 im.save(p)
def mask_image(path,mask):save_image(path,np.uint8(mask)*255)
def overlay(rgb,mask,color=(255,95,40),alpha=.5):
 a=np.asarray(rgb).copy();a[mask]=np.uint8(a[mask]*(1-alpha)+np.array(color)*alpha);return a
def sheet(paths,destination,labels=None,columns=4,tile=(320,205)):
 paths=list(paths)
 if not paths:return
 im=Image.new('RGB',(tile[0]*columns,tile[1]*int(np.ceil(len(paths)/columns))),'#16202a');draw=ImageDraw.Draw(im)
 for i,p in enumerate(paths):
  pic=Image.open(p).convert('RGB');pic.thumbnail((tile[0],tile[1]-27));x=i%columns*tile[0];y=i//columns*tile[1];im.paste(pic,(x,y));draw.text((x+4,y+tile[1]-23),(labels[i] if labels else Path(p).stem)[:50],fill='white')
 save_image(destination,im)
def project(points,im):
 p=np.asarray(points)@np.asarray(im['world_to_camera_R']).T+im['world_to_camera_t'];uvw=p@np.array(im['K']).T
 return uvw[:,:2]/np.maximum(p[:,2,None],1e-10),p[:,2]
def projected_box(box,T,im):
 uv,z=project(transform(corners(box),np.linalg.inv(T)),im)
 if np.any(z<=.01):return None
 lo=uv.min(0);hi=uv.max(0);clo=np.maximum(lo,0);chi=np.minimum(hi,[im['width']-1,im['height']-1]);size=chi-clo
 if np.any(size<8):return None
 return dict(bbox=[*clo.tolist(),*chi.tolist()],area_fraction=float(np.prod(size)/(im['width']*im['height'])),image_coverage=float(np.prod(size)/np.prod(np.maximum(hi-lo,1))),unclipped_bbox=[*lo.tolist(),*hi.tolist()])
def object_color(index):
 import colorsys
 return np.array(colorsys.hsv_to_rgb((index*.61803398875)%1,.78,.98))

class Context:
 def __init__(self,config):
  self.project=Path(__file__).resolve().parents[1];self.config_path=Path(config).resolve();self.c=read(self.config_path);self.out=self.project/self.c['output'];self.out.mkdir(parents=True,exist_ok=True)
 def path(self,stage,*parts):
  p=self.out/STAGES[stage];p.mkdir(parents=True,exist_ok=True);return p.joinpath(*parts)
 def source(self,key):return self.project/self.c['input'][key]
 @property
 def state(self):return read(self.out/'config/m0_state.json')
 @property
 def objects(self):return read(self.path('M1','objects.json'))
 @property
 def images(self):return read(self.out/'config/images.json')
 @property
 def image_map(self):return {im['image_id']:im for im in self.images}
 @property
 def xyz(self):return np.load(self.path('M1','scene/xyz_raw.npy'),mmap_mode='r')
 @property
 def industrial(self):return np.load(self.path('M1','scene/xyz_industrial.npy'),mmap_mode='r')
 @property
 def scales(self):return np.load(self.path('M1','scene/max_scale.npy'),mmap_mode='r')
 @property
 def opacity(self):return np.load(self.path('M1','scene/opacity.npy'),mmap_mode='r')
 def ids(self,oid,final=False):return np.load(self.path('M2.4' if final else 'M1',oid,'gaussian_ids.npy') if final else self.path('M1','object_candidates',oid,'gaussian_ids.npy'))
 def rgb(self,im):return np.asarray(Image.open(self.source('images')/im['filename']).convert('RGB'))
 def selected(self):return read(self.path('M2.1','selected_views.json'))
 def segmentation(self):return read(self.path('M2.2','observations.json'))
 def instances(self):return read(self.path('M2.4','instances.json'))
 def visibility(self,ids,im):
  depth=np.load(self.path('M2.1','full_scene_depth',im['image_id']+'.npz'));uv,z=project(self.xyz[ids],im);pixels=np.rint(uv).astype(np.int32);v=(z>.01)&(pixels[:,0]>=0)&(pixels[:,0]<im['width'])&(pixels[:,1]>=0)&(pixels[:,1]<im['height']);local=np.flatnonzero(v)
  if not len(local):return local,pixels[local],np.empty(0,np.float32)
  px=pixels[local];x,y=px.T;d=depth['depth'][y,x].astype(float);std=depth['std'][y,x].astype(float);alpha=depth['alpha'][y,x].astype(float);cfg=self.c['visibility']
  tol=cfg['absolute_depth_tolerance']+cfg['relative_depth_tolerance']*z[local]+np.minimum(std,cfg['maximum_std_allowance'])+np.minimum(self.scales[ids[local]],cfg['gaussian_scale_allowance'])
  error=abs(z[local]-d);valid=(alpha>=cfg['minimum_alpha'])&(std<=cfg['maximum_depth_std'])&(error<=tol)&(d>0)
  weights=alpha*np.exp(-.5*(error/np.maximum(tol,1e-8))**2)
  return local[valid],px[valid],weights[valid].astype(np.float32)
