#!/usr/bin/env python3
"""Read-only source audit and verified physical copy into Baseline 0."""
import collections, csv, hashlib, json, os, pathlib, shutil, stat, time
ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = pathlib.Path('/mnt/sda/ubuntu/lkx/papers/paper_eli')
OUT = ROOT / 'outputs/relags_baseline/00_data_check'
STAGES = ['00_data_check','01_gaussian_scene','02_image_encoding','03_gaussian_pruning','04_superpoint_partition','05_hierarchical_grouping','06_semantic_aggregation','07_object_part_modeling','08_scene_graph','09_relational_query']
def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False)+'\n')
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024), b''): h.update(b)
    return h.hexdigest()
def main():
    start=time.time()
    for stage in STAGES:
        for sub in ['data','visualizations','metrics']:
            (ROOT/'outputs/relags_baseline'/stage/sub).mkdir(parents=True,exist_ok=True)
    totals=collections.defaultdict(lambda:{'files':0,'bytes':0,'symlinks':0})
    paper_files=[]
    with (OUT/'data/source_inventory.jsonl').open('w') as f:
        for base, dirs, files in os.walk(SRC,followlinks=False):
            dirs.sort(); files.sort()
            for name in files:
                p=pathlib.Path(base)/name; rel=p.relative_to(SRC)
                try:
                    s=p.lstat(); row={'path':str(p),'relative_path':str(rel),'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'mode':stat.S_IMODE(s.st_mode),'symlink':p.is_symlink()}
                    if p.is_symlink(): row['link_target']=os.readlink(p)
                    f.write(json.dumps(row,ensure_ascii=False)+'\n')
                    t=totals[rel.parts[0]]; t['files']+=1; t['bytes']+=s.st_size; t['symlinks']+=p.is_symlink()
                    if p.suffix.lower() in ['.pdf','.tex','.docx'] and not any(x in rel.parts for x in ['envs','models','runtime','repos','third_party','vendor','node_modules','.git']): paper_files.append(str(rel))
                except OSError as e: f.write(json.dumps({'path':str(p),'error':str(e)})+'\n')
    dump(OUT/'metrics/source_inventory_summary.json',dict(totals))
    dump(OUT/'data/discovered_paper_files.json',paper_files)
    copies=[]
    def add(src,dst,purpose,reference=False):
        s=SRC/src; d=ROOT/dst
        if not s.exists(): return
        if s.is_dir():
            for p in sorted(s.rglob('*')):
                if p.is_file(): add(p.relative_to(SRC),pathlib.Path(dst)/p.relative_to(s),purpose,reference)
            return
        d.parent.mkdir(parents=True,exist_ok=True)
        before=s.stat(); h=sha(s)
        if not d.exists() or sha(d)!=h:
            temp=d.with_name(d.name+'.copying'); shutil.copy2(s,temp,follow_symlinks=True); os.replace(temp,d)
        after=s.stat(); target_hash=sha(d)
        assert h==target_hash and before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns, str(s)
        assert not d.is_symlink() and (s.stat().st_dev,s.stat().st_ino)!=(d.stat().st_dev,d.stat().st_ino)
        copies.append({'source':str(s),'resolved_source':str(s.resolve()),'destination':str(d),'relative_destination':str(d.relative_to(ROOT)),'bytes':d.stat().st_size,'sha256':h,'purpose':purpose,'reference_only':reference,'source_unchanged_size_mtime':True})
        print('VERIFIED',str(d.relative_to(ROOT)),d.stat().st_size,flush=True)
    add('data/raw','data/raw','Original acquisition video')
    add('data/industrial/input','data/images_extracted','Original distorted extracted frames before COLMAP undistortion')
    add('data/industrial/images','data/images','Undistorted RGB; direct geometry and new semantic pipeline input')
    add('data/industrial/sparse','data/colmap/sparse','Original calibrated undistorted COLMAP model and point cloud')
    add('data/industrial/distorted/sparse','data/colmap/distorted_sparse','Original SfM reconstruction before undistortion; provenance')
    add('outputs/reconstruction/point_cloud/iteration_30000','data/gaussian_scene/original_3dgs/point_cloud/iteration_30000','Original unedited 3DGS; compatibility audit and visual reference')
    for name in ['chkpnt30000.pth','cameras.json','cfg_args','input.ply']:
        add('outputs/reconstruction/'+name,'data/gaussian_scene/original_3dgs/'+name,'Original final unedited model metadata/checkpoint; cfg_args archived verbatim, not executed')
    records=['camera_split.json','video_metadata.json','video_sha256.txt','sfm_summary.json','final_sfm_quality.txt','selected_colmap_model.txt','colmap_version.txt','reconstruction.model_check.json','reconstruction_commit.txt','reconstruction_submodules.txt','reconstruction.pip.freeze.txt','common_source_identity.json','edit_image_transform.json','target_view_manifest.json']
    for name in records: add('records/'+name,'data/scene_information/'+name,'Acquisition, cameras, split, reconstruction provenance; historical absolute paths are archival')
    for name in ['README.md','README_reproduction.txt','REPORT.txt','gsle/README.txt','gsle/REPORT.txt','gsle/PAPER_NOTES.txt','gsle/interfaces.json','industrial_swap_v2/README.md','baseline_comparison/README.md']:
        add(name,'previous_work/paper/'+name,'Previous study report and scene/experiment context',True)
    for name in paper_files: add(name,'previous_work/paper/discovered/'+name,'Discovered previous paper source',True)
    for name in ['experiment.json','industrial_adaptation.json','target_geometry.json','target_instance.reviewed.json','common_metrics.json','final_comparison.json','instance_selection_summary.json','gsle/camera_validation.json','gsle/final_visual_review.json']:
        add('records/'+name,'previous_work/reference_results/records/'+name,'Historical semantic/editing/reference information; prohibited as ReLaGS input',True)
    add('industrial_swap_v2/records/m3_placement_173dd1e8.json','previous_work/reference_results/ground_reference.json','Historical ground plane estimated with LangSplat; reference only, not used to orient/scale ReLaGS',True)
    add('industrial_swap_v2/configs','previous_work/reference_results/industrial_swap_configs','Previous experiment settings; reference only',True)
    for name in ['01_preprocess.sh','01b_complete_matching.sh','01c_finalize_sfm.sh','05_reconstruction.sh','prepare_edit_dataset.py','verify_preprocess.py','render_common.py']:
        add('scripts/'+name,'previous_work/paper/source_scripts/'+name,'Historical acquisition/reconstruction procedure; archived, not executed',True)
    for p in sorted((SRC/'outputs/comparison').glob('*.png'))[:8]: add(p.relative_to(SRC),'previous_work/reference_results/previews/'+p.name,'Historical comparison preview; not a new baseline result',True)
    for p in sorted((SRC/'outputs/target_view_check').glob('*.jpg'))[:8]: add(p.relative_to(SRC),'previous_work/reference_results/previews/'+p.name,'Historical scene preview; reference only',True)
    # Internal relative links expose COLMAP layout without depending on the old project.
    sparse=ROOT/'data/sparse'
    if not sparse.exists(): sparse.symlink_to('colmap/sparse',target_is_directory=True)
    split=json.loads((ROOT/'data/scene_information/camera_split.json').read_text())
    images=sorted(p.name for p in (ROOT/'data/images').iterdir() if p.suffix.lower() in ['.png','.jpg','.jpeg'])
    assert len(images)==350 and sorted(split['train']+split['test'])==images
    assert not set(split['train']) & set(split['test'])
    assert split['test']==images[::8]
    refs=[images[i] for i in [0,48,96,144,192,240,288,344]]
    dump(ROOT/'configs/reference_views.json',{'image_names':refs,'render_width':938,'render_height':528,'selection':'Fixed held-out views spanning original trajectory; original COLMAP camera coordinates'})
    dump(OUT/'data/migration_manifest.json',copies)
    with (ROOT/'DATA_MIGRATION.tsv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(copies[0]),delimiter='\t');w.writeheader();w.writerows(copies)
    summary={'status':'completed','files_copied':len(copies),'bytes_copied':sum(x['bytes'] for x in copies),'images':len(images),'train_views':len(split['train']),'test_views':len(split['test']),'all_sha256_verified':True,'source_files_modified':False,'elapsed_seconds':time.time()-start,'excluded':'historical 7000-step checkpoint, edited models, generated models, old semantic arrays/masks, environments, caches, duplicate outputs','paper_files_found':paper_files}
    dump(OUT/'metrics/migration_summary.json',summary)
    dump(OUT/'status.json',summary)
    (ROOT/'DATA_MIGRATION.md').write_text('# Baseline 0 数据迁移记录\n\n源工程：`'+str(SRC)+'`。目标工程：`'+str(ROOT)+'`。\n\n全部采用物理复制，逐文件校验 SHA256；不移动、不删除、不修改源文件。完整逐文件原始路径、解析后的源路径、目标路径、用途及 SHA256 见 [DATA_MIGRATION.tsv](DATA_MIGRATION.tsv) 和 `outputs/relags_baseline/00_data_check/data/migration_manifest.json`。\n\n'+json.dumps(summary,indent=2,ensure_ascii=False)+'\n\n## 输入边界\n\n- `data/images`、`data/colmap`、`data/raw`：原始数据。`data/sparse` 仅为指向本工程 `colmap/sparse` 的相对链接。\n- `data/gaussian_scene/original_3dgs`：原始 3DGS 对照，不能无损当作 2DGS。保留最终 30000 步 PLY 和检查点，省略历史 7000 步文件。\n- `data/scene_information`：相机划分与采集重建记录。历史配置中的绝对路径仅为取证，不用于新运行。\n- `previous_work`：上篇报告、历史分割/定位/编辑及地面参考信息，禁止作为新语义流程输入。旧地面估计依赖 LangSplat，未用于本次姿态或尺度变换。\n- 未发现的论文正文、真实设备型号、相机型号或公制标定不凭空补充。原坐标系保持 COLMAP 原始规范；实际物理尺度待核实。\n\n源目录完整文件元信息清单见 `00_data_check/data/source_inventory.jsonl`。\n')
    (OUT/'config.yaml').write_text(json.dumps({'source':str(SRC),'destination':str(ROOT),'copy_mode':'physical_copy_sha256','split_policy':'preserve_original_every_8th_test'},indent=2)+'\n')
    (OUT/'README.md').write_text('# Stage 00\n\n已完成复制及逐文件校验；输入边界和文件清单见根目录 DATA_MIGRATION.md。源目录无写入操作。\n\n运行：`python3 scripts/00_migrate.py`，可重复执行并检查既有目标文件哈希。无 GPU 计算。可视化将在数据审计工具中从本工程副本生成。\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__': main()
