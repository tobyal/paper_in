# ReLaGS 工业场景实验报告：Baseline 0 与 R1 续跑

**最新：R1 已完成完整场景图和 6 项关系查询；原 Baseline 0 的失败记录保持原样。**

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


---

## 原始 Baseline 0 执行记录（历史状态，不代表 R1 状态）

# ReLaGS 工业场景复现报告 — Baseline 0

更新时间（北京时间）：2026-11-25T09:03:45.853062+08:00。

**Baseline 0 本次执行已留档：Stage 00–07 完成；完整 Stage 08 在官方 OBB 构建失败；Stage 09 完成 12 个开放词汇查询，6 个完整关系查询未执行。独立根层关系图为诊断结果，不能视作完整复现成功。**

这是基于真实执行状态生成的报告。**尚未生成的结果不视为复现成功**，具体状态见下表。

工作目录：`/mnt/sda/ubuntu/lkx/papers/paper_in`。原工程严格只读。执行方案见 `EXECUTION_PLAN.md`；迁移见 `DATA_MIGRATION.md` 和逐文件 `DATA_MIGRATION.tsv`。

| 阶段 | 内容 | 实际状态 | 位置 |
|---|---|---|---|
| 00 | 原工程审计与迁移 | 完成并核验 | `outputs/relags_baseline/00_data_check/` |
| 01 | 2DGS 场景准备 | 完成并核验 | `outputs/relags_baseline/01_gaussian_scene/` |
| 02 | 二维分割与语言编码 | 完成并核验 | `outputs/relags_baseline/02_image_encoding/` |
| 03 | 最大权重裁剪 | 完成并核验 | `outputs/relags_baseline/03_gaussian_pruning/` |
| 04 | 初始几何邻接与划分 | 完成并核验 | `outputs/relags_baseline/04_superpoint_partition/` |
| 05 | 层次分组 | 完成并核验 | `outputs/relags_baseline/05_hierarchical_grouping/` |
| 06 | ROFA 语义聚合 | 完成并核验 | `outputs/relags_baseline/06_semantic_aggregation/` |
| 07 | 对象与部件导出 | 完成并核验 | `outputs/relags_baseline/07_object_part_modeling/` |
| 08 | 场景图与关系预测 | 完整场景图失败；根层诊断完成 | `outputs/relags_baseline/08_scene_graph/` |
| 09 | 开放词汇与关系查询 | 开放词汇完成；完整关系查询受阻 | `outputs/relags_baseline/09_relational_query/` |

## 已确认的适配与边界

- 旧 3DGS 的三轴椭球与官方 2DGS 面元不兼容；重用原图像/COLMAP，重新训练 2DGS。详细静态证据：`outputs/relags_baseline/01_gaussian_scene/data/compatibility_audit.json`。
- 固定原划分：306 训练、44 测试。统一参考相机见 `configs/reference_views.json`。保留原 COLMAP 坐标，不擅自宣称米制或用旧 LangSplat 地面调整。
- 512D OpenCLIP 用于开放词汇查询；关系网络需要 768D OpenSeg。同维度 CLIP 不能替代 OpenSeg。采用作者指向的 OpenSeg 函数与公开官方权重进行数据接口适配。
- 原始 MWP 阈值按论文/launcher 取 0.0005；ROFA tau=3。配置与 CLI 默认存在差异，详见执行方案。
- 首次 sp_partition 只构造 KNN，真正 Cut Pursuit 在 graph_weight 后执行。层次分组与 ROFA 在同一脚本中交替发生，保存钩子不改变公式、阈值或合并决策。
- 非核心补丁：明确随机种子、项目内同一预训练权重路径、完整特征文件对恢复、保留异常堆栈、保存中间张量。补丁见 `logs/patches/`。
- 没有独立语义、实例或关系 GT，不能虚构准确率/mIoU；工业设备型号与公制尺寸缺少来源时标记未知。
- 共享 GPU，耗时含记录开销，显存为每 5 秒进程采样峰值；不解释为独占硬件论文速度。

## Stage 00：原工程审计与迁移

状态：**完成并核验**。

输入：原视频、去畸变图、COLMAP、最终 3DGS、历史资料。

