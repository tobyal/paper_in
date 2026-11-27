from common import *
import collections,os,re,xml.etree.ElementTree as ET
verify_locks();before=read(ROOT/'source_data/protected_before.json');changed=[];missing=[]
for path,(size,mtime) in before.items():
    p=PROJECT/path
    if not p.exists():missing.append(path);continue
    st=p.stat()
    if [st.st_size,st.st_mtime_ns]!=[size,mtime]:changed.append(path)
assert not changed and not missing,(changed,missing)
queries=read(BENCH/'configs/benchmark_queries.json');wm=world_model();methods=['box_gated','no_relation','ours','box_all33','sam_original','sam_common','ours_common'];maskcount=0;checks=[]
for q in queries:
    qid=q['query_id'];raw=wm.query(q['query_zh']);gated=read(ROOT/'E02_ablation/predictions/box_gated'/qid/'result.json');ours=read(ROOT/'E02_ablation/predictions/ours'/qid/'result.json');assert gated['returned_object_ids']==ours['returned_object_ids']==raw['renderable_object_ids']
    for m in methods:
        base=ROOT/'E02_ablation/predictions'/m/qid;record=read(base/'result.json');ids=np.load(base/'gaussian_indices.npy');assert record['status']=='completed';assert len(ids)==len(np.unique(ids));assert not len(ids) or (ids.min()>=0 and ids.max()<1828777)
        for iid in q['evaluation_camera_ids']:
            mask=np.array(Image.open(base/iid/'mask.png'));assert mask.shape==(528,938) and set(np.unique(mask))<={0,255};maskcount+=1
            if m=='ours':assert np.array_equal(mask,np.array(Image.open(BENCH/'outputs/ours'/qid/iid/'mask.png')))
    for exp in ['E01_external_comparison','E02_ablation']:assert (ROOT/exp/'gallery'/f'{qid}.png').exists()
for qid in ['Q003','Q006']:
    base=ROOT/'E05_multiview_application/multiview'/qid;ids=np.load(base/'fixed_gaussian_ids.npy');assert np.array_equal(ids,np.load(BENCH/'outputs/ours'/qid/'gaussian_indices.npy'));views=read(base/'views.json');assert len(views)==3 and len({v['same_ids_sha256'] for v in views})==1
    directions=[];target=np.mean([wm.byid[oid]['bbox']['center'] for oid in read(base/'query.json')['matched_object_ids']],axis=0);T=np.array(Context.state['scene']['transform'])
    for v in views:
        eye=np.array(v['camera']['center'])@T[:3,:3].T+T[:3,3];di=eye-target;directions.append(di/np.linalg.norm(di))
    angles=[float(np.rad2deg(np.arccos(np.clip(a@b,-1,1)))) for i,a in enumerate(directions) for b in directions[i+1:]];assert min(angles)>20;checks.append(dict(query_id=qid,direction_separations_deg=angles,fixed_ids_exact=True))
figures=[]
for m in read(ROOT/'figures/manifest.json'):
    p=ROOT/m['png'];svg=ROOT/m['svg'];im=Image.open(p);im.verify();im=Image.open(p);assert im.width>=3000;ET.parse(svg)
    d=p.parent;layout=read(d/'layout.json');assert layout['dpi']==450 and 170<=layout['width_mm']<=180
    for path,meta in read(d/'sources.json').items():assert Path(path).exists() and sha(path)==meta['sha256'],path
    figures.append(dict(figure=m['figure'],size=list(im.size),png_bytes=p.stat().st_size,svg_bytes=svg.stat().st_size,subplots=len(list((d/'subplots').glob('*.png'))),png_sha256=sha(p)))
# Original six figures remain required; F10-F12 are optional frozen-data analyses.
original={'F04_dataset','F05_external_comparison','F06_entity_construction','F07_relation_retrieval','F08_ablation','F09_multiview_application'}
analysis={'F10_query_performance','F11_mechanism_contribution','F12_candidate_reduction'}
found={f['figure'] for f in figures}
assert original <= found <= original | analysis and len(found)==len(figures)
assert len(read(ROOT/'E01_external_comparison/human_review/manifest.json'))==50
for table in ['T01_external','T02_relations','T03_ablation','T04_efficiency']:
    for suffix in ['csv','md','tex','tsv']:assert (ROOT/'tables'/f'{table}.{suffix}').stat().st_size>30
mdlinks=[]
for p in [ROOT/'README.md',ROOT/'docs/GALLERY.md',ROOT/'FIGURE_INDEX.md',ROOT/'E01_external_comparison/GALLERY.md',ROOT/'E02_ablation/GALLERY.md']:
    for link in re.findall(r'\]\(([^)]+)\)',p.read_text()):
        if '://' not in link:
            assert (p.parent/link.split('#')[0]).exists(),(str(p),link);mdlinks.append(link)
result=dict(status='passed',protected_existing_files=len(before),modified_existing_files=changed,missing_existing_files=missing,critical_lock_hashes_passed=True,ablation_binary_masks=maskcount,variants=len(methods),queries=25,views_per_query=2,main_valid_queries=23,main_valid_views=44,ours_predictions_pixel_exact=True,box_gated_identity_exact=True,scene_nodes=len(wm.objects),scene_edges=len(wm.graph['edges']),nearest_cases=len(read(ROOT/'E05_multiview_application/nearest/summary.json')),multiview=checks,figures=figures,complete_comparison_boards=50,human_review_packages=50,markdown_links=len(mdlinks),reference_type='SAM-assisted Pseudo-GT',independent_human_gt=False)
write(ROOT/'source_data/final_validation.json',result);print(json.dumps(result,indent=2),flush=True)
