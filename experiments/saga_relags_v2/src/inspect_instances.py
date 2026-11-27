"""Render every attempted object, including empty and difficult instances."""
import argparse,cv2
from common import *
from industrial_world_model.render import Renderer
from industrial_world_model.hybrid_views.geometry import box_projection

p=argparse.ArgumentParser();p.add_argument('--tag',default='initial');a=p.parse_args()
folder=ROOT/'outputs/A/extractions'/a.tag;summary=read(folder/'summary.json');objects={o['object_id']:o for o in read(ROOT/'inputs/objects.json')}
renderer=Renderer(NativeContext());T=np.array(renderer.ctx.state['scene']['transform']);refs=read(ROOT/'outputs/A/reference_prompts/records.json')
oldrefs=read(V1/'outputs/A/reference_prompts/records.json');oldcams={c['image_id']:c for c in read(ROOT/'inputs/training_cameras.json')}
selection=read(ROOT/'outputs/A/reference_prompts/view_selection.json');gallery=[];labels=[];category={};review=[]
def crop(rgb,projection):
    if not projection:return Image.fromarray(rgb)
    x0,y0,x1,y1=np.array(projection['bbox']).astype(float);dx=(x1-x0)*.10;dy=(y1-y0)*.10
    return Image.fromarray(rgb).crop((max(0,int(x0-dx)),max(0,int(y0-dy)),min(rgb.shape[1],int(x1+dx)),min(rgb.shape[0],int(y1+dy))))
for index,row in enumerate(summary['objects']):
    oid=row['object_id'];obj=objects[oid];ids=np.load(ROOT/row['gaussian_indices']);candidates=candidate_ids(oid);dest=folder/'objects'/oid/'visualizations';dest.mkdir(parents=True,exist_ok=True)
    viewpaths=[]
    for axis in ['oblique','side','top']:
        cam=renderer.virtual(obj['bbox']['center'],obj['bbox']['size'],axis,width=640)
        save(dest/(axis+'.jpg'),renderer.rgb(cam,ids));save(dest/('coarse_'+axis+'.jpg'),renderer.rgb(cam,candidates));write(dest/(axis+'_camera.json'),cam)
        viewpaths.append(dest/(axis+'.jpg'))
    possible=[r for r in refs if r['object_id']==oid];possible.sort(key=lambda r:(r['source_type']=='real',r['accepted'],r['visible_pixels']),reverse=True)
    if not possible:
        for r in oldrefs:
            if r['object_id']==oid and r['accepted']:
                rr=dict(r);rr['image_path']=str(V1/oldcams[r['image_id']]['input_path']);rr['camera']=oldcams[r['image_id']];rr['source_type']=oldcams[r['image_id']]['source_type'];possible.append(rr)
        possible.sort(key=lambda r:r['source_type']=='real',reverse=True)
    representative=possible[0] if possible else None
    if representative:
        cam=scaled_camera(representative['camera'],1200);rgb=np.array(Image.open(representative['image_path']).convert('RGB').resize((cam['width'],cam['height'])))
        projection=box_projection(obj['bbox'],T,cam);rendered=renderer.rgb(cam);contribution=renderer.contribution(cam,ids);mask=contribution>.5
        overlay=rgb.copy();overlay[mask]=(overlay[mask]*.45+[140,10,0]).clip(0,255).astype(np.uint8)
        for name,im in [('real_crop',rgb),('full_scene_crop',rendered),('projection_crop',overlay)]:save(dest/(name+'.jpg'),crop(im,projection))
        save(dest/'training_overlay.jpg',overlay);save(dest/'training_mask.png',mask.astype(np.uint8)*255);np.savez_compressed(dest/'training_contribution.npz',contribution=contribution)
        write(dest/'training_camera.json',cam)
        row['review_image_id']=representative['image_id'];row['review_source_type']=representative['source_type'];row['training_visible_pixels']=int(mask.sum())
    else:
        for name in ['real_crop','full_scene_crop','projection_crop']:save(dest/(name+'.jpg'),np.zeros((300,300,3),np.uint8))
    compare=[dest/'real_crop.jpg',dest/'full_scene_crop.jpg',dest/'coarse_oblique.jpg',dest/'oblique.jpg',dest/'side.jpg',dest/'top.jpg',dest/'projection_crop.jpg']
    comparelabels=['Original train RGB / '+oid[-6:],'Full native scene (same camera)','M0 crop - NOT truth','SAGA oblique / '+obj['name_en'],'SAGA side','SAGA top','Frozen instance projection']
    grid(compare,dest/'comparison.jpg',labels=comparelabels,columns=7,tile=(350,300))
    gallery.extend([dest/'coarse_oblique.jpg',*viewpaths]);labels.extend([obj['name_en']+' / M0',obj['name_en']+' / SAGA',oid+' / side',oid+' / top'])
    category.setdefault(obj['category_id'],[]).append(dest/'comparison.jpg')
    review.append(dict(object_id=oid,name_en=obj['name_en'],comparison=str((dest/'comparison.jpg').relative_to(ROOT)),representative_training_view=row.get('review_image_id'),gaussian_count=len(ids),candidate_count=len(candidates)))
    # Prompt inspection crops contain green positive points and actual SAM overlays.
    rc=[r for r in refs if r['object_id']==oid];pp=[];pl=[]
    for r in rc:
        rd=ROOT/'outputs/A/reference_prompts'/oid/r['image_id'];im=np.array(Image.open(rd/'overlay.jpg'));target=dest/('prompt_'+r['image_id']+'.jpg');save(target,crop(im,r['projection']));pp.append(target);pl.append(r['image_id']+' accepted='+str(r['accepted']))
    if pp:grid(pp,dest/'prompt_review.jpg',labels=pl,columns=3,tile=(480,350))
    print('INSPECT',obj['name_en'],len(ids),flush=True)
for cid,paths in category.items():
    images=[Image.open(path) for path in paths];canvas=Image.new('RGB',(images[0].width,sum(im.height for im in images)),'#15212d');y=0
    for im in images:canvas.paste(im,(0,y));y+=im.height
    save(folder/'review'/f'{cid}.jpg',canvas)
grid(gallery,folder/'all_instances.jpg',labels=labels,columns=4,tile=(360,300));write(folder/'inspection.json',review);write(folder/'summary.json',summary)