预期输出：数据副本、逐文件清单、SHA256、相机划分与统一视角。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/00_data_check/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `final_integrity_check`：completed；命令：`python scripts/audit_final.py`；日志：`outputs/relags_baseline/00_data_check/runs/20261125T005714Z_final_integrity_check/run.log`。 耗时 29.60 秒；进程显存采样峰值 0 MiB。
- `scene_audit`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/audit_scene.py`；日志：`outputs/relags_baseline/00_data_check/runs/20261124T145230Z_scene_audit/run.log`。 耗时 5.14 秒；进程显存采样峰值 0 MiB。

实际证据与限制：

已记录 798 个复制文件，共 5,932,662,465 字节；各文件源/目标/SHA256/用途见根目录 TSV。原视频、350 张原始提取图、350 张去畸变图及 COLMAP 均为独立副本。

未找到原论文完整正文；保留已有报告、图表和实验说明，不补造相机/无人机型号或工业设备规格。旧语义与编辑结果仅作参考，不作为新模块输入。



### 最终交付审计

798 个目标复制文件 SHA256 全部一致；798 个源文件大小和纳秒修改时间均与初始清单一致，无审计覆盖缺失。数据/模型/输出下 32 个链接全部有效且在新工程内部；未检测到运行中的阶段作业。结果见 `metrics/final_integrity.json`。这验证文件完整性，不代表语义准确率或完整关系流程成功。

记录器曾出现任务元信息文件与科学统计同名的冲突，已修正命名；Stage 00 从原始字节副本恢复统计，Stage 02 重新只读统计后 SHA256 与首次统计一致。历史日志未删除，修复证据见根目录 `logs/runner_metric_collision.json`。


## Stage 01：2DGS 场景准备

状态：**完成并核验**。

输入：原始 RGB、COLMAP、306/44 划分。

预期输出：官方 2DGS 检查点、PLY、统一相机渲染和重建指标。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/01_gaussian_scene/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `build_2dgs_wheels`：failed；命令：`python -m pip wheel --no-deps --no-build-isolation --wheel-dir wheels external/2d-gaussian-splatting/submodules/diff-surfel-rasterization ReLaGS/submodules/simple-knn`；日志：`outputs/relags_baseline/01_gaussian_scene/runs/20261124T144815Z_build_2dgs_wheels/run.log`。 耗时 176.58 秒；进程显存采样峰值 0 MiB。 输出校验异常：`FileNotFoundError(2, 'No such file or directory')`。
- `checkpoint7000_preview`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/render_views.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/01_gaussian_scene/data/model --iteration 7000 --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/01_gaussian_scene/visualizations/checkpoint7000`；日志：`outputs/relags_baseline/01_gaussian_scene/runs/20261124T150851Z_checkpoint7000_preview/run.log`。 耗时 33.30 秒；进程显存采样峰值 1030 MiB。
- `render_2dgs`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/render_views.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/01_gaussian_scene/data/model --iteration 30000 --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/01_gaussian_scene/visualizations/reconstruction --all-test`；日志：`outputs/relags_baseline/01_gaussian_scene/runs/20261124T152325Z_render_2dgs/run.log`。 耗时 68.67 秒；进程显存采样峰值 2184 MiB。
- `train_2dgs`：completed；命令：`python train.py -s /mnt/sda/ubuntu/lkx/papers/paper_in/data -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/01_gaussian_scene/data/model --eval -r 2 --iterations 30000 --save_iterations 7000 30000 --test_iterations 7000 30000 --checkpoint_iterations 7000 15000 30000 --ip 127.0.0.1 --port 16926`；日志：`outputs/relags_baseline/01_gaussian_scene/runs/20261124T150320Z_train_2dgs/run.log`。 耗时 1205.75 秒；进程显存采样峰值 2400 MiB。
实际观察：官方 2DGS 完成 30000 步并保存检查点；44 留出视角完成官方 ReLaGS 渲染器验证。重建实际质量见可视化和指标。


实际证据与限制：

7000 步预览（非最终结果）：613,573 个二维高斯；8 个相机；平均 PSNR=24.2229 dB，SSIM=0.81598。输入 RGB 归一化到 [0,1]；官方函数直接比较浮点渲染与真值，使用约半分辨率相机，计算指标前未将渲染量化为 PNG。

30000 步最终重建：865,920 个二维高斯；44 个相机；平均 PSNR=26.9838 dB，SSIM=0.89311。输入 RGB 归一化到 [0,1]；官方函数直接比较浮点渲染与真值，使用约半分辨率相机，计算指标前未将渲染量化为 PNG。

首次训练在 7000 步可视化处因 Matplotlib 移除 tostring_rgb 失败；只更换画布 RGB 读取 API 后重新训练，原失败日志保留。此时尚未保存首次 7000 检查点，未伪称从失败点恢复。

人工查看统一八视角的 7000/30000 步预览：主设备阵列、机架、料箱与地面标线可辨认；30000 步比 7000 步局部更清晰，远处货物/背景及地面反射仍有模糊。最终 44 视角平均 PSNR=26.9838412892 dB，SSIM=0.8931126987；最差留出视角 frame_000297 为 20.69827 dB，frame_000121 为 22.98824 dB。低纹理/反光、遮挡和视角覆盖可能是误差来源，尚未通过消融验证，未据此调参。


## Stage 02：二维分割与语言编码

状态：**完成并核验**。

输入：工业 RGB、原始 SAM/OpenCLIP/OpenSeg 权重。

预期输出：全新四层掩膜、512D CLIP、768D OpenSeg、可视化。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/02_image_encoding/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `diagnostics_partial_50`：completed；命令：`python scripts/encoding_diagnostics.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T162615Z_diagnostics_partial_50/run.log`。 耗时 20.53 秒；进程显存采样峰值 0 MiB。
- `diagnostics_partial_reference145`：completed；命令：`python scripts/encoding_diagnostics.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T190631Z_diagnostics_partial_reference145/run.log`。 耗时 45.15 秒；进程显存采样峰值 0 MiB。
- `encoding_diagnostics`：completed；命令：`python scripts/encoding_diagnostics.py`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261125T002908Z_encoding_diagnostics/run.log`。 耗时 61.81 秒；进程显存采样峰值 0 MiB。
- `openseg_all`：completed；命令：`envs/openseg/bin/python scripts/encode_openseg.py --follow`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T153443Z_openseg_all/run.log`。 耗时 31170.65 秒；进程显存采样峰值 8478 MiB。
- `openseg_probe_cu118`：completed；命令：`envs/openseg/bin/python scripts/encode_openseg.py --probe`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T145732Z_openseg_probe_cu118/run.log`。 耗时 29.33 秒；进程显存采样峰值 8482 MiB。
- `sam_clip`：failed；命令：`python scripts/image_encoding.py --source_path /mnt/sda/ubuntu/lkx/papers/paper_in/data --save_dir /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/02_image_encoding/data/language_features --sam_ckpt_path /mnt/sda/ubuntu/lkx/papers/paper_in/models/sam/sam_vit_h_4b8939.pth`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T145436Z_sam_clip/run.log`。 耗时 666.51 秒；进程显存采样峰值 19432 MiB。 输出校验异常：`FileNotFoundError(2, 'No such file or directory')`。
- `sam_clip_shard_0`：completed；命令：`python scripts/image_encoding.py --source_path /mnt/sda/ubuntu/lkx/papers/paper_in/data --save_dir /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/02_image_encoding/data/language_features --sam_ckpt_path /mnt/sda/ubuntu/lkx/papers/paper_in/models/sam/sam_vit_h_4b8939.pth --image-list /mnt/sda/ubuntu/lkx/papers/paper_in/configs/encoding_shard_0.txt`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T153400Z_sam_clip_shard_0/run.log`。 耗时 30440.02 秒；进程显存采样峰值 36016 MiB。
- `sam_clip_shard_1`：completed；命令：`python scripts/image_encoding.py --source_path /mnt/sda/ubuntu/lkx/papers/paper_in/data --save_dir /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/02_image_encoding/data/language_features --sam_ckpt_path /mnt/sda/ubuntu/lkx/papers/paper_in/models/sam/sam_vit_h_4b8939.pth --image-list /mnt/sda/ubuntu/lkx/papers/paper_in/configs/encoding_shard_1.txt`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T153400Z_sam_clip_shard_1/run.log`。 耗时 31197.20 秒；进程显存采样峰值 33984 MiB。
- `sam_clip_shard_2`：completed；命令：`python scripts/image_encoding.py --source_path /mnt/sda/ubuntu/lkx/papers/paper_in/data --save_dir /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/02_image_encoding/data/language_features --sam_ckpt_path /mnt/sda/ubuntu/lkx/papers/paper_in/models/sam/sam_vit_h_4b8939.pth --image-list /mnt/sda/ubuntu/lkx/papers/paper_in/configs/encoding_shard_2.txt`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T153400Z_sam_clip_shard_2/run.log`。 耗时 30513.62 秒；进程显存采样峰值 30798 MiB。
- `sam_clip_shard_3`：completed；命令：`python scripts/image_encoding.py --source_path /mnt/sda/ubuntu/lkx/papers/paper_in/data --save_dir /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/02_image_encoding/data/language_features --sam_ckpt_path /mnt/sda/ubuntu/lkx/papers/paper_in/models/sam/sam_vit_h_4b8939.pth --image-list /mnt/sda/ubuntu/lkx/papers/paper_in/configs/encoding_shard_3.txt`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T153400Z_sam_clip_shard_3/run.log`。 耗时 30398.01 秒；进程显存采样峰值 32294 MiB。
- `verify_encoding`：completed；命令：`python scripts/verify_encoding.py`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261125T001358Z_verify_encoding/run.log`。 耗时 49.18 秒；进程显存采样峰值 0 MiB。
- `verify_partial_50`：completed；命令：`python scripts/verify_encoding.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T162601Z_verify_partial_50/run.log`。 耗时 13.65 秒；进程显存采样峰值 0 MiB。
- `verify_partial_reference145`：completed；命令：`python scripts/verify_encoding.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T190630Z_verify_partial_reference145/run.log`。 耗时 32.32 秒；进程显存采样峰值 0 MiB。
- `verify_partial_reference193`：completed；命令：`python scripts/verify_encoding.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T203638Z_verify_partial_reference193/run.log`。 耗时 57.43 秒；进程显存采样峰值 0 MiB。
- `verify_partial_reference241`：completed；命令：`python scripts/verify_encoding.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T215056Z_verify_partial_reference241/run.log`。 耗时 67.21 秒；进程显存采样峰值 0 MiB。
- `verify_partial_reference289`：completed；命令：`python scripts/verify_encoding.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T225659Z_verify_partial_reference289/run.log`。 耗时 40.15 秒；进程显存采样峰值 0 MiB。
- `verify_partial_reference97`：completed；命令：`python scripts/verify_encoding.py --partial`；日志：`outputs/relags_baseline/02_image_encoding/runs/20261124T174434Z_verify_partial_reference97/run.log`。 耗时 21.32 秒；进程显存采样峰值 0 MiB。
实际观察：350 帧全新 SAM/CLIP 和 OpenSeg 完成并通过格式/有限数值检查；不代表分割和语义准确率已得到真值验证。


