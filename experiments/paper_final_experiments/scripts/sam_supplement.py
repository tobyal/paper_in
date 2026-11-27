from common import *
verify_locks();old=PROJECT/'outputs/industrial_world_model/baseline_20261126_r29';oldobjects=read(old/'M1_spatial_constraint/objects.json');objects=read(V2/'inputs/objects.json');omap={o['object_id']:o for o in oldobjects};records={o['object_id']:o for o in read(old/'M2_object_modeling/M2_4_instance_extraction/instances.json')}
assert np.array_equal(np.load(old/'M1_spatial_constraint/scene/xyz_raw.npy'),np.load(V1/'inputs/geometry/xyz_raw.npy'))
for o in objects:
    oo=omap[o['object_id']];assert o['bbox']==oo['bbox'];assert np.array_equal(candidates(o['object_id']),np.load(old/oo['candidate_ids']))
train={c['image_id'] for c in read(V2/'inputs/cameras.json') if c['split']=='train'};used={p.name.split('_prompt')[0] for p in (old/'M2_object_modeling/M2_1_view_selection').rglob('*_prompt.jpg')};heldout=used-train
wm=world_model();ours={o['object_id'] for o in wm.objects if o['segmentation_available']};sam={oid for oid,o in records.items() if o['valid']};common=sam&ours
audit=dict(m0_boxes_exact=True,coarse_gaussian_ids_exact=True,source_xyz_exact=True,source=str(old),sam_available=len(sam),ours_available=len(ours),common_available=len(common),sam_used_cameras=sorted(used),heldout_intersection=sorted(heldout),allowed=not heldout,common_ids=sorted(common))
write(ROOT/'E02_ablation/multiview_sam_compatibility.json',audit)
if heldout:print('Supplement deferred: heldout leakage in historical views');sys.exit(0)
r=renderer();views=read(BENCH/'configs/evaluation_views.json')['cameras']
for q in read(BENCH/'configs/benchmark_queries.json'):
    raw=wm.query(q['query_zh'])
    for variant,eligible,source in [('sam_original',sam,'sam'),('sam_common',common,'sam'),('ours_common',common,'ours')]:
        d=ROOT/'E02_ablation/predictions'/variant/q['query_id'];d.mkdir(parents=True,exist_ok=True)
        if (d/'result.json').exists():continue
        oids=[oid for oid in raw['matched_object_ids'] if oid in eligible];ids=union([np.load(old/records[oid]['gaussian_indices']) if source=='sam' else fine(oid) for oid in oids]);np.save(d/'gaussian_indices.npy',ids);vr=[]
        for iid in q['evaluation_camera_ids']:
            c=views[iid];soft=r.contribution(c,ids);mask=soft>.5;np.savez_compressed(d/(iid+'_response.npz'),response=soft);save(d/iid/'mask.png',mask.astype(np.uint8)*255);save(d/iid/'overlay.jpg',overlay(rgb(c),mask));write(d/iid/'camera.json',c);vr.append(dict(camera_id=iid,mask_pixels=int(mask.sum())))
        write(d/'result.json',dict(status='completed',variant=variant,query_id=q['query_id'],returned_object_ids=oids,gaussian_count=len(ids),views=vr,source='historical multiview SAM fusion' if source=='sam' else 'frozen v2 on shared availability'))
    print('SAM supplement',q['query_id'],flush=True)
