# Stage 08 OBB 排查与修复续跑 R1

本次续跑已完成完整 L2/L3 场景图和原定 6 项关系查询。原始 Baseline 0 的 Stage 08 失败、Stage 09 部分完成状态仍保留，不追写成原法未经修复即成功。

工作目录：`/mnt/sda/ubuntu/lkx/papers/paper_in`。R1 输出目录：`outputs/relags_obb_repair_r1/`。记录时间（UTC）：2026-11-25T01:51:29.847281+00:00。

## 问题来源

证据支持：这是公开实现对极小分组缺少 OBB 边界处理的缺陷，被本工业场景的数据触发；未发现导致这五个组的点顺序、标签或特征行适配错误。不能据此推断所有工业域假设均正确。

- 从固定官方提交 `52cc0c98b0ccf9afebea31901bf79246650286b3` 提取未经修改的 OBB 函数，在原数据上重现全部五处失败。
- 重放未经修改的官方 L2 区域生长函数，全部 816,661 个高斯标签及 Superpoint 分组决策与原结果完全一致。邻接、判定、原始分组和小组后处理四个方法的 AST 与官方一致。
- 原 PLY 顺序与失败前的坐标逐值一致；标签长度、连续 ID、特征行数及 CLIP/OpenSeg 分支标签全部匹配。
- 官方 `merge_proj.py` 只在最后一轮合并极小组；`predict_3d_scene_graph.py` 同时读取 L2/L3。L2 残留单点/三点组是这套代码允许产生的输出。它们都已存在于初始 Superpoint，没有在迁移时被截断。

| 失败 L2 组 | 原始点数 | 离群清理后 | L0→L1→L2→L3 |
|---|---:|---:|---|
| 1822 | 1 | 0 | 13672→6513→1822→745 |
| 1836 | 1 | 0 | 13754→6550→1836→701 |
| 1927 | 1 | 0 | 14662→6887→1927→84 |
| 1987 | 1 | 0 | 15395→7163→1987→745 |
| 2307 | 3 | 3 | 19326→8482→2307→523 |

单点经官方统计离群清理变为空集；三点不能生成三维 Qhull 初始单纯形。对原始/清理后的五组实测 `robust=True` 也全部失败。Open3D 的 robust 选项本身还会引入坐标扰动，本次未采用。

证据：`00_investigation/metrics/root_cause.json`、`00_investigation/data/upstream_*.py`、`00_investigation/data/upstream_l2_replay.pt` 及同目录逐组点/索引 NPZ（均相对于 R1 输出目录）。

## 必要修复的严格范围

新增 `scripts/obb_boundary_r1.py`，由 `scripts/predict_graph_obb_r1.py` 在单次进程内显式启用；原 ReLaGS 工作树没有新增变更。

正常节点继续调用原 OBB 函数。仅在原函数失败且实际点集为 1–3 点时，用原点的 PCA 构造退化包围盒；单点的中心为原点、尺度为零，三点保持零法向厚度。统计离群清理将单点清空时，仅为该节点的几何恢复原始单点。未添加噪声、复制点、膨胀尺度、删除或合并节点；高斯、NAG 标签与特征均未改动。

这明确补充了原实现未定义的几何边界行为，并非声称与原函数失败时存在等价输出。五个节点的方向不可辨识，相关边已单独标记。对全部 3,675 个原本有效的 OBB（L2 2,486 + L3 1,189），中心、旋转和尺度与原诊断记录逐值相同。

单点、线段、三角形、重复点、正常三维点云的确定性/包容性/原值一致性测试已通过。原分组、ROFA、图距离阈值 5.0、GNN 权重与结构、关系嵌入、查询候选和阈值规则均保持原设置。输入坐标仍为未作公制/重力标定的 COLMAP 坐标。

OBB 修复后首次全图预测遇到显存不足，日志保留。改用官方已有的 `--edge_batch_size 400000`：对实际 359,928 条 L3 边和 200,051 条 L2 验证边（含退化节点相关边）比较全批/分批推理，最大特征差异分别为 0 和 5.3644e-7，top-1 关系一致率均为 100%。当前官方模型只有一层，边输出不依赖下一层节点聚合；此等价性不能扩展到多层模型。

## 完整场景图

| 层 | 节点 | 有向边 | 涉及退化 OBB 节点的边 |
|---|---:|---:|---:|
| L2 | 2491 | 1645360 | 52 |
| L3 | 1189 | 359928 | 0 |