实际证据与限制：

当前实际文件对：SAM/CLIP 350/350；OpenSeg 350/350。最终完整性以 encoding_verification.json / openseg_verification.json 为准。

已诊断 350 帧：SAM 标签图中原本无像素的掩膜 5319 个；半分辨率映射额外丢失 3450 个。保存逐掩膜索引、丢失位置图和 OpenSeg 特征 PCA 显示图。PCA 仅用于显示，不进入算法。

TensorFlow 2.15.1 与本地 cuDNN 8.7 不匹配的失败已保留；2.14.1/CUDA 11.8 单帧验证通过。先在三张 GPU 编码，几何阶段结束后改为四份独立帧清单；已完成文件对复用。所有参数与逐帧计算保持一致，切换记录与中断日志完整保留。

人工查看 frame_000001 的四层 SAM：大层能覆盖地面/大型设备区域，小层将机架和设备表面切成许多碎块。此观察仅针对一个视角，不是 3D 实例分割结论。该帧半分辨率消失的 12 个掩膜在全分辨率标签图中仅各占 1–7 像素，不能等同于完整工业部件被漏检；额外保存其原始像素计数和位置圈注。

frame_000049：人工查看两个相邻前景箱状对象（具体设备类别未核实）。像素索引核验：默认层两点均为 224，大层两点均为 1123；中层分别为 996/1000；小层左点未覆盖（-1）、右点为 741。不能只凭近似颜色断定同一掩膜；抽查坐标与实际 ID 见 metrics/foreground_pair_mask_probe.json。这只证明单视角粗掩膜存在合并，不能提前推断多视角三维分组结果。OpenSeg PCA 显示两箱体颜色接近，但 PCA 颜色仅表示显示投影，不能当作分类分数或真值。


### 参考视角 frame_000097

已查看同一 RGB 的四层 SAM 叠加图。有效标签数依次为 320、503、288、107；小层未覆盖比例 23.97%。中央箱状组件呈现整体与局部细分差异，小层未覆盖包含地面等区域，不能直接解释为设备漏检率。具体数组统计见 `data/reference97_review.json`，后续与三维层次的同相机结果对照。


### 参考视角 frame_000145

已查看四层 SAM 叠加图。有效标签数为 331、586、311、147；small 层未覆盖比例 28.87%。前景平行细杆区域在 small 层有较多未覆盖位置，而其他层更接近整体区域。杆间空隙也在画面中，不能据此报告细杆漏检率。统计与限制见 `data/reference145_review.json`。另已查看第 97 帧 OpenSeg PCA 图，颜色仅显示特征变化，不当作类别预测或置信度。


### 参考视角 frame_000193

有效 SAM 标签数依次为 379、539、326、126；large 层未覆盖比例 47.15%，包含通道及前景细杆区域。small/medium 层仍可见多条平行结构的区分。该比例不是物体漏检率，需检查最终层次是否保留可见细节。原始统计见 `data/reference193_review.json`。


### 参考视角 frame_000241

已查看四层 SAM 叠加图。中央通道在 default/medium/large 层更接近整体区域，small 层多数通道像素未覆盖。两侧箱状设备及物体具有多尺度分割差异；索引颜色不是物体类别。保留作为后续重复物体实例与地面分离检查的同相机参照。详见 `data/reference241_review.json`。


