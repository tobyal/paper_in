from common import *
import torch,shutil
import matplotlib;matplotlib.use('Agg')
from matplotlib import cm
from m0.native_3dgs import subset_model
verify_locks();wm=world_model();r=renderer();objects=read(V2/'inputs/objects.json');byid={o['object_id']:o for o in objects};T=np.array(Context.state['scene']['transform']);views=read(BENCH/'configs/evaluation_views.json')['cameras'];queries={q['query_id']:q for q in read(BENCH/'configs/benchmark_queries.json')}
colors={o['object_id']:list(cm.get_cmap('tab20')(i%20)[:3]) if i<20 else list(cm.get_cmap('tab20b')((i-20)%20)[:3]) for i,o in enumerate(objects)}
write(ROOT/'configs/object_colors.json',colors)
def bounds(oids):
    centers=np.array([byid[o]['bbox']['center'] for o in oids]);sizes=np.array([byid[o]['bbox']['size'] for o in oids]);lo=(centers-sizes/2).min(0);hi=(centers+sizes/2).max(0);return (lo+hi)/2,hi-lo
def white_rgb(cam,ids):
    if not len(ids):return np.full((cam['height'],cam['width'],3),255,np.uint8)
    model=subset_model(r.model,ids)
    with torch.inference_mode():alpha=r.pass_colors(cam,torch.ones((len(ids),3),device='cuda'),model=model).permute(1,2,0).cpu().numpy()
    return ((r.rgb(cam,ids).astype(float)+255*(1-alpha)).clip(0,255)+.5).astype(np.uint8)
scene=ROOT/'E04_relation_retrieval/scene';scene.mkdir(parents=True,exist_ok=True);available=[o['object_id'] for o in wm.objects if o['segmentation_available']];ids=union([fine(o) for o in available]);groups=[(fine(o),colors[o]) for o in available]
write(scene/'nodes.json',wm.objects);write(scene/'edges.json',wm.graph['edges']);write(scene/'identity_colors.json',[dict(object_id=o['object_id'],display_id=f'O{i+1:02d}',color=colors[o['object_id']],fine_available=o['object_id'] in available) for i,o in enumerate(objects)])
for iid in ['frame_000329','frame_000113']:
    c=scaled(views[iid],1800);save(scene/(iid+'_rgb.png'),rgb(c));save(scene/(iid+'_native.png'),r.rgb(c));save(scene/(iid+'_instances.png'),r.highlight(c,groups));write(scene/(iid+'_camera.json'),c)
center,size=bounds([o['object_id'] for o in objects])
for axis in ['oblique','top']:
    c=r.virtual(center,size,axis,width=1800);save(scene/(axis+'_instances.png'),white_rgb(c,ids));write(scene/(axis+'_camera.json'),c)
    model=subset_model(r.model,ids);lookup=np.zeros((len(r.model.get_xyz),3),np.float32)
    for oid in available:lookup[fine(oid)]=colors[oid]
    with torch.inference_mode():
        colored=r.pass_colors(c,torch.tensor(lookup[ids],device='cuda'),model=model).permute(1,2,0).cpu().numpy();alpha=r.pass_colors(c,torch.ones((len(ids),3),device='cuda'),model=model).permute(1,2,0).cpu().numpy()
    save(scene/(axis+'_colored.png'),((colored+1-alpha).clip(0,1)*255+.5).astype(np.uint8))
