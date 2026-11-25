"""Publish R1 evidence while keeping all Baseline 0 stage files immutable."""
import datetime,hashlib,json,pathlib,shutil
ROOT=pathlib.Path(__file__).resolve().parents[1];OUT=ROOT/'outputs/relags_obb_repair_r1';SNAP=OUT/'baseline0_snapshot'
def read(p):return json.loads(p.read_text())
validation=read(OUT/'00_investigation/metrics/final_validation.json');assert validation['status']=='verified'
cause=read(OUT/'00_investigation/metrics/root_cause.json');batch=read(OUT/'00_investigation/metrics/edge_batch_validation.json')
obb=read(OUT/'08_scene_graph/metrics/obb_repair.json');queries=read(OUT/'09_relational_query/metrics/relational_review.json')['queries']
now=datetime.datetime.now(datetime.timezone.utc).isoformat()
rows=['| 查询 | 选中高斯数 | 官方低阈值回退 | 返回的 subject→object 节点（层） | 图预测关系 |','|---|---:|---|---|---|']
for r in queries:
    q=r['query'];pairs='；'.join(f"{e['subject_cluster']}→{e['object_cluster']} (L{e['level']})" for e in r['selected_edge_evidence'])
    relations=' / '.join(e['predicted_relation_class'] for e in r['selected_edge_evidence'])
    rows.append(f"| {q['subject']} / {q['relation']} / {q['object']} | {r['selected_gaussians']} | {'是' if r['official_threshold_fallback_used'] else '否'} | {pairs or '空'} | {relations or '空'} |")
graph_table=['| 层 | 节点 | 有向边 | 涉及退化 OBB 节点的边 |','|---|---:|---:|---:|']
for r in validation['graph_levels']:graph_table.append(f"| L{r['level']} | {r['nodes']} | {r['edges']} | {r['edges_incident_to_boundary_nodes']} |")
lineage=['| 失败 L2 组 | 原始点数 | 离群清理后 | L0→L1→L2→L3 |','|---|---:|---:|---|']
for r in cause['failure_groups']:
    chain='→'.join('/'.join(map(str,x['ancestor_ids'])) for x in r['lineage'])
    lineage.append(f"| {r['cluster_id']} | {r['raw_count']} | {r['post_outlier_count']} | {chain} |")
