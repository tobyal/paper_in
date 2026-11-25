"""Validate repaired graph/query artifacts, preserve provenance, and render review sheet."""
import hashlib,json,pathlib,subprocess,textwrap
import numpy as np
import torch
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/relags_obb_repair_r1';BASE=ROOT/'outputs/relags_baseline'
snapshot=json.loads((OUT/'baseline0_snapshot/baseline_tree.json').read_text())
changed=[]
for record in snapshot:
    p=BASE/record['path']
    if 'link' in record:
        ok=p.is_symlink() and str(p.readlink())==record['link']
    else:
        ok=p.is_file() and p.stat().st_size==record['bytes'] and p.stat().st_mtime_ns==record['mtime_ns']
        if ok and 'sha256' in record:ok=hashlib.sha256(p.read_bytes()).hexdigest()==record['sha256']
    if not ok:changed.append(record['path'])
added=sorted(str(p.relative_to(BASE)) for p in BASE.rglob('*') if (p.is_file() or p.is_symlink()) and str(p.relative_to(BASE)) not in {x['path'] for x in snapshot})
patch=subprocess.check_output(['git','-C',str(ROOT/'ReLaGS'),'diff','--binary'])
old_manifest=json.loads((OUT/'baseline0_snapshot/final_source_manifest.json').read_text())
core_patch_unchanged=hashlib.sha256(patch).hexdigest()==old_manifest['relags_patch_sha256']
assert not changed and not added and core_patch_unchanged,(changed,added,core_patch_unchanged)
audit=pathlib.Path(json.loads((OUT/'08_scene_graph/data/audit_latest.json').read_text())['directory'])
fallbacks={1822,1836,1927,1987,2307};graph_rows=[]
for level in [2,3]:
    d=torch.load(audit/f'level_{level}_graph_inputs.pt',map_location='cpu')
    pred=torch.load(audit/f'level_{level}_edge_predictions.pt',map_location='cpu')
    edge=np.asarray(d['edge_index']);scores=pred['relation_similarities'];features=pred['edge_features'];ids=np.asarray(d['original_cluster_ids'])
    assert np.array_equal(ids,np.arange(len(ids)))
    assert np.array_equal(edge[0],pred['src']) and np.array_equal(edge[1],pred['dst'])
    assert torch.isfinite(scores).all() and torch.isfinite(features).all()
    assert len(pred['src'])==len(np.unique(edge[0]*len(ids)+edge[1]))
    incident=np.isin(edge,list(fallbacks)).any(axis=0) if level==2 else np.zeros(edge.shape[1],dtype=bool)
    row={'level':level,'nodes':len(ids),'edges':edge.shape[1],'node_ids_preserved':True,'all_predictions_finite':True,'edges_incident_to_boundary_nodes':int(incident.sum())}
    if level==3:
        prior=BASE/'08_scene_graph/data/20261125T004930Z_predict_root_diagnostic'
        old=torch.load(prior/'level_3_edge_predictions.pt',map_location='cpu')
        old_input=torch.load(prior/'level_3_graph_inputs.pt',map_location='cpu')
        row['prior_root_diagnostic_same_edges']=np.array_equal(edge,np.asarray(old_input['edge_index']))
        if row['prior_root_diagnostic_same_edges']:
            row['prior_root_max_abs_feature_difference']=float((features-old['edge_features']).abs().max())
            row['prior_root_top1_agreement']=float((scores.argmax(1)==old['relation_similarities'].argmax(1)).float().mean())
        row['root_comparison_note']='The full official loop recenters a second time before L3; the earlier root-only diagnostic centered once. Any difference here is not automatically due to the OBB repair.'
    graph_rows.append(row)
    np.savez_compressed(OUT/'08_scene_graph/data'/f'level_{level}_boundary_edge_flags.npz',edge_incident_to_degenerate_obb=incident)
    del d,pred,scores,features
