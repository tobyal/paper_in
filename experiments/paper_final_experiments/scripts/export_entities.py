from common import *
import torch,shutil
import matplotlib;matplotlib.use('Agg')
from matplotlib import cm
from m0.native_3dgs import subset_model
from industrial_world_model.hybrid_views.geometry import box_projection
verify_locks();r=renderer();T=np.array(Context.state['scene']['transform']);objs=read(V2/'inputs/objects.json');byid={o['object_id']:o for o in objs};quality={o['object_id']:o for o in read(V2/'outputs/A/final_summary.json')['objects']}
selected=[objs[i]['object_id'] for i in [0,8,6,23,10]]
write(ROOT/'configs/entity_cases.json',dict(objects=selected,reason='Assembly fixture, open multi-tier rack with overlap conflicts, material cart, partial compartmented rack, unavailable blue-bin limitation; no tuning.'))
def isolated(c,ids,colors=None):
    if not len(ids):return np.full((c['height'],c['width'],3),255,np.uint8)
    model=subset_model(r.model,ids)
    with torch.inference_mode():
        alpha=r.pass_colors(c,torch.ones((len(ids),3),device='cuda'),model=model).permute(1,2,0).cpu().numpy()
        if colors is None:base=r.rgb(c,ids).astype(float)/255
        else:base=r.pass_colors(c,torch.tensor(colors,dtype=torch.float32,device='cuda'),model=model).permute(1,2,0).cpu().numpy()
    return ((base+1-alpha).clip(0,1)*255+.5).astype(np.uint8)
def crop(im,proj):
    x0,y0,x1,y1=proj['bbox'];pad=.12*max(x1-x0,y1-y0);return Image.fromarray(im).crop((max(0,int(x0-pad)),max(0,int(y0-pad)),min(im.shape[1],int(x1+pad)),min(im.shape[0],int(y1+pad))))
summary=[]
for oid in selected:
    dest=ROOT/'E03_entity_construction/objects'/oid;dest.mkdir(parents=True,exist_ok=True);source=V2/'outputs/A/extractions/refined/objects'/oid;obj=byid[oid];cand=candidates(oid);ids=fine(oid);score=np.load(source/'affinity_scores.npy',mmap_mode='r')[cand].astype(np.float32);pre=np.load(source/'selected_before_conflicts.npy');lost=np.load(source/'lost_conflict_ids.npy');prompt=read(source/'prompt.json')
    assert np.isfinite(score).all() and score.min()>=0 and score.max()<=1;assert np.all(np.isin(ids,pre));assert np.array_equal(np.setdiff1d(pre,ids),lost)
    xyz=r.model.get_xyz.detach().cpu().numpy()[cand];industrial=xyz@T[:3,:3].T+T[:3,3]
    np.savez_compressed(dest/'actual_intermediates.npz',gaussian_ids=cand,xyz_raw=xyz,xyz_industrial=industrial,affinity=score,selected_before_conflicts=np.isin(cand,pre),final_selected=np.isin(cand,ids),lost_conflict=np.isin(cand,lost))
    for name in ['prompt.json','prompt_features.npy','selected_before_conflicts.npy','gaussian_indices.npy','lost_conflict_ids.npy']:shutil.copy2(source/name,dest/name)
    prompt_exports=[]
    for j,p in enumerate(prompt['prompts']):
        c=p['camera'];maskpath=Path(p['mask_source']);maskpath=maskpath if maskpath.is_absolute() else (V1 if quality[oid]['reused_v1'] else V2)/maskpath
        assert maskpath.exists(),str(maskpath)
        mask=np.array(Image.open(maskpath))>0
        if c.get('source_type','real')=='real':image=rgb(c)
        else:
            ip=V1/c['input_path'] if c.get('input_path') else None
            if ip is None or not ip.exists():
                refs=read(V2/'outputs/A/reference_prompts/records.json')+read(V2/'outputs/A/refinement_prompts/records.json');match=next(v for v in refs if v['object_id']==oid and v['image_id']==p['image_id']);ip=Path(match['image_path'])
            image=np.array(Image.open(ip).convert('RGB').resize((c['width'],c['height'])))
        assert mask.shape==image.shape[:2];d=dest/'prompts'/f'{j:02d}';save(d/'rgb.png',image);save(d/'mask.png',mask.astype(np.uint8)*255);im=Image.fromarray(overlay(image,mask,(40,185,85)));draw=ImageDraw.Draw(im)
        for x,y in p['pixels_xy']:draw.ellipse((x-4,y-4,x+4,y+4),fill=(255,235,0),outline=(0,0,0),width=1)
        save(d/'overlay.png',im);projection=box_projection(obj['bbox'],T,c);save(d/'crop.png',crop(np.array(im),projection));write(d/'camera_and_points.json',p);prompt_exports.append(dict(directory=str(d.relative_to(ROOT)),original_mask=str(maskpath),mask_sha256=sha(maskpath),source_type=c.get('source_type',p.get('source_type','real'))))
    c=scaled(prompt['prompts'][0]['camera'],1500);projection=box_projection(obj['bbox'],T,c)
    if c.get('source_type','real')=='real':image=rgb(c)
    else:image=np.array(Image.open(dest/'prompts/00/rgb.png').resize((c['width'],c['height'])))
    for name,im in [('original',image),('scene',r.rgb(c)),('coarse_projection',overlay(image,r.contribution(c,cand)>.5)),('fine_projection',overlay(image,r.contribution(c,ids)>.5))]:save(dest/(name+'.png'),im);save(dest/(name+'_crop.png'),crop(im,projection))
    write(dest/'real_camera.json',c);write(dest/'crop.json',projection)
    for axis in ['oblique','side','top']:
        cam=r.virtual(obj['bbox']['center'],obj['bbox']['size'],axis,width=1200);write(dest/f'{axis}_camera.json',cam)
        for name,selection,colors in [('coarse',cand,None),('refined',ids,None),('removed',np.setdiff1d(cand,ids),None),('affinity',cand,cm.get_cmap('viridis')(score)[:,:3]),('threshold',pre,None)]:save(dest/f'{name}_{axis}.png',isolated(cam,selection,colors))
    row=dict(object_id=oid,name_en=obj['name_en'],display_id=f'O{objs.index(obj)+1:02d}',candidate_gaussians=len(cand),before_conflicts=len(pre),final_gaussians=len(ids),removed_gaussians=len(cand)-len(ids),lost_conflicts=len(lost),retained_fraction=len(ids)/len(cand),affinity_min=float(score.min()),affinity_max=float(score.max()),score_storage='float16 from frozen v2; float32 threshold membership retained separately',threshold=prompt['threshold'],normalized_scale=prompt['normalized_scale'],source=str(source),source_score_sha256=sha(source/'affinity_scores.npy'),prompts=prompt_exports,quality=quality[oid]);summary.append(row);write(dest/'provenance.json',row);print('Entity export',row['display_id'],len(cand),len(ids),flush=True)
write(ROOT/'E03_entity_construction/summary.json',summary)
