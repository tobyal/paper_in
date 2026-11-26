import numpy as np
from PIL import Image,ImageDraw
from .common import *

def run(ctx):
 cfg=ctx.c['views'];T=np.array(ctx.state['scene']['transform']);objects=ctx.objects;train=[im for im in ctx.images if im['split']=='train'];imap={im['image_id']:im for im in train};rows={};union=set()
 for o in objects:
  values=[]
  for im in train:
   p=projected_box(o['bbox'],T,im);row={'image_id':im['image_id'],'geometrically_eligible':False,'visibility_evaluated':False}
   if p:
    row.update(p);row['geometric_score']=p['image_coverage']*np.sqrt(p['area_fraction']);row['geometrically_eligible']=cfg['minimum_area_fraction']<=p['area_fraction']<=cfg['maximum_area_fraction'] and p['image_coverage']>=cfg['minimum_image_coverage'];row['reason']=None if row['geometrically_eligible'] else 'Insufficient image coverage/area or excessively close view'
   else:row['reason']='Behind camera, near-plane crossing or no bounded projection'
   values.append(row)
  shortlist=sorted([r for r in values if r['geometrically_eligible']],key=lambda r:r['geometric_score'],reverse=True)[:cfg['shortlist']]
  for r in shortlist:r['shortlisted']=True;union.add(r['image_id'])
  rows[o['object_id']]=values
 from .render import Renderer
 renderer=Renderer(ctx);folder=ctx.path('M2.1','full_scene_depth');folder.mkdir(exist_ok=True)
 cache_identity=dict(ply_sha256=sha(ctx.source('ply')),cameras_sha256=sha(ctx.out/'config/images.json'),renderer_sha256=sha(Path(__file__).with_name('render.py')))
 metadata=folder/'cache_identity.json';reuse=metadata.exists() and read(metadata)==cache_identity
 # A failed attempt may resume only matching depth calculations. Legacy caches
 # without provenance are recomputed; completed old stage folders are archived.
 for j,iid in enumerate(sorted(union)):
  path=folder/(iid+'.npz')
  if not reuse or not path.exists():
   result=renderer.moments(imap[iid]);assert np.isfinite(result['depth']).all() and np.isfinite(result['std']).all();np.savez_compressed(path,**result)
   if j<6:
    import matplotlib.pyplot as plt
    fig,axs=plt.subplots(1,3,figsize=(12,3));axs[0].imshow(result['depth'],cmap='turbo',vmin=0,vmax=10);axs[1].imshow(result['alpha'],vmin=0,vmax=1);axs[2].imshow(result['std'],vmin=0,vmax=.2);[ax.set_axis_off() for ax in axs];fig.tight_layout();fig.savefig(folder/(iid+'_moments.jpg'),dpi=100);plt.close(fig)
  print('M2.1 full-scene depth',j+1,len(union),iid,flush=True)
 write(metadata,cache_identity)
 selected={};all_paths=[]
 for o in objects:
  oid=o['object_id'];ids=ctx.ids(oid);sample=ids[np.unique(np.linspace(0,max(len(ids)-1,0),min(len(ids),cfg['sample_centers'])).astype(int))] if len(ids) else ids;center=transform([o['bbox']['center']],np.linalg.inv(T))[0]
  for r in rows[oid]:
   if not r.get('shortlisted'):continue
   im=imap[r['image_id']];local,pixels,w=ctx.visibility(sample,im);r['visible_centers']=len(local);r['tested_centers']=len(sample);r['visible_fraction']=len(local)/max(len(sample),1);r['visibility_evaluated']=True;r['score']=r['geometric_score']*np.sqrt(r['visible_fraction']);r['eligible']=r['visible_fraction']>=cfg['minimum_visible_fraction'];r['direction']=normalize((np.array(im['center'])-center)[None])[0].tolist()
   if not r['eligible']:r['reason']='Insufficient full-scene depth-consistent visible centers'
  pool=sorted([r for r in rows[oid] if r.get('eligible')],key=lambda r:r['score'],reverse=True);chosen=[]
  while pool and len(chosen)<cfg['max_views']:
   candidates=[]
   for r in pool:
    angle=180. if not chosen else min(np.rad2deg(np.arccos(np.clip(np.dot(r['direction'],v['direction']),-1,1))) for v in chosen)
    if angle>=cfg['minimum_angle_degrees']:candidates.append((r['score']*(.35+.65*min(angle/45,1)),angle,r))
   if not candidates:break
   _,angle,r=max(candidates,key=lambda v:v[0]);r['minimum_angle_to_previously_selected']=float(angle);r['selection_rank']=len(chosen)+1;chosen.append(r);pool.remove(r)
  selected[oid]=chosen;dest=ctx.path('M2.1',oid);dest.mkdir(exist_ok=True);paths=[]
  for r in chosen:
   im=imap[r['image_id']];pic=Image.fromarray(ctx.rgb(im));draw=ImageDraw.Draw(pic);draw.rectangle(r['bbox'],outline='#ffae24',width=4);pic.thumbnail((960,600));path=dest/(r['image_id']+'_prompt.jpg');save_image(path,pic);paths.append(path)
  sheet(paths,dest/'selected_views.jpg',labels=[r['image_id'] for r in chosen]);all_paths+=paths[:1]
  print('M2.1 selected',o['name_en'],len(chosen),flush=True)
 write(ctx.path('M2.1','all_view_rankings.json'),rows);write(ctx.path('M2.1','selected_views.json'),selected);sheet(all_paths,ctx.path('M2.1','selection_overview.jpg'))
 return dict(objects=len(objects),training_views=len(train),full_scene_depth_views=len(union),selected_observations=sum(map(len,selected.values())),views_per_object={k:len(v) for k,v in selected.items()},depth_method='Complete native 3DGS alpha-normalized Z/Z^2 moments via three precomputed color channels; exact original camera K; not 2DGS surface depth',shortlist_policy='All training cameras receive geometric scores; full-scene visibility evaluated for top geometric shortlist per object; remaining views explicitly not evaluated')