report=f'''# Stage 08 OBB 排查与修复续跑 R1

本次续跑已完成完整 L2/L3 场景图和原定 6 项关系查询。原始 Baseline 0 的 Stage 08 失败、Stage 09 部分完成状态仍保留，不追写成原法未经修复即成功。

工作目录：`/mnt/sda/ubuntu/lkx/papers/paper_in`。R1 输出目录：`outputs/relags_obb_repair_r1/`。记录时间（UTC）：{now}。

## 问题来源

证据支持：这是公开实现对极小分组缺少 OBB 边界处理的缺陷，被本工业场景的数据触发；未发现导致这五个组的点顺序、标签或特征行适配错误。不能据此推断所有工业域假设均正确。

- 从固定官方提交 `52cc0c98b0ccf9afebea31901bf79246650286b3` 提取未经修改的 OBB 函数，在原数据上重现全部五处失败。
- 重放未经修改的官方 L2 区域生长函数，全部 816,661 个高斯标签及 Superpoint 分组决策与原结果完全一致。邻接、判定、原始分组和小组后处理四个方法的 AST 与官方一致。
- 原 PLY 顺序与失败前的坐标逐值一致；标签长度、连续 ID、特征行数及 CLIP/OpenSeg 分支标签全部匹配。
- 官方 `merge_proj.py` 只在最后一轮合并极小组；`predict_3d_scene_graph.py` 同时读取 L2/L3。L2 残留单点/三点组是这套代码允许产生的输出。它们都已存在于初始 Superpoint，没有在迁移时被截断。

'''+'\n'.join(lineage)+'''

单点经官方统计离群清理变为空集；三点不能生成三维 Qhull 初始单纯形。对原始/清理后的五组实测 `robust=True` 也全部失败。Open3D 的 robust 选项本身还会引入坐标扰动，本次未采用。

证据：`00_investigation/metrics/root_cause.json`、`00_investigation/data/upstream_*.py`、`00_investigation/data/upstream_l2_replay.pt` 及同目录逐组点/索引 NPZ（均相对于 R1 输出目录）。

## 必要修复的严格范围

新增 `scripts/obb_boundary_r1.py`，由 `scripts/predict_graph_obb_r1.py` 在单次进程内显式启用；原 ReLaGS 工作树没有新增变更。

正常节点继续调用原 OBB 函数。仅在原函数失败且实际点集为 1–3 点时，用原点的 PCA 构造退化包围盒；单点的中心为原点、尺度为零，三点保持零法向厚度。统计离群清理将单点清空时，仅为该节点的几何恢复原始单点。未添加噪声、复制点、膨胀尺度、删除或合并节点；高斯、NAG 标签与特征均未改动。

这明确补充了原实现未定义的几何边界行为，并非声称与原函数失败时存在等价输出。五个节点的方向不可辨识，相关边已单独标记。对全部 3,675 个原本有效的 OBB（L2 2,486 + L3 1,189），中心、旋转和尺度与原诊断记录逐值相同。

单点、线段、三角形、重复点、正常三维点云的确定性/包容性/原值一致性测试已通过。原分组、ROFA、图距离阈值 5.0、GNN 权重与结构、关系嵌入、查询候选和阈值规则均保持原设置。输入坐标仍为未作公制/重力标定的 COLMAP 坐标。

OBB 修复后首次全图预测遇到显存不足，日志保留。改用官方已有的 `--edge_batch_size 400000`：对实际 359,928 条 L3 边和 200,051 条 L2 验证边（含退化节点相关边）比较全批/分批推理，最大特征差异分别为 0 和 5.3644e-7，top-1 关系一致率均为 100%。当前官方模型只有一层，边输出不依赖下一层节点聚合；此等价性不能扩展到多层模型。

## 完整场景图

'''+'\n'.join(graph_table)+f'''

节点 ID 连续且与原 NAG 一致，边端点与特征行对应、边键唯一、所有节点几何和边预测有限。全部连续 GNN 边特征、27 类余弦分数、官方 top-1 Jina 原型文件、JSON、PLY、图像与八个固定相机投影已保存。退化几何边标记位于 `08_scene_graph/data/level_2_boundary_edge_flags.npz`，节点策略见 `08_scene_graph/data/node_geometry_quality.json`。

与上一次根层诊断相比，本次 L3 边集完全相同，top-1 关系一致率为 {validation['graph_levels'][1]['prior_root_top1_agreement']:.0%}，边特征最大绝对差异为 {validation['graph_levels'][1]['prior_root_max_abs_feature_difference']:.8g}。完整官方循环在 L3 前会再次去均值，而旧 root-only 仅去均值一次；该差别需与修复本身区分。逐项验证见 `00_investigation/metrics/final_validation.json`。

## 六项关系查询

沿用 `configs/industrial_queries.json` 和原 `search_triplet_subjects`，topk=10、filter_small=300、相似度阈值 (0.55, 0.4, 0.55)、最多 3 个主体。新执行 6 项关系查询；12 项开放词汇结果经项目内链接复用，明确记录为未重跑。

'''+'\n'.join(rows)+f'''

空结果 {validation['empty_relational_results']} 项；使用官方低阈值回退 {validation['official_threshold_fallback_queries']} 项；选中关系边中涉及退化 OBB 节点的边 {validation['selected_edges_touching_degenerate_obb']} 条。完整候选边、subject/relation/object 三个分数、实际选中节点及对应高斯、八视角投影见 `09_relational_query/data/relation_00` 至 `relation_05` 和 `09_relational_query/metrics/relational_review.json`。展示总图为 `09_relational_query/visualizations/relational_query_overview.jpg`，红色只表示选中主体。

查询返回非空或使用阈值回退，不等于所询问的关系真实成立。报告同时给出图预测类别，不能把查询中的关系词当成预测标签；若图预测类别不同，则仍按官方语义相似度与回退逻辑如实保留。没有关系真值，不报告准确率。

## 原始基线保护与恢复

最终核验确认原 Baseline 0 的 {validation['baseline0_items_unchanged']} 个文件/链接没有新增、修改或删除；普通文件大小和纳秒修改时间均一致，小于 1 MiB 的文件另核 SHA256。原 ReLaGS 源码差异的 SHA256 与续跑前一致。原始根目录报告、迁移记录、状态和代码清单另存 `baseline0_snapshot/`。

本次不重跑 Stage 00–07，直接只读复用其 PLY/NAG/特征。R1 的独立记录器为 `scripts/run_stage_repair.py`，各阶段保留独立的 `runs/`、输入快照、命令、日志、每 5 秒显存采样、耗时和返回码。失败尝试不覆盖。后续查看完整原命令可直接读取各 attempt 的 `command.sh`。

`scripts/continue_obb_r1.py` 可在成功图已存在时恢复导出和查询；`scripts/analyze_obb_r1.py` 核验并重新生成检查图；`scripts/report_obb_r1.py` 更新本报告。不要用旧的 `scripts/update_report.py` 覆盖原 Baseline 0 阶段记录。更改方法或输入应建立新输出目录。

## 证据与上游来源

- [官方层次分组源码](https://github.com/dfki-av/ReLaGS/blob/52cc0c98b0ccf9afebea31901bf79246650286b3/merge_proj.py)：小组后处理只在末轮。
- [官方 OBB 函数](https://github.com/dfki-av/ReLaGS/blob/52cc0c98b0ccf9afebea31901bf79246650286b3/scene_graph/network_utils.py)：无极小点集保护。
- [Open3D OBB 文档](https://www.open3d.org/docs/release/python_api/open3d.geometry.OrientedBoundingBox.html)：凸包 PCA 和 robust 的坐标噪声行为。
- 原论文及附录、固定源码版本和环境沿用 Baseline 0；未变更论文方法或增加工业语义监督。
'''
review_note=OUT/'09_relational_query/VISUAL_REVIEW.md'
if review_note.exists():report+='\n'+review_note.read_text()+'\n'
resource_rows=['| 阶段/任务 | 状态 | 秒 | 显存采样峰值 MiB | 日志 |','|---|---|---:|---:|---|']
for stage in ['00_investigation','08_scene_graph','09_relational_query']:
    jobs=[]
    for p in sorted((OUT/stage/'runs').glob('*/status.json')):
        d=read(p);jobs.append(d)
        resource_rows.append(f"| {stage}/{d['job']} | {d['status']} | {d.get('elapsed_seconds',0):.2f} | {d.get('peak_sampled_own_gpu_mib',0)} | `{p.parent.relative_to(OUT)}/run.log` |")
    (OUT/stage/'config.yaml').write_text(json.dumps({'stage':stage,'jobs':jobs},indent=2))
    (OUT/stage/'status.json').write_text(json.dumps({'status':'completed_with_documented_boundary_repair' if stage=='08_scene_graph' else 'completed','parent_baseline_untouched':True,'report':'../OBB_REPAIR_REPORT.md'},indent=2))
    (OUT/stage/'README.md').write_text(f'# {stage} — R1\n\n本阶段已完成，参见 `../OBB_REPAIR_REPORT.md`。输入与实际命令见 `config.yaml` 和逐次 `runs/*/command.sh`；原始数据在 `data/`，可视化在 `visualizations/`，检查结果在 `metrics/`。原 Baseline 0 不变。\n\n'+ '\n\n'.join('`'+d['shell_command']+'`\n\n日志：`'+str(pathlib.Path(d['attempt']).relative_to(OUT))+'/run.log`' for d in jobs))