### 参考视角 frame_000289

该视角以墙面、通道及堆叠箱状物体为主，四层有效标签数为 207、307、207、90。各尺度划分粒度不同；保留用于重复物体实例区分与上下空间关系检查。类别与实例正确性尚无真值，索引颜色不作语义类别解释。详见 `data/reference289_review.json`。


### 参考视角 frame_000345

已查看最后一个固定参考视角：厂房通道地面占画面较大面积，四层均覆盖大面积地面，黄色标线在部分层形成细长片段。保留为地面/标线与细长结构对照；类别准确性仍需独立标注。具体统计见 `data/reference345_review.json`。全部八个固定视角的 SAM 叠加图均已生成并查看。


### 记录文件重名修复

全量诊断首次成功后，运行器将同名统计 JSON 覆盖成任务元信息。已修复命名隔离并从保存的原始数组重放只读诊断；恢复出的 JSON 与首次统计的 SHA256 完全一致。原始编码结果未变，完整过程见 `logs/runner_metric_collision.json` 和两个 encoding_diagnostics 尝试目录。全量结果：原 SAM 图中已无像素的索引 5319 个，半分辨率另丢失 3450 个；后者原像素数中位数 2、最大 77。这不是部件召回率。


## Stage 03：最大权重裁剪

状态：**完成并核验**。

输入：训练完成的 2DGS、训练相机。

预期输出：每点贡献、保留/删除索引、裁剪前后 PLY 与图像。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/03_gaussian_pruning/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `compare_pruning`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/compare_pruning.py`；日志：`outputs/relags_baseline/03_gaussian_pruning/runs/20261124T152613Z_compare_pruning/run.log`。 耗时 6.79 秒；进程显存采样峰值 0 MiB。
- `mwp`：completed；命令：`python max_weight_pruning.py -s /mnt/sda/ubuntu/lkx/papers/paper_in/data -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/03_gaussian_pruning/data/model -r 1 --contribution_threshold 0.0005`；日志：`outputs/relags_baseline/03_gaussian_pruning/runs/20261124T152454Z_mwp/run.log`。 耗时 26.25 秒；进程显存采样峰值 12584 MiB。
- `render_pruned`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/render_views.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/03_gaussian_pruning/data/model --iteration 0 --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/03_gaussian_pruning/visualizations/pruned --all-test`；日志：`outputs/relags_baseline/03_gaussian_pruning/runs/20261124T152520Z_render_pruned/run.log`。 耗时 52.54 秒；进程显存采样峰值 2098 MiB。
实际观察：已保存最大贡献、保留/移除索引、两组 PLY 和 44 留出视角。细结构损失需结合裁剪前后统一相机比较。


实际证据与限制：

裁剪前 865,920，保留 816,661，移除 49,259（5.69%）。44 视角 PSNR 26.9838 → 26.9838 dB；SSIM 0.89311 → 0.89311。逐相机最大贡献、总贡献、索引与删除 PLY 均保留。

裁剪前后图与放大差值只能反映重建变化；细管/细杆是否被误删还需结合图像和被删高斯检查，不能由总体 PSNR 代替细结构真值。

人工查看 frame_000001 裁剪前后对比：主设备、机架、前景料箱及可见细杆没有肉眼明显变化。平均重建指标变化也很小。差值图基于 8-bit PNG，低于量化精度的差异不可见；这些证据不证明所有遮挡区域及所有微细结构都完整保留。完整被删高斯及逐点贡献可供后续检查。


## Stage 04：初始几何邻接与划分

状态：**完成并核验**。

输入：裁剪后 Gaussian。

预期输出：原始邻接图；原始邻接 Cut Pursuit 诊断（主流程使用重加权邻接）。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/04_superpoint_partition/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `export_id_projections`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_id_projections.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition/data/model/nag-l1.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition`；日志：`outputs/relags_baseline/04_superpoint_partition/runs/20261124T162824Z_export_id_projections/run.log`。 耗时 37.72 秒；进程显存采样峰值 1114 MiB。
- `export_initial_partition`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_hierarchy.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition/data/model/nag-l1.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition`；日志：`outputs/relags_baseline/04_superpoint_partition/runs/20261124T152739Z_export_initial_partition/run.log`。 耗时 88.51 秒；进程显存采样峰值 1046 MiB。
- `initial_partition_diagnostic`：completed；命令：`python sp_partition.py -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition/data/model --iteration 0 -a -k neighbor.pt --pcp_regularization 0.1 --pcp_spatial_weight 0.1`；日志：`outputs/relags_baseline/04_superpoint_partition/runs/20261124T152722Z_initial_partition_diagnostic/run.log`。 耗时 16.98 秒；进程显存采样峰值 1280 MiB。
- `neighbors`：completed；命令：`python sp_partition.py -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/04_superpoint_partition/data/model --iteration 0 -a`；日志：`outputs/relags_baseline/04_superpoint_partition/runs/20261124T152712Z_neighbors/run.log`。 耗时 10.48 秒；进程显存采样峰值 0 MiB。
实际观察：官方初始邻接图完成；额外保存同一官方 Cut Pursuit 在原始邻接上的诊断划分。此诊断划分不替代 Stage 05 的重加权划分。


实际证据与限制：

统计来源 `outputs/relags_baseline/04_superpoint_partition/metrics/hierarchy_statistics.json`：

- 层 0：21712 个组，中位成员数 22.0；小于 20 点的组 9173；非唯一父组 0。

分组数、组大小与父子一致性为诊断量；尚不能单独判定设备过分割/欠分割。对象级与部件级指官方层次候选，不把几何组直接当作已确认设备实例。

官方 environment.yml 固定 torch_geometric==2.3.0，但 vendored SPT 调用 Data.keys()，该版本返回 property/list，导致首个邻接步骤 TypeError。环境改为具有 callable keys() 接口的 2.5.3；小型 Data.to(cuda) 接口检查通过。没有修改 SPT 的图构造、距离、Cut Pursuit 或参数。原失败尝试完整保留。

