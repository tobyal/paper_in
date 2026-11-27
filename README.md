# ReLaGS 工业车间复现：Baseline 0 + OBB 修复续跑 R1

基于真实工业车间图像复现 [ReLaGS](https://github.com/dfki-av/ReLaGS)（[论文](https://arxiv.org/abs/2603.17605) / [项目主页](https://dfki-av.github.io/ReLaGS/)）。本仓库保存核心控制与适配代码、固定上游版本、补丁、实验报告、关键检查记录，以及各阶段真实中间结果图。

## Paper experiments: controlled ablations and publication figures

The [paper experiment package](experiments/paper_final_experiments/README.md) completes E01—E06 with six qualitative PNG/SVG paper figures, three statistical PNG/SVG/PDF figures (F10-F12), four principal quantitative tables, 350 ablation/supplement masks, full 25-query comparison galleries and real affinity/relationship traces.

| Configuration | mIoU | Precision | Recall |
|---|---:|---:|---:|
| Box-based (same availability) | 62.95% | 70.33% | 83.72% |
| Ours w/o Relation | 46.52% | 59.18% | 70.54% |
| Ours | 63.70% | 84.33% | 70.21% |

On the same 23-query / 44-view **SAM-assisted reference**, relations add 17.18 percentage points mIoU. Fine extraction improves Precision but sacrifices Recall, with only 0.75 points mIoU gain over gated coarse boxes. The separate all-33 coarse-box supplement reaches 68.07% mIoU; instance availability remains a material limitation. These are not independent human-GT results.

[F04—F12 gallery](experiments/paper_final_experiments/docs/GALLERY.md) · [Full experiment report](experiments/paper_final_experiments/EXPERIMENT_REPORT.md) · [Tables and figure index](experiments/paper_final_experiments/FIGURE_INDEX.md). Existing v2 and benchmark results are preserved; ReLaGS indexing and all 50 projections were checked without changing predictions. Large arrays and models stay on the server.

## External comparison: SAM-assisted Pseudo-GT evaluation

The [relational retrieval benchmark](experiments/relational_retrieval_benchmark/README.md) runs LangSplat, THGS, ReLaGS and frozen v2 Ours on 25 shared queries. Quantitative evaluation uses the same 23 queries / 44 reliable views for every method; 6 views are excluded with documented reasons. References are SAM-assisted Pseudo-GT reviewed by Codex, **not independent human ground truth**.

| Method | Projection mIoU | Mean Precision | Mean Recall |
|---|---:|---:|---:|
| LangSplat | 20.87% | 29.28% | 36.32% |
| THGS | 8.68% | 14.40% | 10.16% |
| ReLaGS | 0.35% | 11.00% | 0.35% |
| Ours | 63.70% | 84.33% | 70.21% |

[Quantitative report](experiments/relational_retrieval_benchmark/QUANTITATIVE_EVALUATION_REPORT.md) · [All queries with reference masks and IoU](experiments/relational_retrieval_benchmark/docs/GALLERY.md) · [Detailed metrics](experiments/relational_retrieval_benchmark/evaluation/metrics/summary.csv). Shared M0 priors, SAM errors and exclusions limit interpretation. Q019 retains the Ours failure alongside useful external-method results. Weights, original RGB, candidate arrays and full point clouds remain on the server.

## SAGA + ReLaGS：工业对象实例与关系查询

新增独立实验 [saga_relags_v1](experiments/saga_relags_v1/README.md)：官方SAGA完成10,000步共享亲和训练；10个对象尝试中9个可用于设备级查询展示、1个料架失败；8类共享语义；33节点几何图；5项类别查询和5项关系查询。视觉关系提升已运行，但没有得到可靠新增语义边，不能视为该部分验证成功。

[完整报告](experiments/saga_relags_v1/EXPERIMENT_REPORT.md) · [关键结果图集](experiments/saga_relags_v1/docs/GALLERY.md) · [版本、补丁及归档范围](experiments/saga_relags_v1/PUBLICATION.md)。原工程及既有结果未改动，模型权重和完整数据保留在服务器。

## 工业空间先验与原生 3DGS：M1—M5

新增独立的 [industrial_world_model](industrial_world_model/README.md) 流程，读取 M0 空间先验、原生 3DGS、原始 RGB/COLMAP，执行多视角 SAM、高斯关联、实例提取、双分支 CLIP、几何场景图和语义/关系查询。原始 Baseline 0/R1 与 M0 保留。

首次实际运行：33 个对象中 19 个获得有效实例，14 个保留不可用原因；634 条几何关系；15 项查询含空结果和多结果。内部重投影 IoU 均值约 0.267，提取仍偏保守，外观查询存在宽泛匹配，不能解释为分割或查询准确率。全部阶段证据和独立世界模型保存在服务器 `outputs/industrial_world_model/baseline_20261126_r29/`，完整运行命令、独立阶段入口和读取接口见 [运行说明](industrial_world_model/README.md)。

本次展示的真实中间结果已收录为 [M1—M5 阶段图集](docs/industrial_world_model/GALLERY.md)，含候选高斯、视角选择、SAM 分割、归属得分、实例提取前后、重投影、语义特征、场景图和关系查询。图像原样复制，来源与 SHA-256 记录在 [图像清单](docs/industrial_world_model/manifest.json)。原始数据、权重和大体积中间数组仍保留在服务器。

## 实际完成状态

- **Baseline 0**：Stage 00–07 完成；完整 Stage 08 因 5 个极小 L2 分组的 OBB 构建失败；12 项开放词汇查询完成。原失败记录保留。
- **R1**：重放官方代码排除点/标签映射错误，仅补充极小点集的退化 OBB 边界处理，完成完整 L2/L3 场景图与 6 项关系查询。分组、ROFA、GNN 权重/结构及查询规则未改；3,675 个正常 OBB 逐值不变。
- L2：2,491 节点、1,645,360 条有向边；L3：1,189 节点、359,928 条有向边。
- 六项关系查询中有两项使用官方低阈值回退，三个查询选中相同的 52 高斯局部。**运行完成不等于语义或关系准确。**

## 阅读入口

| 内容 | 位置 |
|---|---|
| 全流程、失败记录与 R1 更新 | [EXPERIMENT_REPORT.md](EXPERIMENT_REPORT.md) |
| OBB 问题来源、修复范围、六项关系查询 | [OBB_REPAIR_REPORT.md](OBB_REPAIR_REPORT.md) |
| 工业问题分析 | [INDUSTRIAL_REVIEW.md](INDUSTRIAL_REVIEW.md) |
| 数据迁移与逐文件来源 | [DATA_MIGRATION.md](DATA_MIGRATION.md) / [TSV](DATA_MIGRATION.tsv) |
| 完整阶段图集 | [docs/GALLERY.md](docs/GALLERY.md) |
| 上游版本与适配补丁 | [UPSTREAM.lock.json](UPSTREAM.lock.json) / [patches](patches) |
| 环境快照、关键数值证据 | [environment](environment) / [evidence](evidence) |

## 核心代码

- `scripts/pipeline.py`、`run_stage.py`：分阶段执行、输入/输出指纹、命令与资源记录；`advance_pipeline.py`：有限依赖调度。
- `encode_openseg.py`、`parallel_encoding.py`：新图像特征提取与逐帧恢复。
- `relags_audit.py`、`patch_instrumentation.py`、`replay_rofa.py`：中间张量保存与 ROFA 重放。
- `export_hierarchy.py`、`export_id_projections.py`、`export_scene_graph.py`、`query_baseline.py`：层级/场景图导出、查询及统一相机展示。
- `investigate_obb_r1.py`、`obb_boundary_r1.py`、`predict_graph_obb_r1.py`：OBB 溯源、显式边界修复与原预测器续跑。
- `verify_edge_batch_r1.py`、`analyze_obb_r1.py`：官方分批推理一致性与原基线完整性核验。
- `build_stage_gallery.py`：仅从已保存结果生成阶段图，不重新执行算法。

## 获取固定上游代码

```bash
git clone --recurse-submodules https://github.com/tobyal/paper_in.git
cd paper_in
python3 scripts/bootstrap_sources.py
```

`ReLaGS/` 与 `external/2d-gaussian-splatting/` 是固定提交的 Git 子模块；bootstrap 校验提交并应用本次运行的源代码补丁，不重置已有修改。编译产物需在目标 Linux/CUDA 环境重建。

本仓库不包含原视频、350 帧原始图像、COLMAP 二进制、训练检查点、完整特征张量、模型权重或 Python/CUDA 环境。需要按迁移记录准备 `data/`、`models/` 和 `envs/` 后运行。完整大体积结果保留在研究服务器。

成功环境为 Python 3.10.13、PyTorch 2.2.0+cu118、CUDA 11.8、NumPy 1.26.4、torch_geometric 2.5.3；OpenSeg 单独使用 TensorFlow 2.14.1。详见 [环境说明](environment/README.md)。历史安装脚本和 pip 快照保留了实际失败/恢复过程，不应直接当作跨机器的一键安装方案；`common.sh` 的代理和 CUDA 路径需匹配目标机器。

准备好输入后可用 `python scripts/pipeline.py --stage 0` 等执行单阶段。原法完整 Stage 08 会重现 OBB 边界失败；R1 独立入口、实际命令与恢复方式见修复报告。原报告中绝对服务器路径是当次运行溯源信息；仓库内可查看的关键证据复制于 `evidence/`。

## 各阶段中间结果

以下图像来自已保存的实际实验，仅调整排版。分组颜色不是语义类别；场景图只显示少量边以便查看，完整关系尚无人工真值。

### 00 数据与相机

![00 数据与相机](docs/figures/stage_00.jpg)

### 01 二维高斯重建

![01 二维高斯重建](docs/figures/stage_01.jpg)

### 02 SAM 分割与语言特征

![02 SAM 分割与语言特征](docs/figures/stage_02.jpg)

### 03 最大权重高斯裁剪

![03 最大权重高斯裁剪](docs/figures/stage_03.jpg)

### 04 初始 Superpoint 诊断

![04 初始 Superpoint 诊断](docs/figures/stage_04.jpg)

### 05 层次化高斯分组

![05 层次化高斯分组](docs/figures/stage_05.jpg)

### 06 ROFA 多视角聚合

![06 ROFA 多视角聚合](docs/figures/stage_06.jpg)

### 07 对象/部件候选层级

![07 对象/部件候选层级](docs/figures/stage_07.jpg)

### 08 完整场景图（R1）

![08 完整场景图（R1）](docs/figures/stage_08.jpg)

### 09 开放词汇查询

![09 开放词汇查询](docs/figures/stage_09_open.jpg)

### 09 六项关系查询（R1）

![09 六项关系查询（R1）](docs/figures/stage_09_relations.jpg)

## 来源与许可

上游代码、适配补丁及权重分别遵循其原许可，详见 [THIRD_PARTY.md](THIRD_PARTY.md)。工业结果没有被宣称为人工标注真值。

## M0 v2：三维工业先验工作台

两个工作页：工业场景确定、工业对象确定。自由三维与三个正交视图共用空间框，直接点击设备创建粗略范围，再填写基础双语名称和描述；单张训练 SAM 参考可选。旧七步、区域、多视角掩膜、关系和评价标注不再是保存或导出的要求。

- [启动与操作](m0/README.md) · [真实验收及限制](m0/docs/IMPLEMENTATION_REPORT.md)
- [数据格式](m0/docs/DATA_FORMAT.md) · [M1–M5 接口边界](m0/docs/M1_M5_INTERFACE.md)
- [实际数据状态](m0/docs/DATA_STATUS_AT_DELIVERY.md)：场景、一个实际料架候选和单张参考均为待人工复核的草稿，正式数据未冻结。

M0 不生成最终对象高斯实例、融合语义或场景图。Baseline 0/R1 和原始几何保持原状；V1 代码及数据在服务器完整备份，Git 旧版为 6d50092。原图、模型、标注、备份与工作台截图不进入本次源码提交。


## SAGA + ReLaGS 工业世界模型 v2

覆盖全部33台工业设备：20台可用、10台局部可用、3台待改进；复用冻结SAGA特征，保留33节点/2020几何关系，并修复设备查询与精细实例可用性的耦合。64项查询功能检查通过，质量审核不作为人工真值准确率。

- [代码与运行说明](experiments/saga_relags_v2/README.md)
- [完整实验报告及33台汇总表](experiments/saga_relags_v2/EXPERIMENT_REPORT.md)
- [修改记录](experiments/saga_relags_v2/MODIFICATION_REPORT.md)
- [全部设备、关系图与查询结果](experiments/saga_relags_v2/docs/GALLERY.md)
- [归档范围及数据依赖](experiments/saga_relags_v2/PUBLICATION.md)

模型权重、PLY、原始数据与中间数组仅保留在服务器。
