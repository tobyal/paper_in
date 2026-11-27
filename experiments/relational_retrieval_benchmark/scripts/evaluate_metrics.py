"""Query-balanced projection metrics. Independent reviewed human masks required."""
from common import *
METHODS=['langsplat','thgs','relags','ours']
def score(pred,gt,valid=None):
    pred=np.asarray(pred,bool);gt=np.asarray(gt,bool);assert pred.shape==gt.shape
    valid=np.ones_like(gt) if valid is None else np.asarray(valid,bool);assert valid.shape==gt.shape
    p=pred&valid;g=gt&valid;tp=int((p&g).sum());fp=int((p&~g).sum());fn=int((~p&g).sum())
    assert g.any(),'A valid visible-target evaluation view needs positive GT pixels'
    return dict(iou=tp/(tp+fp+fn),precision=tp/(tp+fp) if tp+fp else 0.,recall=tp/(tp+fn),tp=tp,fp=fp,fn=fn)
def average_queries(rows):return {k:float(np.mean([np.mean([v[k] for v in group]) for group in rows if group])) for k in ['iou','precision','recall']} if any(rows) else dict(iou='Pending GT',precision='Pending GT',recall='Pending GT')
def selftest():
    gt=np.array([[1,1],[0,0]],bool);pred=np.array([[1,0],[1,0]],bool);r=score(pred,gt);assert r['iou']==1/3 and r['precision']==r['recall']==.5
    assert score(np.zeros((2,2)),gt)['iou']==0
    assert score(pred,gt,np.array([[1,0],[0,0]],bool))['iou']==1
    perfect=dict(iou=1,precision=1,recall=1);zero=dict(iou=0,precision=0,recall=0);assert average_queries([[perfect,perfect,perfect],[zero]])['iou']==.5
    assert average_queries([[],[]])['iou']=='Pending GT'
    return dict(status='passed',cases=['TP FP FN','empty prediction','ignore pixels','equal query weighting','Pending GT'])
def main():
    check_frozen();write(ROOT/'evaluation/metrics/evaluator_tests.json',selftest());queries=read(ROOT/'configs/benchmark_queries.json');out=[]
    for method in METHODS:
        rows=[];details=[]
        for q in queries:
            group=[]
            for iid in q['evaluation_camera_ids']:
                base=ROOT/'evaluation/ground_truth'/q['query_id'];meta=base/(iid+'.json');gtpath=base/(iid+'.png');predpath=ROOT/'evaluation/predictions'/method/q['query_id']/(iid+'.png');item=dict(query_id=q['query_id'],camera_id=iid,status='Pending GT')
                if meta.exists() and gtpath.exists():
                    provenance=read(meta)
                    if provenance.get('status')=='confirmed' and provenance.get('source')=='independent_manual_annotation' and provenance.get('reviewer') and provenance.get('target_visible') is True:
                        gt=np.array(Image.open(gtpath));assert gt.shape==(528,938) and set(np.unique(gt))<={0,255};valid=None
                        if provenance.get('ignore_mask'):
                            ignore=base/provenance['ignore_mask'];assert ignore.resolve().is_relative_to(base.resolve());valid=np.array(Image.open(ignore))==0
                        if predpath.exists():
                            pred=np.array(Image.open(predpath));assert pred.shape==gt.shape and set(np.unique(pred))<={0,255};values=score(pred>0,gt>0,valid);group.append(values);item.update(status='evaluated',**values)
                        else:item['status']='prediction_unavailable'
                    else:item['reason']='unconfirmed, non-independent, or target not visible'
                details.append(item)
            rows.append(group)
        result=dict(method=method,**average_queries(rows),evaluated_queries=sum(bool(x) for x in rows),evaluated_views=sum(len(x) for x in rows),total_queries=len(queries),views=details);write(ROOT/'evaluation/metrics'/(method+'.json'),result);out.append({k:v for k,v in result.items() if k!='views'})
    write(ROOT/'evaluation/metrics/human_gt_summary.json',out)
    if not (ROOT/'evaluation/metrics/pseudo_summary.json').exists():write(ROOT/'evaluation/metrics/summary.json',out)
    print(out)
if __name__=='__main__':main()
