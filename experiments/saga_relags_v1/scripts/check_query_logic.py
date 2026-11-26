"""Check parsing and filtering on the real graph with real early-checkpoint rows."""
import sys,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
from query_engine import WorldModel
fixture=ROOT/'outputs/validation/query_logic_inputs';fixture.mkdir(parents=True,exist_ok=True);graph=read(ROOT/'outputs/C/scene_graph.json');extraction=read(ROOT/'outputs/A/extractions/iteration_2500_extra_points/summary.json');rows={r['object_id']:r for r in extraction['objects']};excluded={'obj_5bfd32389355'}
for n in graph['nodes']:
    n['segmentation_available']=n['object_id'] in rows and n['object_id'] not in excluded
    if n['segmentation_available']:
        target=fixture/'objects'/n['object_id']/'gaussian_indices.npy';target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(ROOT/rows[n['object_id']]['gaussian_indices'],target);n['gaussian_indices']=str(target.relative_to(fixture))
write(fixture/'scene_graph.json',graph);write(fixture/'manifest.json',dict(purpose='Intermediate query-engine validation; not final world model; no heldout images used'))
for name in ['categories.json','category_features.npz']:shutil.copy2(ROOT/'outputs/B'/name,fixture/name)
wm=WorldModel(fixture);records=[]
for category in wm.categories:
    actual=wm.query(category['name_zh']);expected=[n['object_id'] for n in wm.objects if n['category_id']==category['category_id'] and n['segmentation_available']];assert actual['matched_object_ids']==expected;records.append(dict(query=category['name_zh'],matched=actual['matched_object_ids']))
for anchor in wm.objects[:5]:
    for relation,word in [('nearest_to','最近'),('left_of','左侧'),('right_of','右侧')]:
        text=('距离' if relation=='nearest_to' else '位于')+anchor['name_zh']+word+'的物料车';result=wm.query(text);assert result['anchor_object_ids']==[anchor['object_id']];assert result['relation']==relation;assert result['category_match']['category_id']=='category_01';expected=sorted({e['subject'] for e in graph['edges'] if e['relation']==relation and e['object']==anchor['object_id'] and e['subject'] in result['available_category_candidates']});assert result['matched_object_ids']==expected;records.append(dict(query=text,matched=result['matched_object_ids'],correctly_parsed=True))
write(ROOT/'outputs/validation/query_logic.json',dict(passed=True,real_cases=records,heldout_used=False,segmentation_checkpoint=2500));print('REAL GRAPH QUERY CHECKS',len(records),'PASSED')
