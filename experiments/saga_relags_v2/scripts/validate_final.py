"""Cross-module integrity, source protection and held-out isolation checks."""
from pathlib import Path
import sys,collections,ast
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
from query_engine import WorldModel
from plyfile import PlyData

provenance=read(ROOT/'inputs/provenance.json');protected=read(ROOT/'inputs/protected_before.json');changed=[]
for name,stat in protected.items():
    p=PROJECT/name
    if not p.exists() or [p.stat().st_size,p.stat().st_mtime_ns]!=stat:changed.append(name)
hashes={name:sha(PROJECT/name)==value for name,value in provenance['checkpoint_hashes'].items()}
frozen=read(ROOT/'outputs/A/frozen_manifest.json');frozen_ok=[]
for item in frozen['objects']:frozen_ok.append(sha(ROOT/item['indices'])==item['sha256'] and sha(ROOT/item['ply'])==item['ply_sha256'])
objects=read(ROOT/'outputs/A/final_summary.json')['objects'];raw=PlyData.read(original_ply())['vertex'].data;ownership=np.zeros(len(raw),np.int16);checks=[]
heldout={c['image_id'] for c in read(ROOT/'inputs/cameras.json') if c['split']!='train'};affinity={c['image_id'] for c in read(ROOT/'inputs/training_cameras.json')};prompt_counts=collections.Counter();used_views=set()
for o in objects:
    oid=o['object_id'];ids=np.load(ROOT/o['gaussian_indices']);ply=PlyData.read(ROOT/o['ply'])['vertex'].data
    valid_ids=bool(len(ids) and ids.min()>=0 and ids.max()<len(raw) and len(np.unique(ids))==len(ids));subset_ok=bool(np.isin(ids,candidate_ids(oid)).all());attributes=bool(np.array_equal(raw[ids],ply));ownership[ids]+=1
    prompt=read((ROOT/o['gaussian_indices']).parent/'prompt.json')
    for p in prompt['prompts']:
        iid=p['image_id'];assert iid not in heldout;used_views.add(iid);prompt_counts['in_frozen_affinity_training' if iid in affinity else 'new_train_split_prompt_view']+=1
    checks.append(dict(object_id=oid,valid_ids=valid_ids,inside_M0_candidates=subset_ok,original_ply_attributes_exact=attributes,final_gallery_exists=(ROOT/'outputs/A/final_gallery'/f'{oid}.jpg').exists()))
assert all(all(c[k] for k in ['valid_ids','inside_M0_candidates','original_ply_attributes_exact','final_gallery_exists']) for c in checks)
assert not changed and all(hashes.values()) and all(frozen_ok) and ownership.max()==1
assert len(objects)==33 and len(heldout)==44
wm=WorldModel(ROOT/'world_model');assert len(wm.objects)==33;assert len(wm.features['category_ids'])==8;assert all((wm.path/n['gaussian_indices']).exists() and (wm.path/n['instance_ply']).exists() for n in wm.objects)
for path in list((ROOT/'src').glob('*.py'))+list((ROOT/'scripts').glob('*.py')):ast.parse(path.read_text(),filename=str(path))
# Revalidate B against the final deployed parser, including explicit feature matrix permutation.
b=read(ROOT/'outputs/B/validation.json');cases=b['evaluations'][b['chosen']]['cases'];results=[]
for case in cases:
    result=wm.query(case['query']);actual=result.get('target_match',{}).get('category_match',{}).get('category_id');results.append(dict(query=case['query'],expected=case['expected'],actual=actual,passed=actual==case['expected']))
assert all(r['passed'] for r in results)
permuted=ROOT/'outputs/validation/permuted_features.npz';np.savez(permuted,text=wm.features['text'][::-1],visual=wm.features['visual'][::-1],category_ids=wm.features['category_ids'][::-1]);other=WorldModel(wm.path,features_path=permuted);other.encoder=wm.encoder;other.tokenizer=wm.tokenizer;other.outside_vectors=wm.outside_vectors
for case in cases:
    r=other.query(case['query']);assert r.get('target_match',{}).get('category_match',{}).get('category_id')==case['expected']
runtime=[]
for path in sorted((ROOT/'logs').glob('*/*/result.json')):
    r=read(path);gpu=path.parent/'gpu.csv';memory=[]
    if gpu.exists():
        for line in gpu.read_text().splitlines()[1:]:
            try:memory.append(float(line.split(',')[2]))
            except (IndexError,ValueError):pass
    runtime.append(dict(stage=r['stage'],status=r['status'],seconds=r['seconds'],gpu_sampled_peak_MiB=max(memory) if memory else None,gpu=r['gpu'],command=r['command'],log=str((path.parent/'run.log').relative_to(ROOT))))
report=dict(passed=True,protected_file_count=len(protected),changed_protected_files=changed,critical_hashes_unchanged=hashes,all_33_frozen_instances_unchanged=all(frozen_ok),no_duplicate_final_ids=True,union_gaussian_count=int((ownership>0).sum()),objects=checks,heldout_images_in_prompts=0,unique_prompt_views=len(used_views),per_object_view_uses=dict(prompt_counts),B_final_interface_cases=results,B_feature_row_permutation_passed=True,standalone_query_passed=read(ROOT/'outputs/D/standalone_check.json')['returncode']==0,query_tests=read(ROOT/'outputs/D/tests.json')['total'],runtime=runtime,gpu_measurement_note='5-second nvidia-smi samples for the assigned whole GPU, not exclusive per-process peak; short runs can peak between samples')
write(ROOT/'outputs/validation/final_checks.json',report);write(ROOT/'outputs/validation/runtime.json',runtime);print('FINAL CHECKS PASS',len(protected),'protected;',len(objects),'exact native subsets;',int((ownership>0).sum()),'unique assigned Gaussians')
