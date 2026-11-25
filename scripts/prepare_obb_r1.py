"""Create an isolated continuation and snapshot existing Baseline 0 metadata."""
import hashlib,json,pathlib,shutil,datetime
ROOT=pathlib.Path(__file__).resolve().parents[1]
BASE=ROOT/'outputs/relags_baseline'
OUT=ROOT/'outputs/relags_obb_repair_r1'
OUT.mkdir(exist_ok=True)
snapshot=OUT/'baseline0_snapshot';snapshot.mkdir(exist_ok=True)
assert not (snapshot/'baseline_tree.json').exists(), 'Already prepared; do not replace original snapshot'
items=[]
for p in sorted(BASE.rglob('*')):
    if p.is_symlink(): items.append({'path':str(p.relative_to(BASE)),'link':str(p.readlink())})
    elif p.is_file():
        s=p.stat();r={'path':str(p.relative_to(BASE)),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns}
        if s.st_size<1024*1024:r['sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
        items.append(r)
(snapshot/'baseline_tree.json').write_text(json.dumps(items,indent=2))
for name in ['DATA_MIGRATION.md','DATA_MIGRATION.tsv','EXPERIMENT_REPORT.md','BASELINE_STATUS.json','INDUSTRIAL_REVIEW.md','EXECUTION_PLAN.md','README.md']:
    shutil.copy2(ROOT/name,snapshot/name)
for name in ['logs/final_source_manifest.json','logs/patches/all_baseline_adaptations.patch']:
    shutil.copy2(ROOT/name,snapshot/pathlib.Path(name).name)
for stage in ['00_investigation','08_scene_graph','09_relational_query']:
    for folder in ['data','metrics','visualizations']:(OUT/stage/folder).mkdir(parents=True,exist_ok=True)
runner=(ROOT/'scripts/run_stage.py').read_text().replace("ROOT/'outputs/relags_baseline'/args.stage","ROOT/'outputs/relags_obb_repair_r1'/args.stage")
(ROOT/'scripts/run_stage_repair.py').write_text(runner)
model=OUT/'08_scene_graph/data/model'
(model/'point_cloud/iteration_0').mkdir(parents=True,exist_ok=True)
links={model/'point_cloud/iteration_0/point_cloud.ply':BASE/'03_gaussian_pruning/data/model/point_cloud/iteration_0/point_cloud.ply', model/'sai_nag_openseg.pt':BASE/'06_semantic_aggregation/data/model/sai_nag_openseg.pt'}
for dst,src in links.items():dst.symlink_to(src.resolve())
(OUT/'STATUS.json').write_text(json.dumps({'status':'investigating','parent_baseline':'outputs/relags_baseline','created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'baseline_files_snapshotted':len(items),'scope':'OBB boundary-case repair only; original stages and core grouping/GNN/query algorithms remain unchanged'},indent=2))
print('Prepared',OUT,'baseline items',len(items))