q=OUT/'09_relational_query';summary=json.loads((q/'metrics/query_relational_summary.json').read_text());assert len(summary['queries'])==6
combined=json.loads((q/'metrics/query_summary.json').read_text());assert len(combined['queries'])==18 and not combined['missing_modes']
relations=torch.load(ROOT/'models/relags/relationship_jina_features.pt',map_location='cpu');prototypes=relations['features'];names=relations['names']
refs=[pathlib.Path(x).stem for x in json.loads((ROOT/'configs/reference_views.json').read_text())['image_names']]
sheet=Image.new('RGB',(1200,440*3),'white');draw=ImageDraw.Draw(sheet);review=[]
for i,record in enumerate(summary['queries']):
    folder=q/'data'/record['id'];raw=torch.load(folder/'raw_query.pt',map_location='cpu');indices=np.load(folder/'gaussian_indices.npy')
    assert len(indices)==record['selected_gaussians'] and len(np.unique(indices))==len(indices)
    ranking=raw['ranked_edges'][0] if raw['ranked_edges'] else []
    chosen=[]
    for key,sim in record['selected']:
        matches=[(edge,sims) for edge,sims in ranking if edge['candidate_subject_id']==key[0] and edge['level']==key[1] and np.allclose(sim,sims,rtol=0,atol=1e-7)]
        assert matches,'Returned subject cannot be traced to original ranked edges'
        edge,sims=matches[0];vec=edge['jina_rel'];cls=int((prototypes@vec).argmax())
        chosen.append({'level':int(edge['level']),'subject_cluster':int(edge['candidate_subject_id']),'object_cluster':int(edge['candidate_object_id']),'predicted_relation_class':names[cls],'subject_relation_object_similarities':list(map(float,sims)),'either_endpoint_has_degenerate_obb':edge['level']==2 and bool({int(edge['candidate_subject_id']),int(edge['candidate_object_id'])}&fallbacks)})
    candidates_touching=sum(edge['level']==2 and bool({int(edge['candidate_subject_id']),int(edge['candidate_object_id'])}&fallbacks) for edge,_ in ranking)
    visibility=[]
    for frame in refs:
        a=np.load(folder/f'{frame}_projection.npz')['alpha_weighted_selection'];assert np.isfinite(a).all()
        visibility.append({'frame':frame,'mean_weight':float(a.mean()),'pixels_above_0_5':int((a>.5).sum())})
    best=max(visibility,key=lambda x:x['mean_weight'])
    row={**record,'selected_edge_evidence':chosen,'ranked_candidate_edges':len(ranking),'candidate_edges_touching_degenerate_obb':candidates_touching,'display_view':best['frame'],'visibility_by_reference':visibility}
    review.append(row)
    with Image.open(q/'visualizations'/record['id']/f'{best["frame"]}.png') as im:tile=im.convert('RGB').resize((600,338))
    x=i%2*600;y=i//2*440;sheet.paste(tile,(x,y))
    text=record['query'];label=f"{i+1}: {text['subject']} | {text['relation']} | {text['object']}"
    for k,line in enumerate(textwrap.wrap(label,width=77)):draw.text((x+5,y+343+14*k),line,fill='black')
    draw.text((x+5,y+375),f"{record['selected_gaussians']} Gaussians; fallback={record['official_threshold_fallback_used']}; {best['frame']}",fill='black')
    relation_text='GNN top-1: '+', '.join(v['predicted_relation_class'] for v in chosen)
    draw.text((x+5,y+390),relation_text,fill='black')
    draw.text((x+5,y+407),'Red = selected subject; predictions are not ground truth.',fill='black')
sheet.save(q/'visualizations/relational_query_overview.jpg',quality=95)
(q/'metrics/relational_review.json').write_text(json.dumps({'queries':review,'no_ground_truth_accuracy':True,'display_rule':'Largest mean projected selected-subject weight among eight fixed views; no selection changes.'},indent=2))
result={'status':'verified','baseline0_items_unchanged':len(snapshot),'baseline0_changed':changed,'baseline0_added':added,'relags_source_diff_unchanged':core_patch_unchanged,'graph_levels':graph_rows,'new_relational_queries':6,'reused_open_queries':12,'empty_relational_results':sum(r['empty_result'] for r in review),'official_threshold_fallback_queries':sum(r['official_threshold_fallback_used'] for r in review),'selected_edges_touching_degenerate_obb':sum(x['either_endpoint_has_degenerate_obb'] for r in review for x in r['selected_edge_evidence']),'limitations':'Execution completeness does not establish industrial semantic or relational accuracy. Degenerate node orientation is underdetermined; baseline coordinates still lack metric/gravity calibration.'}
(OUT/'00_investigation/metrics/final_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
