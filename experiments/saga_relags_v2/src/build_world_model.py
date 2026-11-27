"""Freeze category prototypes after a small actual-interface comparison; retain all M0 nodes."""
import collections,shutil,torch,open_clip
from common import *
from query_engine import WorldModel
from m0.spatial import corners
from industrial_world_model.render import Renderer

wm=ROOT/'world_model';wm.mkdir(exist_ok=True);out=ROOT/'outputs/B';out.mkdir(parents=True,exist_ok=True)
quality={o['object_id']:o for o in read(ROOT/'outputs/A/final_summary.json')['objects']}
objects=read(ROOT/'inputs/objects.json');cats=read(V1/'outputs/B/categories.json');old=read(V1/'outputs/C/geometry_graph.json')
graph=read(V1/'outputs/C/geometry_graph.json');xyz=np.load(V1/'inputs/geometry/xyz_industrial.npy',mmap_mode='r')
for node in graph['nodes']:
    oid=node['object_id'];q=quality[oid];ids=np.load(ROOT/q['gaussian_indices']);dest=wm/'instances'/oid;dest.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/q['gaussian_indices'],dest/'gaussian_indices.npy')
    for name,target in [('object.ply',ROOT/q['ply'])]:
        link=dest/name
        if not link.exists():link.symlink_to(Path('../../../')/target.relative_to(ROOT))
    node.update(industrial_position=node['bbox']['center'],reconstruction_status=q['reconstruction_status'],extraction_status=q['extraction_status'],segmentation_available=q['fine_instance_available'],fine_instance_available=q['fine_instance_available'],gaussian_count=len(ids),gaussian_indices=f'instances/{oid}/gaussian_indices.npy',instance_ply=f'instances/{oid}/object.ply',effective_instance_bounds=dict(min=xyz[ids].min(0).tolist(),max=xyz[ids].max(0).tolist(),used_for_relations=False),quality_record=dict(note_zh=q['note_zh'],diagnosis=q['diagnosis'],reviewer=q['quality_reviewer']),m0_annotation_state='draft; frozen r29; not changed')
graph.update(geometry_source='Frozen M0 r29 OBB, not partial SAGA instance geometry',visual_relations_branch='Not run in v2; no invented semantic edges')
write(wm/'scene_graph.json',graph);write(wm/'categories.json',cats)
models=wm/'models';models.mkdir(exist_ok=True)
for name,target in [('open_clip_pytorch_model.bin',PROJECT/'models/openclip_vit_b16/open_clip_pytorch_model.bin'),('native_scene.ply',original_ply())]:
    link=models/name
    if not link.exists():link.symlink_to(target)
shutil.copy2(ROOT/'src/query_engine.py',wm/'query.py')
shutil.copy2(V1/'outputs/B/category_features.npz',out/'features_original.npz')
original=np.load(out/'features_original.npz');cameras={c['image_id']:c for c in read(ROOT/'inputs/cameras.json')};records=read(V1/'outputs/B/crop_observations.json')
model,_,preprocess=open_clip.create_model_and_transforms('ViT-B-16',pretrained=str(models/'open_clip_pytorch_model.bin'),device='cuda');model.eval()
renderer=Renderer(NativeContext());features=collections.defaultdict(list);comparisons=[];panels=[]
with torch.inference_mode():
    for row in records:
        oid=row['object_id'];c=cameras[row['image_id']];assert c['split']=='train';crop=Image.open(V1/row['path']).convert('RGB');q=quality[oid]
        # Only clearly usable extraction is allowed to change a category representative.
        applied=q['extraction_status']=='usable';folder=out/'crop_comparison'/(oid+'_'+row['image_id']);folder.mkdir(parents=True,exist_ok=True)
        if applied:
            contrib=renderer.contribution(c,np.load(ROOT/q['gaussian_indices']));box=row['bbox_xyxy'];alpha=Image.fromarray((np.clip(contrib,0,1)*255).astype(np.uint8)).crop(tuple(box)).resize(crop.size)
            a=np.array(alpha)/255.;rgb=np.array(crop).astype(float);weakened=rgb*(.3+.7*a[...,None])+np.array([127,127,127])*(.7*(1-a[...,None]));candidate=Image.fromarray(weakened.clip(0,255).astype(np.uint8));save(folder/'instance_contribution.png',alpha)
        else:candidate=crop.copy()
        save(folder/'original.jpg',crop);save(folder/'soft_background.jpg',candidate)
        f=norm(model.encode_image(preprocess(candidate).unsqueeze(0).cuda()).float().cpu().numpy()[0]);features[row['category_id']].append(f)
        grid([folder/'original.jpg',folder/'soft_background.jpg'],folder/'comparison.jpg',labels=['M0 crop','A soft background' if applied else 'Original fallback'],columns=2,tile=(300,250));panels.append(folder/'comparison.jpg')
        comparisons.append(dict(**row,modified=applied,extraction_status=q['extraction_status'],comparison=str(folder.relative_to(ROOT)),background_retained=.3))
np.savez(out/'features_soft_background.npz',text=original['text'],visual=np.stack([norm(np.mean(features[cid],0)) for cid in original['category_ids']]),category_ids=original['category_ids'])
write(out/'crop_comparisons.json',comparisons);grid(panels,out/'crop_comparison_gallery.jpg',labels=[r['object_id'][-6:] for r in records],columns=4,tile=(600,295))
tests=[]
for cat in cats:
    for text in [cat['name_zh'],cat['aliases'][-1]]:tests.append(dict(query=text,expected=cat['category_id'],kind='known_name_or_alias'))
