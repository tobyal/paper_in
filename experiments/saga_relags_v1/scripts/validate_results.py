"""Validate real artifacts and protect the previous project; no synthetic accuracy."""
import sys,ast,subprocess,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
from query_engine import WorldModel
from plyfile import PlyData
out=ROOT/'outputs/validation';out.mkdir(parents=True,exist_ok=True);checks={}
sources=read(ROOT/'inputs/protected_sources_before.json');source_changes=[]
for path,expected in sources.items():
    file=PROJECT/path
    if not file.exists() or file.stat().st_size!=expected['bytes'] or sha(file)!=expected['sha256']:source_changes.append(path)
checks['protected_source_changes']=source_changes
before=read(ROOT/'inputs/protected_outputs_before.json');after={str(p.relative_to(PROJECT)):[p.stat().st_size,p.stat().st_mtime_ns] for p in (PROJECT/'outputs').rglob('*') if p.is_file()};checks['protected_outputs_changed']=[p for p,v in before.items() if after.get(p)!=v];checks['protected_outputs_added']=sorted(set(after)-set(before));checks['protected_outputs_checked']=len(before)
wm=WorldModel(ROOT/'world_model');native=PlyData.read(wm.path/'scene/scene.ply')['vertex'].data;used=set();object_checks=[]
feature_ply=PlyData.read(ROOT/f"outputs/A/saga_model/point_cloud/iteration_{wm.manifest['iteration']}/contrastive_feature_point_cloud.ply")['vertex'].data
fixed_fields=['x','y','z','opacity']+['scale_'+str(i) for i in range(3)]+['rot_'+str(i) for i in range(4)]
checks['trained_feature_geometry_equal']=all(np.array_equal(feature_ply[name],native[name]) for name in fixed_fields);assert checks['trained_feature_geometry_equal']
for obj in wm.objects:
    if 'gaussian_indices' not in obj:continue
    ids=np.load(wm.path/obj['gaussian_indices']);ply=PlyData.read(wm.path/obj['ply'])['vertex'].data;candidates=np.load(ROOT/'inputs/geometry/object_candidates'/obj['object_id']/'gaussian_ids.npy');assert np.array_equal(ply,native[ids]);assert len(np.unique(ids))==len(ids) and np.isin(ids,candidates).all();assert not used.intersection(ids.tolist());used.update(ids.tolist());assert len(ids)<len(candidates),'Coarse box copied without feature selection'
    object_checks.append(dict(object_id=obj['object_id'],rows=len(ids),native_attributes_bitwise_equal=True,original_ids_unique=True,within_m0_candidates=True,usable=obj['segmentation_available']))
checks['objects']=object_checks;checks['native_scene_sha256_equal']=sha(wm.path/'scene/scene.ply')==sources['data/gaussian_scene/original_3dgs/point_cloud/iteration_30000/point_cloud.ply']['sha256']
invalid=[];nearest=0
for e in wm.graph['edges']:
    if e['subject'] not in wm.byid or e['object'] not in wm.byid or e['subject']==e['object']:invalid.append(e)
    if e['relation']=='nearest_to':
        a=wm.byid[e['object']];b=wm.byid[e['subject']];pool=[n for n in wm.objects if n['category_id']==b['category_id'] and n['object_id']!=a['object_id']];dist=lambda n:np.linalg.norm(np.array(a['bbox']['center'])-n['bbox']['center']);assert dist(b)<=min(map(dist,pool))+1e-6;nearest+=1
checks['invalid_edges']=invalid;checks['nearest_edges_verified']=nearest
features=wm.features;assert features['text'].shape==(8,512) and features['visual'].shape==(8,512);assert np.isfinite(features['text']).all() and np.isfinite(features['visual']).all()
d=read(ROOT/'outputs/D/summary.json');train_ids={c['image_id'] for c in read(ROOT/'inputs/training_cameras.json')};query_checks=[]
for r in d['queries']:
    result=wm.query(r['query']);assert result['matched_object_ids']==r['matched_object_ids'];saved=np.load(ROOT/'outputs/D'/r['query_id']/'gaussian_indices.npy');assert np.array_equal(saved,wm.gaussian_ids(result));assert all(v['image_id'] not in train_ids for v in r['evaluation_views']);query_checks.append(dict(query=r['query'],returned=len(result['matched_object_ids']),same_class_reduced=bool(result['relation'] and 0<result['matches_after']<result['same_category_candidates_before'])))
checks['queries']=query_checks
for source in list((ROOT/'src').glob('*.py'))+list((ROOT/'scripts').glob('*.py')):ast.parse(source.read_text())
query=d['queries'][0]['query'];proc=subprocess.run([sys.executable,str(wm.path/'query.py'),'--model',str(wm.path),'--text',query,'--output',str(out/'standalone_query')],cwd='/tmp',capture_output=True,text=True);(out/'standalone_query.log').write_text(proc.stdout+'\n'+proc.stderr);checks['standalone_query_exit_code']=proc.returncode
checks['passed']=not(source_changes or checks['protected_outputs_changed'] or checks['protected_outputs_added'] or invalid) and checks['native_scene_sha256_equal'] and proc.returncode==0
write(out/'checks.json',checks);print('ARTIFACT VALIDATION',checks['passed']);assert checks['passed']