节点 ID 连续且与原 NAG 一致，边端点与特征行对应、边键唯一、所有节点几何和边预测有限。全部连续 GNN 边特征、27 类余弦分数、官方 top-1 Jina 原型文件、JSON、PLY、图像与八个固定相机投影已保存。退化几何边标记位于 `08_scene_graph/data/level_2_boundary_edge_flags.npz`，节点策略见 `08_scene_graph/data/node_geometry_quality.json`。

与上一次根层诊断相比，本次 L3 边集完全相同，top-1 关系一致率为 100%，边特征最大绝对差异为 1.1622906e-06。完整官方循环在 L3 前会再次去均值，而旧 root-only 仅去均值一次；该差别需与修复本身区分。逐项验证见 `00_investigation/metrics/final_validation.json`。

## 六项关系查询

沿用 `configs/industrial_queries.json` 和原 `search_triplet_subjects`，topk=10、filter_small=300、相似度阈值 (0.55, 0.4, 0.55)、最多 3 个主体。新执行 6 项关系查询；12 项开放词汇结果经项目内链接复用，明确记录为未重跑。

| 查询 | 选中高斯数 | 官方低阈值回退 | 返回的 subject→object 节点（层） | 图预测关系 |
|---|---:|---|---|---|
| blue plastic bin / close by / industrial machine | 52 | 否 | 2208→2068 (L2) | front |
| gray plastic container / standing on / floor | 52 | 否 | 2208→1608 (L2) | front |
| control cabinet / attached to / industrial machine | 522 | 是 | 195→175 (L3) | smaller than |
| roller / part of / conveyor belt | 13 | 是 | 1446→2068 (L2) | front |
| metal frame / connected to / industrial machine | 1372 | 否 | 399→2449 (L2)；261→179 (L3) | front / close by |
| blue plastic bin / left / gray plastic container | 52 | 否 | 2208→2428 (L2) | close by |

空结果 0 项；使用官方低阈值回退 2 项；选中关系边中涉及退化 OBB 节点的边 0 条。完整候选边、subject/relation/object 三个分数、实际选中节点及对应高斯、八视角投影见 `09_relational_query/data/relation_00` 至 `relation_05` 和 `09_relational_query/metrics/relational_review.json`。展示总图为 `09_relational_query/visualizations/relational_query_overview.jpg`，红色只表示选中主体。

查询返回非空或使用阈值回退，不等于所询问的关系真实成立。报告同时给出图预测类别，不能把查询中的关系词当成预测标签；若图预测类别不同，则仍按官方语义相似度与回退逻辑如实保留。没有关系真值，不报告准确率。

## 原始基线保护与恢复

最终核验确认原 Baseline 0 的 4298 个文件/链接没有新增、修改或删除；普通文件大小和纳秒修改时间均一致，小于 1 MiB 的文件另核 SHA256。原 ReLaGS 源码差异的 SHA256 与续跑前一致。原始根目录报告、迁移记录、状态和代码清单另存 `baseline0_snapshot/`。

本次不重跑 Stage 00–07，直接只读复用其 PLY/NAG/特征。R1 的独立记录器为 `scripts/run_stage_repair.py`，各阶段保留独立的 `runs/`、输入快照、命令、日志、每 5 秒显存采样、耗时和返回码。失败尝试不覆盖。后续查看完整原命令可直接读取各 attempt 的 `command.sh`。

`scripts/continue_obb_r1.py` 可在成功图已存在时恢复导出和查询；`scripts/analyze_obb_r1.py` 核验并重新生成检查图；`scripts/report_obb_r1.py` 更新本报告。不要用旧的 `scripts/update_report.py` 覆盖原 Baseline 0 阶段记录。更改方法或输入应建立新输出目录。

## 证据与上游来源