descriptions=['factory material transport trolley','an open jig on a white wheeled assembly base','fixture holding a dark workpiece','a metal rack with multiple shelves','stacked blue plastic boxes','a wheeled cooling appliance with a grille','a flat table used for industrial work','rack with separate vertical slots']
for c,t in zip(cats,descriptions):tests.append(dict(query=t,expected=c['category_id'],kind='unlisted_description'))
for t in ['a forklift truck','an industrial robot arm','a human worker','a living cat','a mountain landscape','未知设备','吊车']:
    tests.append(dict(query=t,expected=None,kind='outside_catalog'))
evaluations={};shared_encoder=None
for variant in ['original','soft_background']:
    query=WorldModel(wm,features_path=out/f'features_{variant}.npz')
    if shared_encoder:query.encoder,query.tokenizer,query.outside_vectors=shared_encoder
    rows=[]
    for case in tests:
        result=query.query(case['query']);match=result.get('target_match',{}).get('category_match',{});actual=match.get('category_id');ok=actual==case['expected']
        rows.append(dict(**case,actual=actual,correct=ok,result=result))
    shared_encoder=(query.encoder,query.tokenizer,query.outside_vectors);evaluations[variant]=dict(correct=sum(r['correct'] for r in rows),total=len(rows),by_kind={k:dict(correct=sum(r['correct'] for r in rows if r['kind']==k),total=sum(r['kind']==k for r in rows)) for k in {r['kind'] for r in rows}},cases=rows)
before=evaluations['original'];after=evaluations['soft_background']
adopt=after['correct']>before['correct'] and all(a['correct'] or not b['correct'] for a,b in zip(after['cases'],before['cases']))
chosen='soft_background' if adopt else 'original';shutil.copy2(out/f'features_{chosen}.npz',wm/'category_features.npz');shutil.copy2(wm/'category_features.npz',out/'category_features.npz');write(out/'categories.json',cats)
write(out/'validation.json',dict(interface='src/query_engine.py WorldModel.query, identical to D runtime',evaluations=evaluations,chosen=chosen,adoption_rule='More correct curated cases and no regression; otherwise retain v1',interpretation='Hand-authored functional sanity checks, not retrieval accuracy or independent benchmark.'))
write(out/'summary.json',dict(categories=8,feature_dimension=512,crops=len(records),modified_crops=sum(r['modified'] for r in comparisons),selected_prototype=chosen,original_correct=before['correct'],soft_correct=after['correct'],total=before['total'],heldout_used=False))

# Independent verification of the existing six-relation geometry against the frozen M0 boxes.
edgekeys={(e['subject'],e['relation'],e['object']) for e in graph['edges']};byid={o['object_id']:o for o in objects};bounds={oid:(corners(o['bbox']).min(0),corners(o['bbox']).max(0)) for oid,o in byid.items()};expected=set()
for aid,a in byid.items():
    alo,ahi=bounds[aid]
    for bid,b in byid.items():
        if aid==bid:continue
        blo,bhi=bounds[bid];gap=np.linalg.norm(np.maximum(np.maximum(blo-ahi,alo-bhi),0))
        for relation,valid in [('left_of',ahi[0]<blo[0]-.02),('right_of',alo[0]>bhi[0]+.02),('in_front_of',alo[1]>bhi[1]+.02),('behind',ahi[1]<blo[1]-.02),('near',gap<.35)]:
            if valid:expected.add((aid,relation,bid))
    for category in cats:
        pool=[b for bid,b in byid.items() if bid!=aid and b['category_id']==category['category_id']]
        if not pool:continue
        distances=[np.linalg.norm(np.array(b['bbox']['center'])-a['bbox']['center']) for b in pool];minimum=min(distances)
        expected.update((b['object_id'],'nearest_to',aid) for b,d in zip(pool,distances) if d<=minimum+1e-6)
assert edgekeys==expected
for s,r,t in edgekeys:
    assert s!=t and s in byid and t in byid
    inverse={'left_of':'right_of','right_of':'left_of','in_front_of':'behind','behind':'in_front_of','near':'near'}.get(r)
    if inverse:assert (t,inverse,s) in edgekeys
write(ROOT/'outputs/C/scene_graph.json',graph)
write(ROOT/'outputs/C/validation.json',dict(nodes=len(graph['nodes']),edges=len(graph['edges']),relation_counts=dict(collections.Counter(e['relation'] for e in graph['edges'])),exact_independent_geometry_agreement=True,inverse_and_near_symmetry=True,self_edges=0,all_node_ids_valid=True,coordinates=graph['coordinate_semantics'],units='SfM relative, not meters',m0_unchanged=True,instance_geometry_used_for_relations=False))
write(wm/'manifest.json',dict(version='saga_relags_v2',objects=33,fine_instances=sum(q['fine_instance_available'] for q in quality.values()),query='query.py',category_features='category_features.npz',scene_graph='scene_graph.json',read_only_dependencies=['models/open_clip_pytorch_model.bin -> original CLIP weights','models/native_scene.ply -> original native 3DGS','instances/*/object.ply -> v2 extraction outputs'],portability='Alias and geometry queries need only this directory and numpy. Description queries additionally require open_clip/torch and the referenced weights; native rendering needs the existing project renderer.'))
print('B',read(out/'summary.json'));print('C',read(ROOT/'outputs/C/validation.json'))