实际邻接为 816661 × 10；225 个缺失邻居槽涉及 46 个高斯。源码 AdjacencyGraph 明确用 target >= 0 屏蔽这些槽，故保留官方 -1 哨兵而不擅自删点。初始划分 21712 组，统一视角呈现密集细碎几何块，这是后续语义合并之前的诊断结果，不能直接当作设备实例。


## Stage 05：层次分组

状态：**完成并核验**。

输入：邻接、全新 SAM、相机、高斯。

预期输出：正负边证据、重加权邻接、Cut Pursuit 分组、逐层投影和成员索引。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/05_hierarchical_grouping/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `audit_reference_pair`：completed；命令：`python scripts/audit_reference_pair.py`；日志：`outputs/relags_baseline/05_hierarchical_grouping/runs/20261125T003137Z_audit_reference_pair/run.log`。 耗时 0.38 秒；进程显存采样峰值 0 MiB。
- `export_hierarchy`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_hierarchy.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model/sai_nag_3.0.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping`；日志：`outputs/relags_baseline/05_hierarchical_grouping/runs/20261125T002410Z_export_hierarchy/run.log`。 耗时 109.66 秒；进程显存采样峰值 1046 MiB。
- `export_id_projections`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_id_projections.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model/sai_nag_3.0.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping`；日志：`outputs/relags_baseline/05_hierarchical_grouping/runs/20261125T002600Z_export_id_projections/run.log`。 耗时 27.70 秒；进程显存采样峰值 1146 MiB。
- `graph_reweight`：completed；命令：`python graph_weight.py -s /mnt/sda/ubuntu/lkx/papers/paper_in/data -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --iteration 0 -r 1 --config configs/lerf.yml --level 1`；日志：`outputs/relags_baseline/05_hierarchical_grouping/runs/20261125T001458Z_graph_reweight/run.log`。 耗时 45.37 秒；进程显存采样峰值 17534 MiB。
- `hierarchy_clip_rofa`：completed；命令：`python merge_proj.py -s /mnt/sda/ubuntu/lkx/papers/paper_in/data -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --iteration 0 -r 1 --thres_connect 0.9,0.7,0.7 --thres_merge 20 --tau 3 --vlm_type clip`；日志：`outputs/relags_baseline/05_hierarchical_grouping/runs/20261125T001606Z_hierarchy_clip_rofa/run.log`。 耗时 484.49 秒；进程显存采样峰值 32636 MiB。
- `reweighted_partition`：completed；命令：`python sp_partition.py -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --iteration 0 -a -k neighbor_new.pt --pcp_regularization 0.1 --pcp_spatial_weight 0.1`；日志：`outputs/relags_baseline/05_hierarchical_grouping/runs/20261125T001544Z_reweighted_partition/run.log`。 耗时 21.91 秒；进程显存采样峰值 1280 MiB。
实际观察：按官方顺序完成邻接重加权、Cut Pursuit 和三级合并；各层投影标签、邻接、成员与统一相机颜色渲染已保存。


实际证据与限制：

统计来源 `outputs/relags_baseline/05_hierarchical_grouping/metrics/hierarchy_statistics.json`：

- 层 0：21784 个组，中位成员数 22.0；小于 20 点的组 8989；非唯一父组 0。

- 层 1：9281 个组，中位成员数 33.0；小于 20 点的组 2626；非唯一父组 0。

- 层 2：2491 个组，中位成员数 62.0；小于 20 点的组 464；非唯一父组 0。

- 层 3：1189 个组，中位成员数 126.0；小于 20 点的组 0；非唯一父组 0。

分组数、组大小与父子一致性为诊断量；尚不能单独判定设备过分割/欠分割。对象级与部件级指官方层次候选，不把几何组直接当作已确认设备实例。



### 执行资源调度

正式层次分组使用 GPU 3；启动前等待本次 OpenSeg 编码进程完成并释放显存。只改变并发调度，不改变任一模块的输入、分辨率、参数或算法顺序依赖。


### 前景箱状区域的粗层合并候选

沿用 Stage 02 预先选定的第 49 帧采样点 A/B，投影对应的三维 L2 组分别为 156、182，L3 父组均为 18。5x5 邻域中 A 点有 17/25 像素属于 L3 组 18、8/25 属于 538；B 点为 25/25 属于组 18。说明采样点在中层区分、粗层合并，也存在投影边界歧义。这是需人工实例标注核查的粗层过合并候选，不报告实例准确率。原始数值见 `metrics/reference_pair_analysis.json`，同视角图见 `visualizations/reference049_pair_levels.jpg`。


## Stage 06：ROFA 语义聚合

状态：**完成并核验**。

输入：逐层分组、逐视角新特征。

