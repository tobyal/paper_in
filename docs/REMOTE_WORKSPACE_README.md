# ReLaGS 工业车间原始基线 Baseline 0

实际计算目录：`/mnt/sda/ubuntu/lkx/papers/paper_in`（`ubuntuA6000`，用户 `kxliu`）。本机 `E:\codex_projects\paper_in` 保存控制脚本和便于查看的报告副本；大数据与运行状态以远程目录为准。

原工程 `/mnt/sda/ubuntu/lkx/papers/paper_eli` 只读，迁移通过复制完成。参见 `DATA_MIGRATION.md`、逐文件 `DATA_MIGRATION.tsv`、`EXPERIMENT_REPORT.md`、`EXECUTION_PLAN.md`。报告状态来自真实执行日志，不把准备好的脚本视为已完成实验。

## 原始 Baseline 0 实际结果（历史状态）

**Stage 00–07 完成；完整 Stage 08 失败；Stage 09 仅完成 12 个开放词汇查询，6 个关系查询未执行。** 失败原因是官方 OBB 对 5 个极小 L2 分组无法构造包围盒。原始失败和完整输入均保留；`08_scene_graph/diagnostics/root_only/` 的 1189 节点、359928 边是独立根层诊断，不代表完整图成功。阶段作业已全部结束。

查看顺序：`EXPERIMENT_REPORT.md`（状态、实际命令与结果）→ `INDUSTRIAL_REVIEW.md`（工业问题）→ `DATA_MIGRATION.md` / `.tsv`（数据溯源）。机器可读状态为 `BASELINE_STATUS.json`，最终审计为 `outputs/relags_baseline/00_data_check/metrics/final_integrity.json`。

主要可视化：Stage 01 的 `visualizations/reconstruction/`，Stage 05 的层次着色图与 `reference049_pair_levels.jpg`，Stage 07 的分支 PLY，Stage 08 的 `diagnostics/root_only/visualizations/`，Stage 09 的 `visualizations/query_overview.jpg`。每个阶段的 README 给出完整数据、指标和运行记录位置。根目录下的路径均相对于本远程项目。

## R1 续跑已完成

完整 L2/L3 图和 6 项关系查询已完成；详见 `OBB_REPAIR_REPORT.md`、`REPAIR_STATUS.json`。独立结果位于 `outputs/relags_obb_repair_r1/`。原始 `outputs/relags_baseline/` 和 `BASELINE_STATUS.json` 保留失败事实。原根目录文档快照在新目录的 `baseline0_snapshot/`。

## 执行

登录后先进入项目并加载独立环境：

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in
source scripts/common.sh
```

单阶段命令为 `python scripts/pipeline.py --stage 0`，将最后的数字改为所需阶段。可传多个数字，例如 `--stage 3 4`。默认使用 GPU 3。入口对应关系：

| 阶段 | 实际模块及依赖 |
|---|---|
| 00 | 已迁移数据审计；不会重新复制原工程 |
| 01 | 官方 2DGS 30000 步训练、检查点及 44 留出相机渲染 |
| 02 | 官方 SAM/CLIP 编码与完整性检查；OpenSeg 命令见下文 |
| 03 | MWP、被删/保留高斯、固定视角比较 |
| 04 | 原始 KNN、原始边权 Cut Pursuit 诊断及导出 |
| 05 | 官方边权重算、主流程 Cut Pursuit、分层合并与 CLIP ROFA |
| 06 | 同一官方流程的 OpenSeg 分支，ROFA 独立重放和诊断 |
| 07 | 两种特征分支对象/部件层次的只读导出 |
| 08 | 官方 GNN 场景图预测及 JSON/PLY 导出 |
| 09 | 官方开放词汇和关系查询、候选分数、选中高斯及图像 |

二维编码也可按 `configs/encoding_shard_{0,1,2,3}.txt` 在四张 GPU 上运行：

```bash
python scripts/parallel_encoding.py
```

每张图像仍使用原官方参数和计算。完整的 mask/feature 对自动复用，不能同时再启动另一个编码作业。OpenSeg 使用独立 TensorFlow 环境及同项目 Torch 库，保留官方逐像素特征与池化前数据：

```bash
export LD_LIBRARY_PATH=$(find "$ROOT/envs/relags/lib/python3.10/site-packages/nvidia" -type d -name lib | paste -sd:):/usr/local/cuda-11.8/lib64
python scripts/run_stage.py --stage 02_image_encoding --job openseg_all --gpu 3 --cwd . \
  --input scripts/encode_openseg.py \
  --expect outputs/relags_baseline/02_image_encoding/metrics/openseg_verification.json \
  --expect outputs/relags_baseline/02_image_encoding/data/language_features_openseg/frame_000350_f_openseg.npy \
  -- envs/openseg/bin/python scripts/encode_openseg.py --follow
