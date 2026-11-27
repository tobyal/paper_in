"""Independent M0 geometry audit and RGB prompts. Does not read retrieval outputs."""
from common import *
import datetime, collections
from m0.spatial import corners
from industrial_world_model.hybrid_views.geometry import box_projection
check_frozen()
out=ROOT/'evaluation/pseudo_ground_truth';out.mkdir(parents=True,exist_ok=True)
objects=read(ROOT/'inputs/objects.json');queries=read(ROOT/'configs/benchmark_queries.json');views=read(ROOT/'configs/evaluation_views.json')['cameras'];T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform'])
bounds={o['object_id']:(corners(o['bbox']).min(0),corners(o['bbox']).max(0)) for o in objects}
labels={o['object_id']:f'O{i:02d}' for i,o in enumerate(objects,1)}
audit=[];needed=collections.defaultdict(set)
for q in queries:
    pool=[o for o in objects if o['category_id']==q['subject_category_id']];anchors=[o for o in objects if o['category_id']==q['object_category_id']];pairs=[];targets=[]
    for obj in pool:
        lo,hi=bounds[obj['object_id']];matches=[]
        for anchor in anchors:
            al,ah=bounds[anchor['object_id']];gap=float(np.linalg.norm(np.maximum(np.maximum(al-hi,lo-ah),0)))
            margins=dict(left_of=float(al[0]-hi[0]-.02),right_of=float(lo[0]-ah[0]-.02),in_front_of=float(lo[1]-ah[1]-.02),behind=float(al[1]-hi[1]-.02),near=.35-gap)
            margin=margins[q['predicate_ours']];valid=margin>0
            pairs.append(dict(subject=obj['object_id'],anchor=anchor['object_id'],matches=valid,margin=margin,aabb_gap=gap,subject_center=obj['bbox']['center'],anchor_center=anchor['bbox']['center']))
            if valid:matches.append(anchor['object_id'])
        if matches:targets.append(obj['object_id'])
    for iid in q['evaluation_camera_ids']:needed[iid].update(targets)
    audit.append(dict(query_id=q['query_id'],query_en=q['query_en'],target_ids=targets,anchor_ids=[a['object_id'] for a in anchors],all_candidate_pairs=pairs,selection='Independently recomputed directly from M0 OBB geometry; no Ours graph/query output read',review_status='awaiting_RGB_layout_review'))
write(out/'target_audit.json',audit)
tasks=[]
for iid,oids in sorted(needed.items()):
    c=views[iid];rgb=Image.open(PROJECT/'data/images'/c['filename']).convert('RGB').resize((c['width'],c['height']));save(out/'rgb'/(iid+'.png'),rgb)
    for o in objects:
        if o['object_id'] not in oids:continue
        projection=box_projection(o['bbox'],T,c)
        task=dict(task_id=f'T{len(tasks)+1:03d}',camera_id=iid,object_id=o['object_id'],label=labels[o['object_id']],name=o['name_en'],name_zh=o['name_zh'],projection=projection,queries=[q['query_id'] for q,a in zip(queries,audit) if iid in q['evaluation_camera_ids'] and o['object_id'] in a['target_ids']],points=[],point_labels=[])
        tasks.append(task)
write(out/'tasks.json',tasks)
write(out/'protocol.json',dict(reference_type='SAM-assisted Pseudo-GT',independent_human_ground_truth=False,reviewer='Codex visual review',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sam_checkpoint=str(PROJECT/'models/sam/sam_vit_h_4b8939.pth'),sam_model='vit_h',pixels=[938,528],target_identity_basis='Original RGB, M0 labels and separately recomputed OBB relations; no retrieval output used',relation_rules=dict(axis_gap=.02,near_aabb_gap=.35,frame='+X right, +Y front, +Z up'),mask_basis='Fresh SAM inference on original held-out RGB with projected boxes and visually specified positive/negative points; no model prediction masks',empty_prediction_precision=0,empty_prediction_recall=0,invisible_or_unreliable='Excluded identically for all methods',averaging='Mean valid views per query then equal query mean',limitations=['M0-derived target semantics share priors with Ours; not independent human truth','SAM has difficulty with holes, fine rods, material changes and occlusion'],source_hashes={str(p.relative_to(ROOT)):sha(p) for p in [ROOT/'inputs/objects.json',ROOT/'inputs/m0_state.json',ROOT/'configs/FROZEN.json']}))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
canvas=Image.new('RGB',(1300,1200),'white');d=ImageDraw.Draw(canvas)
allpts=np.concatenate([corners(o['bbox']) for o in objects]);low=allpts[:,:2].min(0)-.4;high=allpts[:,:2].max(0)+.4
def pix(x):return (int(80+(x[0]-low[0])/(high[0]-low[0])*1100),int(1100-(x[1]-low[1])/(high[1]-low[1])*1000))
for o in objects:
    lo,hi=bounds[o['object_id']];a=pix([lo[0],hi[1]]);b=pix([hi[0],lo[1]]);d.rectangle([a,b],outline='blue',width=2);d.text(pix(o['bbox']['center']),labels[o['object_id']],fill='black',font=font)
d.text((30,20),'M0 layout: +X right / +Y front (up on map). Labels are IDs, not GT.',font=font,fill='black');save(out/'layout.jpg',canvas)
write(out/'object_labels.json',[dict(label=labels[o['object_id']],object_id=o['object_id'],name=o['name_en'],category_id=o['category_id'],bbox=o['bbox']) for o in objects])
print('TASKS',len(tasks),'projected',sum(t['projection'] is not None for t in tasks),'cameras',len(needed),'queries',len(audit),flush=True)
