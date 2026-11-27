from common import *
import os,datetime,subprocess,shutil
verify_locks();assert not (ROOT/'configs/FROZEN.json').exists(),'Already initialized'
for d in ['E01_external_comparison','E02_ablation','E03_entity_construction','E04_relation_retrieval','E05_multiview_application','E06_computational_efficiency','figures','tables','method_figure_assets','source_data','logs','docs','cache/tmp']:(ROOT/d).mkdir(parents=True,exist_ok=True)
protected={}
for root in [V1,V2,BENCH]:
    for folder,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d not in ['envs','cache','git_review','.git','__pycache__']]
        for name in files:
            p=Path(folder)/name
            if p.is_symlink():continue
            st=p.stat();protected[str(p.relative_to(PROJECT))]=[st.st_size,st.st_mtime_ns]
write(ROOT/'source_data/protected_before.json',protected)
critical=[V2/'world_model/query.py',V2/'world_model/scene_graph.json',V2/'world_model/category_features.npz',V2/'inputs/m0_state.json',V2/'outputs/A/frozen_manifest.json',BENCH/'configs/FROZEN.json',BENCH/'evaluation/pseudo_ground_truth/REFERENCE_FROZEN.json']
critical += [PROJECT/p for p in read(V2/'inputs/provenance.json')['checkpoint_hashes']]
critical += list((BENCH/'configs').glob('*.json'))
critical += list((V2/'src').glob('*.py'))
config=dict(native_scene=read(V2/'inputs/manifest.json')['ply'],variants=['box_gated','no_relation','ours','box_all33'],box_gate='same renderable IDs as frozen Ours; never substitute another device',mask_threshold=.5,resolution=[938,528],reference='frozen SAM-assisted Pseudo-GT',aggregation='equal query weight after mean of valid views',empty_precision=0,training=False,reference_changes=False,affinity_checkpoint='iteration_10000',plot_width_mm=180,dpi=450)
write(ROOT/'configs/experiment.json',config);critical.append(ROOT/'configs/experiment.json')
write(ROOT/'configs/FROZEN.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256={str(p.relative_to(PROJECT)):sha(p) for p in critical}))
for source in [V2/'inputs/provenance.json',V2/'outputs/A/frozen_manifest.json',BENCH/'configs/benchmark_queries.json',BENCH/'configs/evaluation_views.json',BENCH/'evaluation/pseudo_ground_truth/sample_manifest.json']:
    shutil.copy2(source,ROOT/'source_data'/source.name)
write(ROOT/'source_data/repositories.json',{str(p):subprocess.run(['git','-C',str(p),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip() for p in [PROJECT/'publication/repository',PROJECT/'ReLaGS',V1/'third_party/SegAnyGAussians']})
(ROOT/'EXPERIMENT_PLAN.md').write_text('''# 实际执行计划

冻结 v2 和现有 SAM 辅助参考。所有新增写入本目录。

1. E01：从二值掩膜重算全部指标；复核 ReLaGS 行号、层次、方向与投影。
2. E02：25 查询 × 2 固定真实视角；Box-based 使用与 Ours 相同精细可用性门控；No Relation 返回全部可用同类实例；另列全部33粗框的补充统计。
3. E03：导出冻结真实亲和度、提示、筛选前后与冲突后集合；统一相机比较粗细实例。
4. E04：实际运行25关系查询，输出全部候选、参照、筛选证据、可用性及图。
5. E05：两查询各三方向固定集合渲染、五条最近查询和困难案例。
6. E06：复核历史耗时边界、日志与存储；不推测未记录成本。
7. F04—F09、T01—T04及F01—F03真实素材；PNG、可编辑SVG、子图、配置、双语图注和来源。
8. 保护复核，完整报告和轻量 Git 归档。

有效样本沿用冻结 23 查询 / 44 查询视角；不利用本轮得分修改实例或参考。
''')
print('Initialized',len(protected),'protected files',flush=True)

