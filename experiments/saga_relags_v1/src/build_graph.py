"""M0 geometry and local ReLaGS-style SoM evidence, lifted by fixed object IDs."""
import collections,base64,time,urllib.request,cv2
from common import *
from m0.spatial import corners,transform
from industrial_world_model.hybrid_views.geometry import box_projection
from industrial_world_model.render import Renderer
out=ROOT/'outputs/C';out.mkdir(parents=True,exist_ok=True)
objects=read(ROOT/'inputs/objects.json');byid={o['object_id']:o for o in objects};T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform']);manifest=read(ROOT/'inputs/manifest.json')
nodes=[];bounds={}
for i,o in enumerate(objects,1):
    pts=corners(o['bbox']);bounds[o['object_id']]=(pts.min(0),pts.max(0))
    nodes.append(dict(object_id=o['object_id'],category_id=o['category_id'],name_zh=o['name_zh'],name_en=o['name_en'],bbox=o['bbox'],display_id=f'O{i:02d}',geometry_source='M0 r29',segmentation_available=False))
edges=[]
def edge(s,r,t,evidence):edges.append(dict(subject=s,relation=r,object=t,source='industrial_geometry',evidence=evidence))
for a in objects:
    aid=a['object_id'];alo,ahi=bounds[aid]
    for b in objects:
        bid=b['object_id']
        if aid==bid:continue
        blo,bhi=bounds[bid];gap=np.maximum(np.maximum(blo-ahi,alo-bhi),0);distance=float(np.linalg.norm(gap));delta=np.array(a['bbox']['center'])-b['bbox']['center']
        ev=dict(aabb_gap=distance,center_delta=delta.tolist(),coordinate_frame='industrial',units='SfM relative units; not meters',extent_source='M0 OBB projected into industrial axes')
        for relation,valid in [('left_of',ahi[0]<blo[0]-.02),('right_of',alo[0]>bhi[0]+.02),('in_front_of',alo[1]>bhi[1]+.02),('behind',ahi[1]<blo[1]-.02)]:
            if valid:edge(aid,relation,bid,ev)
        if distance<.35:edge(aid,'near',bid,ev)
    for cid in sorted({o['category_id'] for o in objects}):
        pool=[o for o in objects if o['category_id']==cid and o['object_id']!=aid]
        if not pool:continue
        distances=[float(np.linalg.norm(np.array(o['bbox']['center'])-a['bbox']['center'])) for o in pool];minimum=min(distances)
        for target,d in zip(pool,distances):
            if d<=minimum+1e-6:edge(target['object_id'],'nearest_to',aid,dict(target_category=cid,center_distance=d,tie_tolerance=1e-6,candidate_distances=[dict(object_id=o['object_id'],distance=x) for o,x in zip(pool,distances)],units='SfM relative units'))
write(out/'geometry_graph.json',dict(nodes=nodes,edges=edges,coordinate_semantics={'+X':'right','+Y':'front','+Z':'up'},rules=dict(axis_gap_margin=.02,near_aabb_gap=.35,nearest='Per target category and anchor, all 33 M0 objects considered.')))

# Choose complementary real training images with clearly visible known objects.
selected=read(PROJECT/manifest['hybrid_observations']/'selected_views.json');cams={c['image_id']:c for c in read(ROOT/'inputs/training_cameras.json') if c['source_type']=='real'};view_objects=collections.defaultdict(list)
for obj in objects:
    for v in selected[obj['object_id']]:
        if v['image_id'] in cams and v['visible_fraction']>.15 and v['image_coverage']>.65:view_objects[v['image_id']].append((obj,v))
chosen=[];covered=set()
for _ in range(6):
    pool=[iid for iid,rows in view_objects.items() if len(rows)>=3 and iid not in chosen]
    if not pool:break
    iid=max(pool,key=lambda iid:sum((1. if o['object_id'] not in covered else .15)*v['visible_fraction'] for o,v in view_objects[iid]));chosen.append(iid);covered.update(o['object_id'] for o,v in view_objects[iid])