- [官方层次分组源码](https://github.com/dfki-av/ReLaGS/blob/52cc0c98b0ccf9afebea31901bf79246650286b3/merge_proj.py)：小组后处理只在末轮。
- [官方 OBB 函数](https://github.com/dfki-av/ReLaGS/blob/52cc0c98b0ccf9afebea31901bf79246650286b3/scene_graph/network_utils.py)：无极小点集保护。
- [Open3D OBB 文档](https://www.open3d.org/docs/release/python_api/open3d.geometry.OrientedBoundingBox.html)：凸包 PCA 和 robust 的坐标噪声行为。
- 原论文及附录、固定源码版本和环境沿用 Baseline 0；未变更论文方法或增加工业语义监督。

## 关系查询的实际视觉检查

已查看六查询总图、放大对照图、relation_00 的第 241 帧原尺寸叠加图，以及完整 L2 图的第 49 帧投影。放大图只用于显示已存在的浮点投影，不改变原查询掩膜。

- relation_00（蓝箱靠近设备）、relation_01（灰色容器位于地面上）和 relation_05（蓝箱在灰色容器左侧）返回完全相同的 L2 组 2208，共 52 个高斯。第 241 帧可见红色只覆盖蓝色堆箱的局部小片段；没有分出完整箱体。灰色容器查询也选中这个蓝箱片段，属于明确需要标注核查的类别混淆。三者在该视角投影大于 0.5 的像素均为 95。
- relation_02（控制柜附着于设备）触发官方回退：关系相似度 0.25844，小于 0.4；图预测类别为 smaller than。所选主体在第 241 帧主要落于右边界附近的局部结构，不能凭该结果确认控制柜身份或附着关系。
- relation_03（滚筒是输送带的部件）触发官方回退：主体相似度 0.48776，小于 0.55，只选中 13 个高斯。最佳固定视角第 241 帧最大投影权重仅 0.17342，超过 0.5 的像素为 0；未形成可辨识的完整滚筒定位。图预测类别为 front，不能把请求中的 part of 当成预测结果。
- relation_04（金属框架连接设备）包含 L2 399 和 L3 261，共 1,372 个高斯；第 1 帧可见选中上方/背景金属结构。类别外观与框架有一定对应，但选中边的图类别为 front / close by，无法据此确认 connected to。
- 完整 L2 场景图在第 49 帧能投影显示节点和边；画面只展示 269,134 条两端在视锥内边中的 20 条，未做遮挡判断。投影可查看不代表边具有真实物理关系，完整原始边和分数另存。

六项查询中选中边均不直接涉及本次五个退化 OBB 节点；原分组与语义特征均未修改。上述语义/关系问题不能简单归因于 OBB 修复。它们提示层次叶组选择、领域外语义表征、关系原型相似度及官方回退规则仍需后续独立评估。本次只记录，不调整查询或网络。

证据：`09_relational_query/metrics/relational_review.json`、`relational_localization_diagnostics.json`、原始 `data/relation_*/raw_query.pt`、`visualizations/relational_query_overview.jpg` 和 `relational_query_crops.jpg`（相对于 R1 输出目录）。投影统计不是定位准确率。


## 全部执行记录

| 阶段/任务 | 状态 | 秒 | 显存采样峰值 MiB | 日志 |
|---|---|---:|---:|---|
| 00_investigation/root_cause | failed | 5.69 | 992 | `00_investigation/runs/20261125T013805Z_root_cause/run.log` |
| 00_investigation/root_cause | completed | 16.42 | 992 | `00_investigation/runs/20261125T013933Z_root_cause/run.log` |
| 00_investigation/obb_boundary_tests | failed | 2.49 | 0 | `00_investigation/runs/20261125T013949Z_obb_boundary_tests/run.log` |
| 00_investigation/obb_boundary_tests | completed | 2.82 | 0 | `00_investigation/runs/20261125T014026Z_obb_boundary_tests/run.log` |
| 00_investigation/edge_batch_validation | completed | 11.89 | 4146 | `00_investigation/runs/20261125T014152Z_edge_batch_validation/run.log` |
| 00_investigation/final_validation | failed | 4.13 | 0 | `00_investigation/runs/20261125T014648Z_final_validation/run.log` |
| 00_investigation/final_validation | completed | 9.38 | 0 | `00_investigation/runs/20261125T014807Z_final_validation/run.log` |
| 08_scene_graph/predict_full_graph | failed | 33.15 | 31146 | `08_scene_graph/runs/20261125T014029Z_predict_full_graph/run.log` |
| 08_scene_graph/predict_full_graph | completed | 133.29 | 15822 | `08_scene_graph/runs/20261125T014233Z_predict_full_graph/run.log` |
| 08_scene_graph/export_full_graph | completed | 69.66 | 0 | `08_scene_graph/runs/20261125T014509Z_export_full_graph/run.log` |
| 08_scene_graph/project_full_graph | completed | 18.13 | 0 | `08_scene_graph/runs/20261125T014509Z_project_full_graph/run.log` |
| 09_relational_query/six_relational_queries | completed | 98.97 | 3718 | `09_relational_query/runs/20261125T014509Z_six_relational_queries/run.log` |
| 09_relational_query/localization_review | completed | 0.49 | 0 | `09_relational_query/runs/20261125T014944Z_localization_review/run.log` |

显存为每 5 秒采样；OOM 日志给出的瞬时占用高于采样峰值，二者不混用。排查脚本缺失导入、单点测试维度处理及审计时普通 diff 与原 binary diff 的格式不一致均已修正，失败尝试保留；未因此修改原始科学结果。