预期输出：聚合前特征、视角 ID、异常值掩膜、聚合后特征。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/06_semantic_aggregation/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `hierarchy_openseg_rofa`：completed；命令：`python merge_proj.py -s /mnt/sda/ubuntu/lkx/papers/paper_in/data -m /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/model --iteration 0 -r 1 --thres_connect 0.9,0.7,0.7 --thres_merge 20 --tau 3 --vlm_type openseg`；日志：`outputs/relags_baseline/06_semantic_aggregation/runs/20261125T002743Z_hierarchy_openseg_rofa/run.log`。 耗时 528.14 秒；进程显存采样峰值 33622 MiB。
- `replay_clip`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/replay_rofa.py --observations /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/20261125T001606Z_hierarchy_clip_rofa --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/replay --vlm clip`；日志：`outputs/relags_baseline/06_semantic_aggregation/runs/20261125T003631Z_replay_clip/run.log`。 耗时 67.87 秒；进程显存采样峰值 2310 MiB。
- `replay_openseg`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/replay_rofa.py --observations /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/20261125T002743Z_hierarchy_openseg_rofa --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/replay --vlm openseg`；日志：`outputs/relags_baseline/06_semantic_aggregation/runs/20261125T003739Z_replay_openseg/run.log`。 耗时 71.02 秒；进程显存采样峰值 3568 MiB。
- `visualize_rofa`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/visualize_rofa.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/model`；日志：`outputs/relags_baseline/06_semantic_aggregation/runs/20261125T003850Z_visualize_rofa/run.log`。 耗时 120.85 秒；进程显存采样峰值 1046 MiB。
实际观察：CLIP 和 OpenSeg 均通过官方 ROFA；保留原始多视角观测及异常值决策，单独重放与原结果数值一致。


实际证据与限制：

clip 层 1：997938 条多视角观测，保留 988133，排除 9805；无观测组 0。

clip 层 2：259823 条多视角观测，保留 257359，排除 2464；无观测组 0。

clip 层 3：122344 条多视角观测，保留 121188，排除 1156；无观测组 0。

openseg 层 1：997171 条多视角观测，保留 981882，排除 15289；无观测组 0。

openseg 层 2：259704 条多视角观测，保留 255806，排除 3898；无观测组 0。

openseg 层 3：122330 条多视角观测，保留 120363，排除 1967；无观测组 0。

clip 官方 ROFA 独立重放最大绝对误差 0。

openseg 官方 ROFA 独立重放最大绝对误差 0。

保留率颜色图统一使用原参考相机；紫红色表示没有语义观测。离群值少不代表特征准确，工业重复设备和遮挡仍需检查。

## Stage 07：对象与部件导出

状态：**完成并核验**。

输入：官方多层 NAG。

预期输出：对象/部件成员、父子关系、着色 PLY、统一视角。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/07_object_part_modeling/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `compare_branches`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/compare_hierarchy_branches.py`；日志：`outputs/relags_baseline/07_object_part_modeling/runs/20261125T004626Z_compare_branches/run.log`。 耗时 4.54 秒；进程显存采样峰值 0 MiB。
- `export_clip`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_hierarchy.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model/sai_nag_3.0.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/07_object_part_modeling/clip`；日志：`outputs/relags_baseline/07_object_part_modeling/runs/20261125T004051Z_export_clip/run.log`。 耗时 131.61 秒；进程显存采样峰值 1046 MiB。
- `export_clip_ids`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_id_projections.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model/sai_nag_3.0.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/07_object_part_modeling/clip`；日志：`outputs/relags_baseline/07_object_part_modeling/runs/20261125T004303Z_export_clip_ids/run.log`。 耗时 34.78 秒；进程显存采样峰值 1146 MiB。
- `export_openseg`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_hierarchy.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/model/sai_nag_openseg.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/07_object_part_modeling/openseg`；日志：`outputs/relags_baseline/07_object_part_modeling/runs/20261125T004338Z_export_openseg/run.log`。 耗时 131.95 秒；进程显存采样峰值 1046 MiB。
- `export_openseg_ids`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/export_id_projections.py --model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/model --labels /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/06_semantic_aggregation/data/model/sai_nag_openseg.pt --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/07_object_part_modeling/openseg`；日志：`outputs/relags_baseline/07_object_part_modeling/runs/20261125T004550Z_export_openseg_ids/run.log`。 耗时 35.93 秒；进程显存采样峰值 1146 MiB。
实际观察：对象/部件层级为官方分组导出，不包含人为纠正。两种特征分支均保存成员索引、父子关系、特征统计、PLY 和相同参考相机图。


实际证据与限制：

统计来源 `outputs/relags_baseline/07_object_part_modeling/clip/metrics/hierarchy_statistics.json`：

- 层 0：21784 个组，中位成员数 22.0；小于 20 点的组 8989；非唯一父组 0。

- 层 1：9281 个组，中位成员数 33.0；小于 20 点的组 2626；非唯一父组 0。

- 层 2：2491 个组，中位成员数 62.0；小于 20 点的组 464；非唯一父组 0。

- 层 3：1189 个组，中位成员数 126.0；小于 20 点的组 0；非唯一父组 0。

统计来源 `outputs/relags_baseline/07_object_part_modeling/openseg/metrics/hierarchy_statistics.json`：

- 层 0：21784 个组，中位成员数 22.0；小于 20 点的组 8989；非唯一父组 0。

- 层 1：9281 个组，中位成员数 33.0；小于 20 点的组 2626；非唯一父组 0。

- 层 2：2491 个组，中位成员数 62.0；小于 20 点的组 464；非唯一父组 0。

- 层 3：1189 个组，中位成员数 126.0；小于 20 点的组 0；非唯一父组 0。

分组数、组大小与父子一致性为诊断量；尚不能单独判定设备过分割/欠分割。对象级与部件级指官方层次候选，不把几何组直接当作已确认设备实例。

CLIP/OpenSeg 分支层 0：逐点标签完全相同=True；忽略标签编号后的划分相同=True。不跨分支套用未经核验的组 ID。

CLIP/OpenSeg 分支层 1：逐点标签完全相同=True；忽略标签编号后的划分相同=True。不跨分支套用未经核验的组 ID。

CLIP/OpenSeg 分支层 2：逐点标签完全相同=True；忽略标签编号后的划分相同=True。不跨分支套用未经核验的组 ID。

CLIP/OpenSeg 分支层 3：逐点标签完全相同=True；忽略标签编号后的划分相同=True。不跨分支套用未经核验的组 ID。

## Stage 08：场景图与关系预测

状态：**完整场景图失败；根层诊断完成**。

输入：768D OpenSeg NAG、官方 GNN、Jina。

