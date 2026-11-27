from common import *
import traceback
verify_locks();wm=world_model();r=renderer();views=read(BENCH/'configs/evaluation_views.json')['cameras'];queries=read(BENCH/'configs/benchmark_queries.json');records=[]
for q in queries:
    qid=q['query_id'];raw=wm.query(q['query_zh']);old=read(BENCH/'outputs/ours'/qid/'raw_query.json')
    assert raw==old,(qid,'query changed')
    category=wm.query(raw['target_text']);identity=dict(query=q,raw_relation_query=raw,raw_category_query=category,excluded_same_class=sorted(set(raw['known_category_instances'])-set(raw['matched_object_ids'])))
    write(ROOT/'E04_relation_retrieval/queries'/qid/'trace.json',identity)
    variants={'box_gated':raw['renderable_object_ids'],'box_all33':raw['matched_object_ids'],'no_relation':category['renderable_object_ids'],'ours':raw['renderable_object_ids']}
    for variant,oids in variants.items():
        dest=ROOT/'E02_ablation/predictions'/variant/qid;dest.mkdir(parents=True,exist_ok=True)
        if (dest/'result.json').exists():records.append(read(dest/'result.json'));continue
        start=time.perf_counter()
        try:
            ids=union([(candidates(o) if variant.startswith('box') else fine(o)) for o in oids]);np.save(dest/'gaussian_indices.npy',ids)
            if variant=='ours':assert np.array_equal(ids,np.load(BENCH/'outputs/ours'/qid/'gaussian_indices.npy'))
            rr=[]
            for iid in q['evaluation_camera_ids']:
                c=views[iid];d=dest/iid;d.mkdir(exist_ok=True)
                if variant=='ours':soft=np.load(BENCH/'outputs/ours'/qid/iid/'response.npz')['response']
                else:soft=r.contribution(c,ids)
                mask=soft>.5;assert soft.shape==(528,938) and np.isfinite(soft).all()
                np.savez_compressed(d/'response.npz',response=soft);save(d/'mask.png',mask.astype(np.uint8)*255);save(d/'overlay.jpg',overlay(rgb(c),mask));write(d/'camera.json',c)
                rr.append(dict(camera_id=iid,mask_pixels=int(mask.sum())))
            sync();record=dict(variant=variant,query_id=qid,status='completed',returned_object_ids=oids,matched_object_ids=raw['matched_object_ids'],category_candidate_ids=raw['known_category_instances'],unavailable_ids=raw['unavailable_object_ids'],gaussian_count=len(ids),views=rr,wall_seconds=time.perf_counter()-start,reused_prediction=(variant=='ours'))
        except Exception as e:traceback.print_exc();record=dict(variant=variant,query_id=qid,status='failed',error=repr(e))
        write(dest/'result.json',record);records.append(record);print(variant,qid,record['status'],record.get('gaussian_count'),flush=True)
write(ROOT/'E02_ablation/run_summary.json',records)
assert all(x['status']=='completed' for x in records)
write(ROOT/'E04_relation_retrieval/query_statistics.json',[dict(query_id=q['query_id'],query=q['query_en'],**{k:wm.query(q['query_zh'])[k] for k in ['same_category_candidates_before','matches_after','known_category_instances','anchor_object_ids','matched_object_ids','renderable_object_ids','unavailable_object_ids','relation_evidence']}) for q in queries])