```

`--follow` 仅等待当前新生成的 SAM 文件，不调用原工程的语义结果。全部完成后运行 `python scripts/encoding_diagnostics.py`。只检查当前已生成结果可用 `python scripts/verify_encoding.py --partial` 和 `python scripts/encoding_diagnostics.py --partial`，其输出明确标记为 partial。

## 恢复和产物

`scripts/run_stage.py` 为每个实际命令创建不可变的 `runs/<UTC时间_任务名>/`，包含命令、参数、输入指纹、日志、资源采样及返回码。标准输出只在阶段根 `run.log` 追加。成功输出与声明的输入/参数指纹匹配时复用。共享导入代码不保证自动发现；修改这类代码后应使用 `--force`，并为改进实验使用独立输出目录。旧运行的配置、日志和输入快照保留，常规阶段产物路径可能被新的运行更新。训练恢复使用官方 `--start_checkpoint`，不修改原训练公式。

`scripts/advance_pipeline.py` 是本次有限任务的依赖调度入口：等待训练，执行 03/04，等待新二维特征，执行 05–09；失败即保留日志并停在失败依赖处。不要在它仍运行时重复启动。查看 `logs/pipeline_progress.json` 和 `logs/advance_pipeline.log`。

阶段 05/06 的分组与 ROFA 按官方源码交替进行，不能将文档中的两个编号误认为完全独立的官方命令。已提供 `scripts/replay_rofa.py`，可用已保存的逐视角观测独立重放原 ROFA 函数。

固定视角见 `configs/reference_views.json`。普通彩色点云 PLY 可用 CloudCompare/MeshLab/Open3D 查看；Gaussian PLY 需兼容二维高斯的渲染器。预测的场景图与对象层次均保留 JSON/张量数据，不仅保存截图。

## 基线边界

- 旧 3DGS 三轴椭球不等价于 2DGS 二轴面元，故重用图像/COLMAP、重新训练 2DGS。
- 原划分 306/44，原 COLMAP 坐标；缺少公制尺度、重力及语义/关系真值。不可据此虚构准确率。
- 全新 SAM、CLIP、OpenSeg、MWP、图分组与 GNN；旧语义分割、定位、编辑及 LangSplat 地面仅作历史参考。
- 核心公式和阈值按官方 LERF launcher；接口、打包、日志与可视化兼容补丁保存在 `logs/patches/`。依赖失败尝试均保留。
- 下载代理为本机代理经 SSH 转发到远程 `127.0.0.1:17891`；模型缓存和环境都在本项目，不依赖原工程运行。

## 从本次结果继续

原始失败无需重复编码即可复查：完整 Stage 08 命令和失败日志见该阶段 README；原始失败分组位于 `diagnostics/obb/`。在另立改进实验并解决极小分组问题后，可从已保存的 Stage 07 继续运行受影响的 08–09。原法不变时再次执行会遇到相同 OBB 输入限制。

`scripts/query_baseline.py --mode open` 可以独立运行开放词汇分支；`--mode relational` 要求完整 L2/L3 关系文件。六个未执行查询、依赖和原定命令保存在 `09_relational_query/metrics/relational_query_blocked.json`，该相对路径位于 `outputs/relags_baseline/` 下。