预期输出：节点几何、候选边、预测关系和分数、场景图。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/08_scene_graph/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `diagnose_obb`：completed；命令：`python scripts/diagnose_obb.py`；日志：`outputs/relags_baseline/08_scene_graph/runs/20261125T004930Z_diagnose_obb/run.log`。 耗时 17.07 秒；进程显存采样峰值 0 MiB。
- `export_root_diagnostic`：completed；命令：`python scripts/export_scene_graph.py --audit outputs/relags_baseline/08_scene_graph/data/20261125T004930Z_predict_root_diagnostic --output outputs/relags_baseline/08_scene_graph/diagnostics/root_only --levels 3`；日志：`outputs/relags_baseline/08_scene_graph/runs/20261125T005146Z_export_root_diagnostic/run.log`。 耗时 13.14 秒；进程显存采样峰值 0 MiB。
- `graph_model_probe`：completed；命令：`python -c 'import sys; sys.path.insert(0,"../scripts"); from predict_3d_scene_graph import REL_NAMES,load_model; from relags_relationships import load_relationship_embeddings; f,_=load_relationship_embeddings(REL_NAMES); m=load_model("../models/relags/graph_transformer_512_80.pth"); print("Jina",f.shape,"GNN checkpoint loaded")'`；日志：`outputs/relags_baseline/08_scene_graph/runs/20261124T151156Z_graph_model_probe/run.log`。 耗时 16.27 秒；进程显存采样峰值 0 MiB。
- `predict_graph`：failed；命令：`python predict_3d_scene_graph.py --root_pred /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/08_scene_graph/data/model --iteration 0 --vlm_type openseg --neighbor_thresh 5.0 --checkpoint /mnt/sda/ubuntu/lkx/papers/paper_in/models/relags/graph_transformer_512_80.pth`；日志：`outputs/relags_baseline/08_scene_graph/runs/20261125T004631Z_predict_graph/run.log`。 耗时 26.48 秒；进程显存采样峰值 1570 MiB。 输出校验异常：`FileNotFoundError(2, 'No such file or directory')`。
- `predict_root_diagnostic`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/predict_root_graph_diagnostic.py --root_pred /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/08_scene_graph/diagnostics/root_only/model --iteration 0 --vlm_type openseg --neighbor_thresh 5.0 --checkpoint /mnt/sda/ubuntu/lkx/papers/paper_in/models/relags/graph_transformer_512_80.pth`；日志：`outputs/relags_baseline/08_scene_graph/runs/20261125T004930Z_predict_root_diagnostic/run.log`。 耗时 37.94 秒；进程显存采样峰值 2340 MiB。
- `project_root_diagnostic`：completed；命令：`python scripts/project_scene_graph.py --audit outputs/relags_baseline/08_scene_graph/data/20261125T004930Z_predict_root_diagnostic --gaussians outputs/relags_baseline/03_gaussian_pruning/data/model/point_cloud/iteration_0/point_cloud.ply --output outputs/relags_baseline/08_scene_graph/diagnostics/root_only --levels 3`；日志：`outputs/relags_baseline/08_scene_graph/runs/20261125T005159Z_project_root_diagnostic/run.log`。 耗时 5.98 秒；进程显存采样峰值 0 MiB。
实际观察：官方完整 L2/L3 场景图在 OBB 构建失败。逐组诊断找到 5 个退化 L2 组，均保留原始点与索引；L3 独立诊断完成 1189 节点、359928 边，不替代完整图。


实际证据与限制：

官方 OBB 逐组诊断：层 2 共 2491 个组，成功 2486，失败 5。失败点云、原始高斯索引与异常见 `diagnostics/obb/`。

官方 OBB 逐组诊断：层 3 共 1189 个组，成功 1189，失败 0。失败点云、原始高斯索引与异常见 `diagnostics/obb/`。

独立根层诊断（不代表完整图成功）：1189 节点，359928 条预测有向边，保留全部分数、JSON、PLY 和八相机投影。位置：`diagnostics/root_only/`。

只完成权重加载探针时，不算场景图已执行。官方网络在 3DSSG 训练；保留距离阈值 5.0、默认 z 轴重力及原 COLMAP 单位。工业场景缺少公制尺度/重力标定，方向与距离关系的可信度受限，暂不旋转/缩放来改善结果。

历史 LangSplat 地面估计法向为 [-0.04795057566135688, -0.9585350486111748, -0.280911557038363]，与默认 z 重力轴的无向夹角约 73.69 度。该历史估计仅作风险提示，未用于旋转新基线，不当作独立标定或真值。这意味着上下关系应重点核查。

官方 predictor 保存的 jina_edges_predicted.pt 是 top-1 关系类别的 Jina 原型；连续 GNN 边向量已另存。关系查询按官方文件使用这些原型，不偷偷替换为连续预测。


## 本次最终状态

完整图失败于 L2 组 1822：原 1 点，官方离群清理后 0 点。进一步核验共 5 个失败叶组，完整原始点云/索引/错误均保留。根层独立预测及其相机投影保存在 diagnostics/root_only，未删除失败叶组来拼成完整图。后续改变退化节点处理规则属于新的方法设置，应另建基线。


## Stage 09：开放词汇与关系查询

状态：**开放词汇完成；完整关系查询受阻**。

输入：NAG、文本、关系嵌入。

预期输出：官方查询输出、候选分数、选择索引、三维子集与二维图。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。

中间结果目录：`outputs/relags_baseline/09_relational_query/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。

- `build_query_review`：completed；命令：`python scripts/build_query_review.py`；日志：`outputs/relags_baseline/09_relational_query/runs/20261125T005235Z_build_query_review/run.log`。 耗时 1.07 秒；进程显存采样峰值 0 MiB。
- `open_vocabulary_queries`：completed；命令：`python /mnt/sda/ubuntu/lkx/papers/paper_in/scripts/query_baseline.py --clip-model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model --graph-model /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/08_scene_graph/data/model --output /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/09_relational_query --mode open`；日志：`outputs/relags_baseline/09_relational_query/runs/20261125T004930Z_open_vocabulary_queries/run.log`。 耗时 65.86 秒；进程显存采样峰值 1446 MiB。
实际观察：12 个官方开放词汇查询已执行并保存全量分数、候选、高斯子集和八参考相机图；6 个完整关系查询因 Stage 08 缺少完整 L2/L3 图未执行。


实际证据与限制：

实际执行 12 个查询；空结果 0；完整关系查询未执行，其阈值回退统计不适用。保存全量相似度、候选、索引、选中高斯 PLY 和统一相机叠加图。

保持官方 root/leaf 筛选、相似度间隙切分及关系查询回退规则。空结果不手动补选；低置信回退不解释为确定定位。没有查询真值时不报告定位准确率。

六个关系查询未执行：完整 L2/L3 场景图在 OBB 步骤失败，所需关系文件不存在。没有用独立根层诊断冒充完整图。依赖、计划命令及原因见 `metrics/relational_query_blocked.json`。

实际细粒度问题：floor 与 yellow floor marking 的选中高斯集合 Jaccard=0.97087；第 345 帧两个投影完全一致。该数值是两次预测的重合度，不是真值 IoU；黄色标线在此例未从大块地面中分离。



## 本次最终状态