xyz=r.model.get_xyz.detach().cpu().numpy();pts=xyz@T[:3,:3].T+T[:3,3];lo=center-size*.65;hi=center+size*.65;idx=np.where(((pts>lo)&(pts<hi)).all(1))[0][::12];dc=r.model.get_features.detach().cpu().numpy()[:,0,:]*.28209479177387814+.5
np.savez_compressed(scene/'native_scene_display_points.npz',xyz=pts[idx],rgb=dc[idx].clip(0,1),original_ids=idx)
cams=read(V2/'inputs/cameras.json');write(scene/'original_cameras.json',cams)
for qid in ['Q003','Q006']:
    q=queries[qid];raw=wm.query(q['query_zh']);fixed=wm.gaussian_ids(raw);d=ROOT/'E05_multiview_application/multiview'/qid;d.mkdir(parents=True,exist_ok=True);np.save(d/'fixed_gaussian_ids.npy',fixed);write(d/'query.json',raw);center,size=bounds(raw['matched_object_ids']);records=[]
    for axis in ['oblique','side','top']:
        c=r.virtual(center,size,axis,width=1500);dest=d/axis;save(dest/'scene.png',r.rgb(c));save(dest/'highlight.png',r.highlight(c,[(fixed,[.95,.25,.12])]+[(fine(o),[.1,.65,.85]) for o in raw['anchor_object_ids'] if o in available]));save(dest/'isolated.png',white_rgb(c,fixed));soft=r.contribution(c,fixed);np.savez_compressed(dest/'contribution.npz',response=soft);write(dest/'camera.json',c);records.append(dict(axis=axis,camera=c,visible_pixels=int((soft>.5).sum()),same_ids_sha256=sha(d/'fixed_gaussian_ids.npy')))
    write(d/'views.json',records);print('Multiview',qid,[(v['axis'],v['visible_pixels']) for v in records],flush=True)
near_cases=[(0,'material cart'),(14,'upright portable air cooler'),(23,'multi-tier material rack'),(12,'material cart'),(1,'group of blue storage bins')];nearest=[]
for i,(anchor_index,category_en) in enumerate(near_cases):
    anchor=objects[anchor_index];category_id=wm.identify(category_en)[0]
    # Use the category's registered English alias, verified by the frozen parser.
    assert category_id,category_en
    text=category_en+' nearest to '+anchor['name_en'];raw=wm.query(text);assert raw['status']=='ok',(text,raw)
    ac=np.array(anchor['bbox']['center']);ranking=[]
    for oid in raw['known_category_instances']:
        if oid==anchor['object_id']:continue
        ranking.append(dict(object_id=oid,name_en=byid[oid]['name_en'],center_distance=float(np.linalg.norm(np.array(byid[oid]['bbox']['center'])-ac)),fine_available=oid in available))
    ranking.sort(key=lambda x:x['center_distance']);expected={x['object_id'] for x in ranking if x['center_distance']-ranking[0]['center_distance']<=1e-6};assert expected==set(raw['matched_object_ids'])
    fixed=wm.gaussian_ids(raw);d=ROOT/'E05_multiview_application/nearest'/f'N{i+1:02d}';d.mkdir(parents=True,exist_ok=True);np.save(d/'gaussian_ids.npy',fixed)
    view_ids=fixed if len(fixed) else union([candidates(o) for o in raw['matched_object_ids']]);stats=[(int((r.contribution(c,view_ids)>.5).sum()),iid) for iid,c in views.items()];pixels,iid=max(stats);c=scaled(views[iid],1500)
    save(d/'original.png',rgb(c));save(d/'scene.png',r.rgb(c));save(d/'highlight.png',r.highlight(c,[(fixed,[.95,.25,.12]),(candidates(anchor['object_id']),[.1,.65,.85])]));save(d/'isolated.png',white_rgb(c,fixed));write(d/'camera.json',c);write(d/'query.json',raw);write(d/'distances.json',ranking)
    row=dict(case_id=f'N{i+1:02d}',query=text,anchor_id=anchor['object_id'],matched_ids=raw['matched_object_ids'],renderable_ids=raw['renderable_object_ids'],unavailable_ids=raw['unavailable_object_ids'],distance_definition='Euclidean distance of frozen M0 centers; SfM relative units; ties 1e-6',ranking=ranking,chosen_camera=iid,view_selection='largest target contribution among existing 29 heldout cameras; coarse only if fine unavailable');nearest.append(row);print('Nearest',row['case_id'],text,raw['matched_object_ids'],flush=True)
write(ROOT/'E05_multiview_application/nearest/summary.json',nearest)
write(ROOT/'E05_multiview_application/difficult_cases.json',[dict(object_id=objects[i]['object_id'],role=role,quality=next(x for x in read(V2/'outputs/A/final_summary.json')['objects'] if x['object_id']==objects[i]['object_id']),related_query=qid,source=str(V2/'outputs/A/extractions/refined/objects'/objects[i]['object_id'])) for i,role,qid in [(23,'partially reconstructed but useful instance','Q012'),(10,'identity localized but fine instance unavailable','Q019'),(14,'partial workbench reconstruction','Q008')]])
print('Scene and application exports complete',flush=True)