renderer=Renderer(NativeContext());attempts=[];accepted_evidence=collections.defaultdict(list)
for iid in chosen:
    folder=out/'som'/iid;folder.mkdir(parents=True,exist_ok=True)
    camera=scaled_camera(cams[iid],width=1500);rgb=np.array(Image.open(ROOT/cams[iid]['input_path']).convert('RGB').resize((camera['width'],camera['height'])));marked=rgb.copy();tags=[]
    rows=sorted(view_objects[iid],key=lambda p:p[1]['visible_fraction'],reverse=True)[:8]
    for obj,v in rows:
        ids=np.load(ROOT/'inputs/geometry/object_candidates'/obj['object_id']/'gaussian_ids.npy');contribution=renderer.contribution(camera,ids);visible=(contribution>.6).astype(np.uint8);dist=cv2.distanceTransform(visible,cv2.DIST_L2,5)
        if dist.max()<2:continue
        y,x=np.unravel_index(dist.argmax(),dist.shape);tag=len(tags)+1;color=(255,220,30)
        contours,_=cv2.findContours(visible,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);cv2.drawContours(marked,contours,-1,color,1)
        cv2.circle(marked,(x,y),17,(15,15,15),-1);cv2.putText(marked,str(tag),(x-9,y+7),cv2.FONT_HERSHEY_SIMPLEX,.7,color,2)
        tags.append(dict(tag=tag,object_id=obj['object_id'],category_id=obj['category_id'],name=obj['name_en'],pixel=[int(x),int(y)],coarse_prior_boundary=True))
    save(folder/'som.jpg',marked);write(folder/'tags.json',tags);write(folder/'camera.json',camera)
    prompt='Inspect the numbered WHOLE industrial devices in this image. The yellow contours are approximate spatial priors, NOT exact object segmentation. Device tags: '+json.dumps(tags)+'. Report ONLY directly visible physical relations between DIFFERENT numbered whole devices: supports, supported_by, contains, inside, covers, covered_by, rests_on. Do not describe parts within a device as another device. Mere adjacency, visual overlap, aligned machinery, or shared function is NOT physical support or containment. Do NOT report left/right/front/behind/near: those are computed in 3D. If no clear relation is visible, return an empty relations list. Return JSON {"relations":[{"subject_tag":1,"relation":"supports","object_tag":2,"confidence":0.9,"evidence":"specific visible contact or containment evidence"}],"observation":"brief explanation"}. Never invent a relation to fill the list.'
    payload=dict(model='qwen3.5:9b',prompt=prompt,images=[base64.b64encode((folder/'som.jpg').read_bytes()).decode()],format='json',stream=False,think=False,options=dict(temperature=0,num_ctx=8192,num_predict=1500),keep_alive='2m');write(folder/'request_metadata.json',{k:v for k,v in payload.items() if k!='images'})
    start=time.time()
    try:
        request=urllib.request.Request('http://127.0.0.1:11434/api/generate',json.dumps(payload).encode(),headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=600) as response:raw=json.load(response)
        write(folder/'raw_response.json',raw);parsed=json.loads(raw['response']);write(folder/'parsed_response.json',parsed);tagmap={t['tag']:t['object_id'] for t in tags};review=[]
        for r in parsed.get('relations',[]):
            reason=None;s=tagmap.get(r.get('subject_tag'));t=tagmap.get(r.get('object_tag'));relation=r.get('relation');confidence=float(r.get('confidence',0))
            if not s or not t or s==t:reason='Invalid distinct object tags'
            elif relation not in ['supports','supported_by','contains','inside','covers','covered_by','rests_on']:reason='Unsupported or geometric relation'
            elif confidence<.8:reason='Low VLM confidence'
            else:
                alo,ahi=bounds[s];blo,bhi=bounds[t];gap=float(np.linalg.norm(np.maximum(np.maximum(blo-ahi,alo-bhi),0)))
                if gap>.08:reason='No plausible contact or containment in M0 geometry'
            row=dict(**r,subject_id=s,object_id=t,rejection_reason=reason,image_id=iid)
            review.append(row)
            if reason is None:accepted_evidence[(s,relation,t)].append(row)
        write(folder/'validated_relations.json',review);attempts.append(dict(image_id=iid,status='completed',seconds=time.time()-start,raw_relations=len(parsed.get('relations',[])),locally_valid=sum(r['rejection_reason'] is None for r in review)))
    except Exception as exc:
        write(folder/'failure.json',dict(error=repr(exc),seconds=time.time()-start));attempts.append(dict(image_id=iid,status='failed',error=repr(exc)))
    print('LOCAL SOM',attempts[-1],flush=True)
semantic=[];insufficient=[]
for (s,r,t),evidence in accepted_evidence.items():
    row=dict(subject=s,relation=r,object=t,source='ReLaGS_style_local_SoM',evidence=evidence)
    (semantic if len({e['image_id'] for e in evidence})>=2 else insufficient).append(row)
write(out/'semantic_relations.json',semantic);write(out/'insufficient_evidence_relations.json',insufficient);write(out/'scene_graph.json',dict(nodes=nodes,edges=edges+semantic,coordinate_semantics={'+X':'right','+Y':'front','+Z':'up'},geometry_rules=dict(axis_gap_margin=.02,near_aabb_gap=.35),visual_model='qwen3.5:9b',visual_fusion='At least two distinct real training views, valid IDs, confidence >=0.8, plausible 3D contact.'))
write(out/'summary.json',dict(nodes=len(nodes),geometric_edges=len(edges),accepted_visual_edges=len(semantic),single_view_hypotheses=len(insufficient),som_attempts=attempts,external_image_upload=False,heldout_used=False,note='Empty semantic relations are allowed: separately annotated whole devices need not support or contain each other.'))
grid([out/'som'/iid/'som.jpg' for iid in chosen],out/'som_overview.jpg',labels=chosen,columns=2,tile=(750,460));print('SCENE GRAPH',len(nodes),len(edges),len(semantic))
