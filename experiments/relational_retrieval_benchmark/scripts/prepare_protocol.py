import argparse,collections,datetime
from common import *
from industrial_world_model.render import Renderer
from industrial_world_model.hybrid_views.geometry import box_projection

p=argparse.ArgumentParser();p.add_argument('--freeze',action='store_true');args=p.parse_args()
if args.freeze:
    files=['benchmark_queries.json','category_mapping.json','relation_mapping.json','evaluation_views.json','methods.json']
    assert not (ROOT/'configs/FROZEN.json').exists()
    write(ROOT/'configs/FROZEN.json',dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256={name:sha(ROOT/'configs'/name) for name in files},selection_uses_method_predictions=False,gt='pending_independent_review',visual_review='Codex inspected original RGB contact sheet and existing equipment reference RGB; not human truth'))
    print('FROZEN',read(ROOT/'configs/FROZEN.json'));raise SystemExit
assert not (ROOT/'configs/FROZEN.json').exists()
objects=read(ROOT/'inputs/objects.json');byid={o['object_id']:o for o in objects};cats=read(V2/'world_model/categories.json');graph=read(V2/'world_model/scene_graph.json');quality={n['object_id']:n for n in graph['nodes']};T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform'])
relations=[('left_of','left of','left','左侧'),('right_of','right of','right','右侧'),('in_front_of','in front of','front','前方'),('behind','behind','behind','后方'),('near','near','close by','附近')]
category_map=[dict(category_id=c['category_id'],zh=c['name_zh'],en=c['name_en'],instances=sum(o['category_id']==c['category_id'] for o in objects)) for c in cats];write(ROOT/'configs/category_mapping.json',category_map);write(ROOT/'configs/relation_mapping.json',[dict(ours=r,english=e,relags=p,zh=z,frame='industrial +X right +Y front +Z up',anchor_semantics='union_over_matching_anchors') for r,e,p,z in relations])
queries=[];target_usage=collections.Counter();anchor_usage=collections.Counter();selection=[]
for relation,en,predicate,zh in relations:
    pool=[]
    for subject in category_map:
        candidates={o['object_id'] for o in objects if o['category_id']==subject['category_id']}
        for anchor in category_map:
            if subject['category_id']==anchor['category_id']:continue
            anchors={o['object_id'] for o in objects if o['category_id']==anchor['category_id']};expected={e['subject'] for e in graph['edges'] if e['relation']==relation and e['subject'] in candidates and e['object'] in anchors}
            if 0<len(expected)<len(candidates):pool.append(dict(subject=subject,anchor=anchor,targets=sorted(expected),candidates=sorted(candidates)))
    used_targets=set();chosen=[]
    while pool and len(chosen)<5:
        def score(row):
            cid=row['subject']['category_id'];aid=row['anchor']['category_id'];fraction=len(row['targets'])/len(row['candidates']);return (cid not in used_targets,-target_usage[cid],-anchor_usage[aid],1-fraction,-len(row['targets']),cid,aid)
        row=max(pool,key=score);pool.remove(row);chosen.append(row);used_targets.add(row['subject']['category_id']);target_usage[row['subject']['category_id']]+=1;anchor_usage[row['anchor']['category_id']]+=1
    selection.append(dict(relation=relation,discriminative_candidates=len(pool)+len(chosen),selected=len(chosen)))
    for row in chosen:
        s=row['subject'];o=row['anchor'];phrase='to the '+en if en in ['left of','right of'] else en
        queries.append(dict(query_id=f'Q{len(queries)+1:03d}',subject_category=s['en'],subject_category_id=s['category_id'],predicate=en,predicate_ours=relation,predicate_relags=predicate,object_category=o['en'],object_category_id=o['category_id'],query_en=s['en']+' '+phrase+' the '+o['en'],query_zh='位于'+o['zh']+zh+'的'+s['zh'],anchor_semantics='union_over_matching_anchors',evaluation_camera_ids=[],query_selection_reason=f'M0-only candidate union reduces {len(row["candidates"])} same-class devices to {len(row["targets"])}; balance target/anchor classes before method predictions',ground_truth_status='pending_independent_review'))
        write(ROOT/'inputs/candidate_references'/(queries[-1]['query_id']+'.json'),dict(target_ids=row['targets'],same_class_ids=row['candidates'],source='Frozen M0 geometry, NOT independent truth',quality=[dict(object_id=oid,reconstruction=quality[oid]['reconstruction_status'],extraction=quality[oid]['extraction_status']) for oid in row['targets']]))
class Ctx:
    project=PROJECT
    state=read(ROOT/'inputs/m0_state.json')
