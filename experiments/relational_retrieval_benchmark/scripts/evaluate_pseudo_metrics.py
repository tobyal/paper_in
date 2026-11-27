"""Frozen-mask, query-balanced evaluation against reviewed SAM-assisted Pseudo-GT."""
from common import *
from evaluate_metrics import score,selftest
import csv,collections,shutil,datetime
METHODS=['langsplat','thgs','relags','ours'];NAMES=dict(langsplat='LangSplat',thgs='THGS',relags='ReLaGS',ours='Ours');keys=['iou','precision','recall']
def csvwrite(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True);columns=list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
def means(rows):return {k:float(np.mean([r[k] for r in rows])) if rows else None for k in keys}
def main():
    check_frozen();base=ROOT/'evaluation/pseudo_ground_truth';lock=read(base/'REFERENCE_FROZEN.json');assert all(sha(ROOT/p)==h for p,h in lock['sha256'].items())
    write(ROOT/'evaluation/metrics/pseudo_evaluator_tests.json',dict(**selftest(),reference_lock_verified=True,empty_prediction_precision_rule=0))
    queries=read(ROOT/'configs/benchmark_queries.json');qmap={q['query_id']:q for q in queries};samples=read(base/'sample_manifest.json');results={m:{q['query_id']:read(ROOT/'outputs'/m/q['query_id']/'result.json') for q in queries} for m in METHODS};viewrows=[];queryrows=[];relationrows=[];summary=[];eligible=[]
    for ref in samples:
        qid,iid=ref['query_id'],ref['camera_id'];paths={m:ROOT/'outputs'/m/qid/iid/'mask.png' for m in METHODS};missing=[m for m in METHODS if not paths[m].exists() or results[m][qid]['status']!='completed'];ok=ref['status']=='accepted_pseudo' and ref['target_visible'] and not missing
        gt=np.array(Image.open(ROOT/ref['mask_path']));assert gt.shape==(528,938) and set(np.unique(gt))<={0,255}
        if ok:assert gt.any();eligible.append((qid,iid))
        for m in METHODS:
            pred=np.array(Image.open(paths[m])) if paths[m].exists() else None
            if pred is not None:assert pred.shape==gt.shape and set(np.unique(pred))<={0,255}
            status='evaluated' if ok else ('excluded_missing_prediction' if missing else ref['status']);row=dict(method=NAMES[m],method_id=m,query_id=qid,camera_id=iid,relation=qmap[qid]['predicate_ours'],status=status,reference_type='SAM-assisted Pseudo-GT',reason='; '.join(ref['reasons']) if not missing else 'Missing/failed: '+','.join(missing),reference_pixels=int((gt>0).sum()),prediction_pixels=int((pred>0).sum()) if pred is not None else None,empty_prediction=bool(pred is not None and not pred.any()),query_execution_status=results[m][qid]['status'],iou=None,precision=None,recall=None,tp=None,fp=None,fn=None)
            if ok:row.update(score(pred>0,gt>0))
            viewrows.append(row)
    for m in METHODS:
        for q in queries:
            rows=[r for r in viewrows if r['method_id']==m and r['query_id']==q['query_id'] and r['status']=='evaluated'];allr=[r for r in viewrows if r['method_id']==m and r['query_id']==q['query_id']];r=results[m][q['query_id']]
            queryrows.append(dict(method=NAMES[m],method_id=m,query_id=q['query_id'],relation=q['predicate_ours'],query=q['query_en'],status='evaluated' if rows else 'excluded_no_reliable_reference',valid_views=len(rows),total_views=len(allr),empty_evaluated_predictions=sum(x['empty_prediction'] for x in rows),**means(rows),query_seconds=r['timing']['query']['median_seconds'],end_to_end_seconds=r['timing']['end_to_end']['median_seconds']))
        for relation in ['left_of','right_of','in_front_of','behind','near']:
            rows=[r for r in queryrows if r['method_id']==m and r['relation']==relation and r['status']=='evaluated'];relationrows.append(dict(method=NAMES[m],method_id=m,relation=relation,valid_queries=len(rows),valid_views=sum(r['valid_views'] for r in rows),**means(rows)))
        qr=[r for r in queryrows if r['method_id']==m and r['status']=='evaluated'];vr=[r for r in viewrows if r['method_id']==m];valid=[r for r in vr if r['status']=='evaluated'];old=read(ROOT/'outputs'/m/'summary.json');record=dict(method=NAMES[m],method_id=m,reference_type='SAM-assisted Pseudo-GT',projection_miou=means(qr)['iou'],precision=means(qr)['precision'],recall=means(qr)['recall'],valid_queries=len(qr),valid_views=len(valid),total_queries=len(queries),total_views=len(vr),excluded_views=len(vr)-len(valid),normal_empty_view_masks_all=sum(r['empty_prediction'] and r['query_execution_status']=='completed' for r in vr),normal_empty_view_masks_evaluated=sum(r['empty_prediction'] for r in valid),normal_empty_query_outputs=sum(bool(r['empty_result']) for r in results[m].values() if r['status']=='completed'),failed_final_queries=sum(r['status']!='completed' for r in results[m].values()),unavailable_fine_instance_queries=sum(bool(r.get('unavailable_object_ids')) for r in results[m].values()),query_seconds=float(np.mean([r['timing']['query']['median_seconds'] for r in results[m].values()])),end_to_end_seconds=float(np.mean([r['timing']['end_to_end']['median_seconds'] for r in results[m].values()])),query_seconds_valid_subset=float(np.mean([r['query_seconds'] for r in qr])),model_load_seconds=old['model_load_seconds']);summary.append(record)
    for filename,rows in [('per_view.csv',viewrows),('per_query.csv',queryrows),('per_relation.csv',relationrows),('summary.csv',summary)]:csvwrite(ROOT/'evaluation/metrics'/filename,rows)
    for filename,rows in [('pseudo_per_view.json',viewrows),('pseudo_per_query.json',queryrows),('pseudo_per_relation.json',relationrows)]:write(ROOT/'evaluation/metrics'/filename,rows)
    previous=ROOT/'evaluation/metrics/summary.json';backup=ROOT/'evaluation/metrics/formal_gt_summary_before_pseudo.json'
    if previous.exists() and not backup.exists():shutil.copy2(previous,backup)
    result=dict(reference_type='SAM-assisted Pseudo-GT',formal_human_ground_truth=False,methods=summary,averaging='mean of valid views within query, then equal-weight mean of valid queries',empty_prediction_precision=0,common_evaluated_samples=[dict(query_id=q,camera_id=i) for q,i in eligible],common_exclusions=[r for r in samples if (r['query_id'],r['camera_id']) not in eligible],reference_lock_sha256=sha(base/'REFERENCE_FROZEN.json'),formal_gt_status='Pending independent human GT',computed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write(previous,result);write(ROOT/'evaluation/metrics/pseudo_summary.json',result);assert len(set((r['valid_queries'],r['valid_views']) for r in summary))==1
    # Independent aggregation check on serialized per-view rows.
    for m,row in zip(METHODS,summary):
        for key,dest in [('iou','projection_miou'),('precision','precision'),('recall','recall')]:
            groups=collections.defaultdict(list)
            for r in viewrows:
                if r['method_id']==m and r['status']=='evaluated':groups[r['query_id']].append(r[key])
            expected=sum(sum(v)/len(v) for v in groups.values())/len(groups);assert abs(expected-row[dest])<1e-12
    print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
