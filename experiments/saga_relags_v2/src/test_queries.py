"""Real-scene functional regressions and explicitly separate synthetic edge cases."""
import copy,shutil,subprocess,sys,tempfile
from common import *
from query_engine import WorldModel

wm=WorldModel(ROOT/'world_model');rows=[];demonstrations=[];byid=wm.byid
def check(name,text,expected,status='ok',synthetic=False,model=None):
    model=model or wm;result=model.query(text);ok=set(result['matched_object_ids'])==set(expected) and result['status']==status
    rows.append(dict(name=name,query=text,synthetic=synthetic,passed=ok,expected_ids=expected,expected_status=status,result=result));assert ok,rows[-1]
    return result
for cat in wm.categories:
    ids=[o['object_id'] for o in wm.objects if o['category_id']==cat['category_id']];check('all category instances',cat['name_zh'],ids);demonstrations.append(cat['name_zh'])
for o in wm.objects:check('unique object identity',o['name_zh'],[o['object_id']])
words={'nearest_to':'最近','left_of':'左侧','right_of':'右侧','in_front_of':'前方','behind':'后方','near':'附近'}
for rel,word in words.items():
    found=False
    for cat in wm.categories:
        for anchor in wm.objects:
            expected=[e['subject'] for e in wm.graph['edges'] if e['relation']==rel and e['object']==anchor['object_id'] and byid[e['subject']]['category_id']==cat['category_id']]
            if not expected:continue
            text=('距离' if rel=='nearest_to' else '位于')+anchor['name_zh']+word+'的'+cat['name_zh'];check('real '+rel,text,expected)
            # Prefer a relation that actually narrows a category.
            if len(set(expected))<sum(o['category_id']==cat['category_id'] for o in wm.objects):demonstrations.append(text);found=True;break
        if found:break
    assert found,rel
regressions=[]
for e in wm.graph['edges']:
    if e['relation']!='nearest_to' or byid[e['subject']]['segmentation_available']:continue
    cat=next(c for c in wm.categories if c['category_id']==byid[e['subject']]['category_id']);anchor=byid[e['object']];text='距离'+anchor['name_zh']+'最近的'+cat['name_zh']
    pool=[o for o in wm.objects if o['category_id']==cat['category_id'] and o['object_id']!=anchor['object_id']];distances=[float(np.linalg.norm(np.array(o['bbox']['center'])-anchor['bbox']['center'])) for o in pool];expected=[o['object_id'] for o,d in zip(pool,distances) if d<=min(distances)+1e-6];result=check('actual nearest unavailable regression',text,expected)
    assert e['subject'] in result['unavailable_object_ids'];assert e['subject'] not in result['renderable_object_ids'];regressions.append(rows[-1])
    if len(regressions)==3:break
assert regressions;demonstrations.append(regressions[0]['query'])
partial=next(o for o in wm.objects if o['extraction_status']=='partial_usable');result=check('partial instance remains queryable',partial['name_zh'],[partial['object_id']]);assert partial['object_id'] in result['renderable_object_ids'];demonstrations.append(partial['name_zh'])
unavailable=next(o for o in wm.objects if not o['segmentation_available']);result=check('unavailable equipment retains location',unavailable['name_zh'],[unavailable['object_id']]);assert not len(wm.gaussian_ids(result));demonstrations.append(unavailable['name_zh'])
for text,status in [('物料车 99','unknown_equipment'),('距离物料车 99最近的工作台','reference_not_found'),('物料车上方的工作台','unsupported_relation_expression'),('物料车下方的工作台','unsupported_relation_expression'),('workbench between material carts','unsupported_relation_expression'),('工作台支撑的蓝色箱组','unsupported_relation_expression'),('未知设备','unknown_category')]:check('invalid or unsupported',text,[],status)
# Actual empty relation from frozen geometry, not a synthetic object.
for anchor in wm.objects:
    text='位于'+anchor['name_zh']+'左侧的工作台';r=wm.query(text)
    if r['status']=='no_relation_match':check('actual empty relation',text,[],'no_relation_match');demonstrations.append(text);break
else:raise AssertionError('No real empty-case found')
anchors=[o['object_id'] for o in wm.objects if o['category_id']=='category_01'];expected={e['subject'] for e in wm.graph['edges'] if e['relation']=='nearest_to' and e['object'] in anchors and byid[e['subject']]['category_id']=='category_04'}
check('multiple same-category references use union','距离物料车最近的多层料架',list(expected))
# A failed node remains a valid anchor and answer; synthetic test is labelled explicitly.
synthetic=WorldModel(ROOT/'world_model');synthetic.graph=copy.deepcopy(wm.graph);synthetic.objects=synthetic.graph['nodes'];synthetic.byid={o['object_id']:o for o in synthetic.objects}
for o in synthetic.objects:o.update(segmentation_available=False,extraction_status='failed')
r=check('synthetic all instances unavailable',regressions[0]['query'],regressions[0]['expected_ids'],synthetic=True,model=synthetic);assert not r['renderable_object_ids'] and r['unavailable_object_ids'];assert not len(synthetic.gaussian_ids(r))
# Synthetic equidistant candidates, calculated from explicit positions using the C tolerance.
tie=WorldModel(ROOT/'world_model');ns=copy.deepcopy(wm.objects[:3]);ns[0].update(name_zh='参照 01',name_en='Anchor 01',category_id='category_02');ns[1].update(name_zh='物料车 98',category_id='category_01');ns[2].update(name_zh='物料车 99',category_id='category_01');centers=np.array([[0,0,0],[-1,0,0],[1,0,0]])
for n,p in zip(ns,centers):n['bbox']['center']=p.tolist()
d=np.linalg.norm(centers[1:]-centers[0],axis=1);edges=[dict(subject=n['object_id'],relation='nearest_to',object=ns[0]['object_id'],evidence=dict(center_distance=float(x),synthetic=True)) for n,x in zip(ns[1:],d) if x<=d.min()+1e-6]
tie.objects=ns;tie.byid={n['object_id']:n for n in ns};tie.graph=dict(nodes=ns,edges=edges);check('synthetic tied nearest','距离参照 01最近的物料车',[n['object_id'] for n in ns[1:]],synthetic=True,model=tie)
out=ROOT/'outputs/D';write(out/'tests.json',dict(total=len(rows),passed=sum(r['passed'] for r in rows),real_cases=sum(not r['synthetic'] for r in rows),synthetic_cases=sum(r['synthetic'] for r in rows),cases=rows,interpretation='Engineering correctness against frozen geometry and known catalog; not independent segmentation or relationship accuracy.'))
write(out/'nearest_regressions.json',regressions);write(out/'demonstration_queries.json',list(dict.fromkeys(demonstrations)))
# Standalone from /tmp, with no project packages on PYTHONPATH; aliases/geometry need numpy only.
shutil.copy2(ROOT/'src/query_engine.py',ROOT/'world_model/query.py')
result=subprocess.run([sys.executable,str(ROOT/'world_model/query.py'),'--model',str(ROOT/'world_model'),'--text',regressions[0]['query'],'--output',str(out/'standalone_query')],cwd='/tmp',capture_output=True,text=True)
write(out/'standalone_check.json',dict(returncode=result.returncode,cwd='/tmp',stdout=result.stdout,stderr=result.stderr));assert result.returncode==0
print('QUERY TESTS',len(rows),'passed; standalone query passed')