renderer=Renderer(Ctx());cameras=[c for c in read(ROOT/'inputs/cameras.json') if c['split']!='train'];assert len(cameras)==44
visibility={};cand={o['object_id']:np.load(ROOT.parent/'saga_relags_v1/inputs/geometry/object_candidates'/o['object_id']/'gaussian_ids.npy') for o in objects}
for source in cameras:
    c=scaled_camera(source,469,264);row={}
    for obj in objects:
        projection=box_projection(obj['bbox'],T,c)
        row[obj['object_id']]=dict(pixels=int((renderer.contribution(c,cand[obj['object_id']])>.5).sum()) if projection else 0,coverage=projection['image_coverage'] if projection else 0)
    visibility[c['image_id']]=row
write(ROOT/'inputs/coarse_visibility_for_camera_selection.json',dict(views=visibility,width=469,height=264,source='Raw scene + M0 coarse candidates only; not SAGA or external method output',truth=False))
allviews={};panels=[]
for q in queries:
    targets=read(ROOT/'inputs/candidate_references'/(q['query_id']+'.json'))['target_ids'];chosen=[];seen=set()
    for index in range(3):
        def score(c):
            row=visibility[c['image_id']];valid=[oid for oid in targets if row[oid]['pixels']>=50 and row[oid]['coverage']>=.35]
            return (len(set(valid)-seen),sum(np.log1p(row[oid]['pixels'])*min(row[oid]['coverage'],1) for oid in targets))
        eligible=[c for c in cameras if c not in chosen and (not chosen or min(np.linalg.norm(np.array(c['center'])-old['center']) for old in chosen)>.35)]
        if not eligible:break
        best=max(eligible,key=score)
        if index==2 and score(best)[0]==0:break
        chosen.append(best);seen.update(oid for oid in targets if visibility[best['image_id']][oid]['pixels']>=50 and visibility[best['image_id']][oid]['coverage']>=.35)
    assert len(chosen)>=2
    q['evaluation_camera_ids']=[c['image_id'] for c in chosen]
    for c in chosen:allviews[c['image_id']]=scaled_camera(c)
    q['camera_selection_note']='Greedy M0-coarse visible coverage with >=0.35 camera-center separation; fixed before predictions. 3rd view only if it adds a candidate target.'
write(ROOT/'configs/benchmark_queries.json',queries);write(ROOT/'configs/evaluation_views.json',dict(width=938,height=528,cameras=allviews,original_heldout_count=44,common_split=True));write(ROOT/'inputs/query_selection_audit.json',dict(relations=selection,target_class_counts=dict(target_usage),anchor_class_counts=dict(anchor_usage),queries=len(queries),views=len(allviews)))
methods=dict(langsplat=dict(model='frozen 3 levels iteration30000',query='official full-English-description relevancy',negatives=['object','things','stuff','texture'],temperature=10,layer_selection='official maximum smoothed relevancy, no GT',mean_filter=30,mask_threshold=.4,threshold_rule='official eval/eval.sh and evaluate_iou_loc.py default verified 0.4',m0=False),thgs=dict(model='unpruned 2DGS iteration30000',official_config='configs/lerf.yml',query_topk=3,query_levels=[2,3],contribution_threshold=.5,m0=False),relags=dict(model='R1 hierarchy/semantics/weights; coordinate-aligned geometry prediction copy',topk=10,filter_small=300,sim_thresholds=[.55,.4,.55],max_subjects=3,contribution_threshold=.5,m0_device_priors=False,global_coordinate_calibration='Rigid industrial axes shared for directional meaning; no equipment boxes/classes supplied'),ours=dict(model='frozen saga_relags_v2',m0=True,graph_nodes=33,fine_available=30,contribution_threshold=.5),timing=dict(hardware='RTX A6000',warmup=1,repetitions=3,report_load_query_render_end_to_end_separately=True),metrics=dict(projection_miou='Pending GT',precision='Pending GT',recall='Pending GT',averaging='mean over GT-valid views per query, then equal query mean'))
write(ROOT/'configs/methods.json',methods)
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',18)
ids=list(allviews);chosen_ids=[ids[i] for i in np.linspace(0,len(ids)-1,min(12,len(ids))).astype(int)];canvas=Image.new('RGB',(1600,4*340),'#14212b');draw=ImageDraw.Draw(canvas)
for i,iid in enumerate(chosen_ids):
    c=allviews[iid];im=Image.open(PROJECT/'data/images'/c['filename']).convert('RGB');im.thumbnail((533,300));x=i%3*533;y=i//3*340;canvas.paste(im,(x,y));draw.text((x+8,y+305),iid+' original held-out RGB',font=font,fill='white')
save(ROOT/'docs/figures/protocol_original_rgb.jpg',canvas);print('PROPOSED PROTOCOL',read(ROOT/'inputs/query_selection_audit.json'),flush=True)

