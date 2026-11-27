from common import *
import collections
verify_locks();samples=read(BENCH/'evaluation/pseudo_ground_truth/sample_manifest.json');queries=read(BENCH/'configs/benchmark_queries.json');qmap={q['query_id']:q for q in queries};metric_names=['iou','precision','recall']
def score(p,g):
    tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum());return dict(tp=tp,fp=fp,fn=fn,iou=tp/max(tp+fp+fn,1),precision=tp/max(tp+fp,1),recall=tp/max(tp+fn,1))
def means(rows):return {k:float(np.mean([r[k] for r in rows])) if rows else None for k in metric_names}
supplement=['sam_original','sam_common','ours_common'] if (ROOT/'E02_ablation/predictions/ours_common/Q025/result.json').exists() else []
for experiment,methods in [('E01_external_comparison',['langsplat','thgs','relags','ours']),('E02_ablation',['box_gated','no_relation','ours','box_all33']+supplement)]:
    views=[];perquery=[];perrelation=[];summary=[]
    for method in methods:
        base=BENCH/'outputs'/method if experiment.startswith('E01') else ROOT/experiment/'predictions'/method
        for s in samples:
            qid,iid=s['query_id'],s['camera_id'];p=base/qid/iid/'mask.png';g=BENCH/s['mask_path'];record=read(base/qid/'result.json');c=read(base/qid/iid/'camera.json')
            assert record['status']=='completed';assert c==read(BENCH/'configs/evaluation_views.json')['cameras'][iid]
            pred=np.array(Image.open(p));gt=np.array(Image.open(g));assert pred.shape==gt.shape==(528,938);assert set(np.unique(pred))<={0,255};valid=s['status']=='accepted_pseudo' and s['target_visible']
            row=dict(method=method,query_id=qid,camera_id=iid,relation=qmap[qid]['predicate_ours'],evaluated=valid,status='evaluated' if valid else s['status'],reason='; '.join(s['reasons']),empty_prediction=not bool(pred.any()),prediction_pixels=int((pred>0).sum()),reference_pixels=int((gt>0).sum()),execution_status=record['status'])
            row.update(score(pred>0,gt>0) if valid else dict.fromkeys(['tp','fp','fn']+metric_names));views.append(row)
        for q in queries:
            vv=[r for r in views if r['method']==method and r['query_id']==q['query_id'] and r['evaluated']];perquery.append(dict(method=method,query_id=q['query_id'],relation=q['predicate_ours'],valid_views=len(vv),**means(vv)))
        for rel in dict.fromkeys(q['predicate_ours'] for q in queries):
            qr=[r for r in perquery if r['method']==method and r['relation']==rel and r['valid_views']];perrelation.append(dict(method=method,relation=rel,valid_queries=len(qr),valid_views=sum(r['valid_views'] for r in qr),**means(qr)))
        qr=[r for r in perquery if r['method']==method and r['valid_views']];vr=[r for r in views if r['method']==method];summary.append(dict(method=method,valid_queries=len(qr),valid_views=sum(r['evaluated'] for r in vr),normal_empty_evaluated=sum(r['evaluated'] and r['empty_prediction'] for r in vr),normal_empty_all=sum(r['empty_prediction'] for r in vr),failed_queries=0,**means(qr)))
    for name,rows in [('per_view',views),('per_query',perquery),('per_relation',perrelation),('summary',summary)]:
        write(ROOT/experiment/'metrics'/f'{name}.json',rows);csvwrite(ROOT/experiment/'metrics'/f'{name}.csv',rows)
    if experiment.startswith('E01'):
        previous={r['method_id']:r for r in read(BENCH/'evaluation/metrics/summary.json')['methods']}
        for row in summary:
            for k,old in [('iou','projection_miou'),('precision','precision'),('recall','recall')]:assert abs(row[k]-previous[row['method']][old])<1e-12
    print(experiment,json.dumps(summary),flush=True)
write(ROOT/'E01_external_comparison/evaluation_audit.json',dict(metrics_independently_recomputed=True,previous_aggregates_exact=True,common_queries=23,common_views=44,total_queries=25,total_views=50,excluded_samples=[s for s in samples if s['status']!='accepted_pseudo'],camera_parameters_exact=True,binary_mask_dimensions_exact=True,reference_sha256=sha(BENCH/'evaluation/pseudo_ground_truth/REFERENCE_FROZEN.json'),human_reference_files=[str(p) for p in (BENCH/'evaluation/ground_truth').rglob('*') if p.is_file()]))