report+='\n## 全部执行记录\n\n'+'\n'.join(resource_rows)+'\n\n显存为每 5 秒采样；OOM 日志给出的瞬时占用高于采样峰值，二者不混用。排查脚本缺失导入、单点测试维度处理及审计时普通 diff 与原 binary diff 的格式不一致均已修正，失败尝试保留；未因此修改原始科学结果。\n'
(OUT/'OBB_REPAIR_REPORT.md').write_text(report);(ROOT/'OBB_REPAIR_REPORT.md').write_text(report)
(OUT/'08_scene_graph/data/node_geometry_quality.json').write_text(json.dumps({'normal_boxes_unchanged':3675,'flags':[{'level':r['level'],'cluster_id':r['cluster_id'],'affine_rank':r['affine_rank'],'orientation_underdetermined':True,'extent':r['extent']} for r in obb['fallbacks']]},indent=2))
state={**validation,'status':'completed_with_obb_boundary_repair','time_utc':now,'output_root':str(OUT),'original_baseline_status_preserved':True}
(OUT/'STATUS.json').write_text(json.dumps(state,indent=2));(ROOT/'REPAIR_STATUS.json').write_text(json.dumps(state,indent=2))
old=(SNAP/'EXPERIMENT_REPORT.md').read_text()
(ROOT/'EXPERIMENT_REPORT.md').write_text('# ReLaGS 工业场景实验报告：Baseline 0 与 R1 续跑\n\n**最新：R1 已完成完整场景图和 6 项关系查询；原 Baseline 0 的失败记录保持原样。**\n\n'+report+'\n\n---\n\n## 原始 Baseline 0 执行记录（历史状态，不代表 R1 状态）\n\n'+old)
t=(SNAP/'README.md').read_text().replace('## 本次实际结果','## 原始 Baseline 0 实际结果（历史状态）')
t=t.replace('## 执行','## R1 续跑已完成\n\n完整 L2/L3 图和 6 项关系查询已完成；详见 `OBB_REPAIR_REPORT.md`、`REPAIR_STATUS.json`。独立结果位于 `outputs/relags_obb_repair_r1/`。原始 `outputs/relags_baseline/` 和 `BASELINE_STATUS.json` 保留失败事实。原根目录文档快照在新目录的 `baseline0_snapshot/`。\n\n## 执行',1)
(ROOT/'README.md').write_text(t)
(ROOT/'DATA_MIGRATION.md').write_text((SNAP/'DATA_MIGRATION.md').read_text()+'''\n## R1 续跑的数据复用\n\n本次未再复制或修改 `paper_eli` 文件，798 个迁移文件与原 TSV 不变。`outputs/relags_obb_repair_r1/08_scene_graph/data/model/` 通过本项目内部只读使用的链接复用 Baseline 0 Stage 03 PLY 和 Stage 06 OpenSeg NAG；R1 Stage 09 链接复用原 12 项开放词汇数据和可视化。新写入项仅为排查、OBB 边界处理后的完整场景图、6 项关系查询和记录。原 Baseline 0 4298 个文件/链接经最终核验未改变。详见 `OBB_REPAIR_REPORT.md`。\n''')
(ROOT/'EXECUTION_PLAN.md').write_text((SNAP/'EXECUTION_PLAN.md').read_text()+'''\n## R1 续跑执行完成\n\n按用户新增要求，独立封存 Baseline 0 元信息与报告；重放官方 L2 并重现 OBB 失败；为 1–3 点补充退化 PCA 包围盒；验证正常节点逐值一致；使用验证过的官方边分批参数完成完整 L2/L3 图；执行原 6 项关系查询并保存全部中间结果；最后核验原基线未变。结果与限制见 `OBB_REPAIR_REPORT.md`。\n''')
(ROOT/'INDUSTRIAL_REVIEW.md').write_text('# 工业场景检查：R1 更新\n\n完整图与六项关系查询现已执行；具体查询返回、阈值回退及几何边界限制见 `OBB_REPAIR_REPORT.md`。此前的分割、粗层合并、标线/地面混淆等问题不因流程跑通而消失。\n\n'+(review_note.read_text() if review_note.exists() else '')+'\n\n## 原始 Baseline 0 检查（历史记录）\n\n'+(SNAP/'INDUSTRIAL_REVIEW.md').read_text())
files=list((ROOT/'scripts').glob('*obb*r1.py'))+[ROOT/'scripts/run_stage_repair.py',ROOT/'scripts/verify_edge_batch_r1.py',ROOT/'scripts/review_relations_r1.py',ROOT/'scripts/query_baseline.py',ROOT/'scripts/export_scene_graph.py',ROOT/'scripts/project_scene_graph.py',ROOT/'configs/industrial_queries.json']
manifest={str(p.relative_to(ROOT)):{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files if p.is_file()}
(OUT/'source_manifest.json').write_text(json.dumps({'files':manifest,'parent_source_manifest':'baseline0_snapshot/final_source_manifest.json','relags_source_unchanged':True},indent=2))
print(json.dumps({'status':state['status'],'report':str(ROOT/'OBB_REPAIR_REPORT.md'),'queries':len(queries)}))
