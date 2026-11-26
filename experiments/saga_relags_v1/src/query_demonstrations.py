"""Evaluate stored world-model queries and project only frozen 3D instances."""
import shutil,cv2
from common import *
from query_engine import WorldModel
from industrial_world_model.render import Renderer
from industrial_world_model.hybrid_views.geometry import box_projection
wm=WorldModel(ROOT/'world_model');renderer=Renderer(NativeContext());out=ROOT/'outputs/D';out.mkdir(parents=True,exist_ok=True);objects={o['object_id']:o for o in read(ROOT/'inputs/objects.json')};T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform']);manifest=read(ROOT/'inputs/manifest.json');cameras=[c for c in read(ROOT/'inputs/cameras.json') if c['split']!='train'];assert cameras and all(c['image_id'] not in {im['image_id'] for im in read(ROOT/'inputs/training_cameras.json')} for c in cameras)
available=[o for o in wm.objects if o.get('segmentation_available')];category_ids=sorted({o['category_id'] for o in available});queries=[c['name_zh'] for c in wm.categories if c['category_id'] in category_ids]
# Select display views by actual full-scene visibility, not box area alone.
# This affects visualization cameras only; frozen A indices are never changed.
visibility={}
for original in cameras:
    c=scaled_camera(original,width=750);row={}
    for obj in available:
        projection=box_projection(objects[obj['object_id']]['bbox'],T,c)
        if projection:
            contribution=renderer.contribution(c,np.load(wm.path/obj['gaussian_indices']));pixels=int((contribution>.5).sum())
            row[obj['object_id']]=dict(pixels=pixels,image_coverage=projection['image_coverage'])
        else:row[obj['object_id']]=dict(pixels=0,image_coverage=0)
    visibility[c['image_id']]=row
write(out/'heldout_display_visibility.json',dict(width=750,cameras=visibility,purpose='Choose readable evaluation displays using frozen 3D instances; no segmentation parameter tuning.'))
# Select reproducible examples from the graph, then execute the language parser
# afresh. No object answer is supplied to the query engine.
relation_words={'nearest_to':'最近','left_of':'左侧','right_of':'右侧','in_front_of':'前方','behind':'后方'};examples=[]
for rel in relation_words:
    for category in wm.categories:
        pool=[o for o in available if o['category_id']==category['category_id']]
        if len(pool)<2:continue
        for anchor in wm.objects:
            text=('距离' if rel=='nearest_to' else '位于')+anchor['name_zh']+relation_words[rel]+'的'+category['name_zh'];result=wm.query(text)
            if 0<len(result['matched_object_ids'])<len(pool):
                examples.append(dict(query=text,relation=rel,target_category=category['category_id'],reduction=len(pool)-len(result['matched_object_ids'])));break
chosen=[];used_categories=set();used_rel=set()
for e in sorted(examples,key=lambda e:(e['relation']!='nearest_to',-e['reduction'])):
    if len(chosen)>=5:break
    if (e['target_category'],e['relation']) in used_categories:continue
    chosen.append(e);used_categories.add((e['target_category'],e['relation']));used_rel.add(e['relation'])
queries += [e['query'] for e in chosen];write(out/'example_selection.json',dict(class_queries=queries[:len(category_ids)],relation_examples=chosen,selection='Deterministically choose real graph conditions that reduce >=2 available same-class candidates; engine receives text only.'))
gallery=[];labels=[];records=[]
for index,text in enumerate(queries,1):
    result=wm.query(text);ids=wm.gaussian_ids(result);folder=out/f'query_{index:02d}';folder.mkdir(parents=True,exist_ok=True);np.save(folder/'gaussian_indices.npy',ids);write(folder/'result.json',result)
    def view_score(c):
        rows=[visibility[c['image_id']][oid] for oid in result['matched_object_ids']];return (sum(v['pixels']>=80 for v in rows),sum(np.log1p(v['pixels'])*min(v['image_coverage'],1) for v in rows))
    ranked=sorted(cameras,key=view_score,reverse=True);chosen=[ranked[0]]
    for candidate in ranked[1:]:
        if np.linalg.norm(np.array(candidate['center'])-chosen[0]['center'])>.2:chosen.append(candidate);break
    evaluated=[]
    for camera in chosen:
        if view_score(camera)[0]<=0:continue
        c=scaled_camera(camera,width=1500);rgb=np.array(Image.open(PROJECT/manifest['images']/camera['filename']).convert('RGB').resize((c['width'],c['height'])));contribution=renderer.contribution(c,ids);mask=contribution>.5;overlay=rgb.copy();overlay[mask]=(overlay[mask]*.4+[153,0,0]).clip(0,255).astype(np.uint8);iid=c['image_id'];save(folder/(iid+'_original.jpg'),rgb);save(folder/(iid+'_overlay.jpg'),overlay);save(folder/(iid+'_mask.png'),mask.astype(np.uint8)*255);np.savez_compressed(folder/(iid+'_contribution.npz'),contribution=contribution);save(folder/(iid+'_highlight.jpg'),renderer.highlight(c,[(ids,[1,.12,.05])]))
        write(folder/(iid+'_camera.json'),c);evaluated.append(dict(image_id=iid,split=camera['split'],mask_pixels=int(mask.sum()),camera_path=str((folder/(iid+'_camera.json')).relative_to(ROOT))))
        if len(evaluated)==1:gallery.append(folder/(iid+'_overlay.jpg'));labels.append(f'Q{index:02d} '+result['target_text']+' | '+str(result['same_category_candidates_before'])+' -> '+str(result['matches_after']))
        target=ROOT/'world_model/evaluation_rgb'/camera['filename'];target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():shutil.copy2(PROJECT/manifest['images']/camera['filename'],target)
    write(folder/'evaluation_views.json',evaluated);records.append(dict(query_id=f'query_{index:02d}',query=text,relation=result['relation'],category=result['category_match']['category_id'],matched_object_ids=result['matched_object_ids'],candidates_before=result['same_category_candidates_before'],matches_after=result['matches_after'],evaluation_views=evaluated));print('QUERY',index,text,result['matched_object_ids'],flush=True)
# PIL's default font cannot render Chinese; use readable English category labels.
english={c['category_id']:c['name_en'] for c in wm.categories};labels=[f"{r['query_id']} {english[r['category']]} / {r['relation'] or 'category'} / {r['candidates_before']} -> {r['matches_after']}" for r in records if r['evaluation_views']]
grid(gallery,out/'query_gallery.jpg',labels=labels,columns=2,tile=(900,590));write(out/'summary.json',dict(queries=records,class_queries=sum(r['relation'] is None for r in records),relation_queries=sum(r['relation'] is not None for r in records),heldout_images_used_only_after_freezing_A=True,no_ground_truth_masks_available=True,projection='Full native scene alpha compositing; membership contribution > 0.5',segmentation_at_query_time=False))