开放词汇 12 项均已执行，非空不等于正确。黄色标线查询与地面查询在第 345 帧投影完全一致，未实现标线级分离。6 个关系查询因完整关系图失败而未执行，计划命令与缺失依赖保存在 metrics/relational_query_blocked.json。root-only 诊断没有用于冒充完整关系查询。


## 工业场景实际检查与后续方向

**本次为原始方法的工业适配 Baseline 0，不是全流程成功的结果。** Stage 00–07 完成，Stage 08 完整 L2/L3 图因官方 OBB 的输入条件失败；Stage 09 完成 12 个开放词汇查询，6 个关系查询因缺少完整关系图未执行。独立 L3 关系图仅作为诊断保存。

| 检查项 | 实际证据与结论 | 限制与后续值得检查的方向 |
|---|---|---|
| 几何复用 | 原 3DGS 为三尺度椭球，官方 ReLaGS 需二维面元，因此复用图像/COLMAP 训练 2DGS。最终 865,920 高斯，44 留出视角 PSNR 26.98384 dB、SSIM 0.89311。 | 保留原坐标、306/44 划分与官方训练默认值；没有公制尺度、重力或语义真值。 |
| MWP 与细结构 | 保留 816,661，移除 49,259（5.6886%）；裁剪前后 PSNR 变化约 -0.00000256 dB。统一视角中平行细杆仍可见。 | 总体重建指标不能证明所有细杆、遮挡部件均未误删；后续需专门的细结构标注与移除点云检查。 |
| 初始 Superpoint | 原邻接诊断 21,712 组；正式重加权后 21,784 组。后续层为 9,281 / 2,491 / 1,189 组。所有父子映射唯一。 | 组数不是实例数；L2 包含极小组，已实际影响后续 OBB。 |
| 分割与尺寸 | 新跑 350 帧。原 SAM 标签图已有 5,319 个无像素索引，OpenSeg 半分辨率额外丢失 3,450 个索引；后者原始像素数中位数 2、最大 77。 | 这是掩膜索引损失，不是部件召回率。八个固定视角的分割差异、原始像素计数与位置图全部保留。 |
| 对象、部件及重复实例 | 第 49 帧两个预先选定的箱状区域采样点，在 L2 为 156/182，在 L3 同为 18。对应对照图与 5×5 邻域索引已保存。 | 属于粗层合并候选；A 点邻域存在边界歧义。需要设备实例/部件标注才能量化过分割、欠分割。 |
| 多视角语义 | CLIP 与 OpenSeg 的六次 ROFA 重放最大绝对误差均为 0。每层均无空观测组，CLIP 排除约 0.94–0.98% 观测，OpenSeg 约 1.50–1.61%。两分支分组标签逐点一致。 | 高保留率不代表工业语义准确；重复外观、反光与视角变化仍需对照原始观测。PCA 图仅为显示。 |
| 完整场景图 | L2 的 1822、1836、1927、1987 各仅 1 个点，离群清理后为 0；2307 为 3 个点，无法构造 Qhull 初始四点单纯形。官方完整预测在首个失败处退出。 | 保留原始分组与失败；后续若增加极小节点处理或包围盒退化规则，应另立改进基线，不能追写为本次原法成功。 |
| 根层关系诊断 | 独立 L3：1,189 节点、359,928 条有向预测边。保存连续 GNN 输出、27 类分数、top3、JSON、PLY 与八个参考相机投影。 | 根层结果不能替代缺失的 L2/L3 完整图。预测受 3DSSG 训练域、原 COLMAP 单位、默认 z 轴和距离阈值 5.0 的影响；无关系 GT，未报告准确率。 |
| 开放词汇查询 | 12 个查询均得到非空结果。`blue plastic bin`、`gray plastic container` 在查看的视角可命中相应外观的箱状区域；`floor` 命中大面积地面。 | 非空不是正确。`roller` 命中后方小区域，没有覆盖前景平行滚筒；`pipe` 仅选中 156 个高斯，需人工核查对象身份。 |
| 标线级定位 | `floor` 与 `yellow floor marking` 的高斯集合 Jaccard 为 0.970867；第 345 帧两个浮点投影完全一致。该例的黄色标线未与地面分离。 | 这是两次预测的重合度，非真值 IoU。可能与 L2/L3 分组、语义特征及官方仅比较 root/leaf 的查询逻辑有关；未做消融，不能归因单一模块。 |
| 完整关系查询 | 预定 6 个关系查询未执行，缺少完整的 `jina_edges_predicted.pt`。 | 保留待执行命令、依赖和阻塞原因；未使用根层诊断填充缺失的关系图。 |

主要证据位置：

- `outputs/relags_baseline/03_gaussian_pruning/metrics/pruning_comparison.json`
- `outputs/relags_baseline/05_hierarchical_grouping/visualizations/reference049_pair_levels.jpg`
- `outputs/relags_baseline/06_semantic_aggregation/data/replay/`
- `outputs/relags_baseline/07_object_part_modeling/metrics/branch_comparison.json`
- `outputs/relags_baseline/08_scene_graph/metrics/obb_failure_audit.json`
- `outputs/relags_baseline/08_scene_graph/diagnostics/obb/`
- `outputs/relags_baseline/08_scene_graph/diagnostics/root_only/`
- `outputs/relags_baseline/09_relational_query/visualizations/query_overview.jpg`
- `outputs/relags_baseline/09_relational_query/metrics/floor_marking_confusion.json`

当前只记录问题。后续应先补充独立尺度/重力依据与少量设备、部件、查询真值，再围绕小节点 OBB、粗层合并、细结构语义和查询层级分别做可追踪实验；本次未实施这些算法修改。


## 上游证据

- 论文及附录：`references/ReLaGS_2603.17605.pdf`（20 页）。
- 官方代码固定提交：`52cc0c98b0ccf9afebea31901bf79246650286b3`。
- 作者确认 OpenSeg 数据适配与域差异：https://github.com/dfki-av/ReLaGS/issues/3#issuecomment-4507638043 。
- 作者确认 CLIP/OpenSeg 不可替换：https://github.com/dfki-av/ReLaGS/issues/4#issuecomment-4903379261 。
- 2DGS README 的 plumerai 链接失效；使用作者官方仓库 hbb1/2d-gaussian-splatting，失败与后续下载日志均保留。
