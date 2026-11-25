# Baseline 0 数据迁移记录

最终保留 **798 个物理复制文件，共 5,932,662,465 字节（5.525 GiB）**。该数字仅指从旧工程迁移的文件，不包含本次生成的中间结果、独立环境及新下载权重。

源工程：`/mnt/sda/ubuntu/lkx/papers/paper_eli`。目标工程：`/mnt/sda/ubuntu/lkx/papers/paper_in`。下表路径分别相对于这两个根目录；逐文件绝对路径、解析后的源路径、目标路径、用途、大小、SHA256 及是否仅作参考，见 [DATA_MIGRATION.tsv](DATA_MIGRATION.tsv) 和 `outputs/relags_baseline/00_data_check/data/migration_manifest.json`。

## 最终迁移内容

| 内容与用途 | 文件数 | 字节数 | 源相对路径 | 目标相对路径 |
|---|---:|---:|---|---|
| 原始采集视频 | 1 | 98,033,689 | `data/raw/20261016-142321.mp4` | `data/raw/20261016-142321.mp4` |
| 去畸变前的提取图像及完成标记 | 351 | 146,263,457 | `data/industrial/input` | `data/images_extracted` |
| 去畸变 RGB：新流程直接输入 | 350 | 375,758,596 | `data/industrial/images` | `data/images` |
| 去畸变 COLMAP 相机、位姿与点云 | 4 | 100,428,398 | `data/industrial/sparse/0` | `data/colmap/sparse/0` |
| 原始 SfM 重建：溯源 | 8 | 95,461,361 | `data/industrial/distorted/sparse` | `data/colmap/distorted_sparse` |
| 原始未编辑 3DGS PLY：兼容性和视觉参考 | 1 | 453,538,228 | `outputs/reconstruction/point_cloud/iteration_30000/point_cloud.ply` | `data/gaussian_scene/original_3dgs/point_cloud/iteration_30000/point_cloud.ply` |
| 原始最终检查点及模型元数据：归档 | 4 | 1,320,559,999 | `outputs/reconstruction` | `data/gaussian_scene/original_3dgs` |
| 采集、相机、划分及重建记录 | 14 | 118,471 | `records` | `data/scene_information` |
| 旧研究报告及场景描述：参考 | 9 | 86,211 | `` | `previous_work/paper` |
| 发现的旧论文图表和源文件：参考 | 24 | 171,716,044 | `` | `previous_work/paper/discovered` |
| 旧语义、定位和编辑记录：仅参考 | 9 | 263,041 | `records` | `previous_work/reference_results/records` |
| 旧 LangSplat 地面估计：仅参考 | 1 | 2,552 | `industrial_swap_v2/records/m3_placement_173dd1e8.json` | `previous_work/reference_results/ground_reference.json` |
| 旧实验配置：仅参考 | 11 | 42,002 | `industrial_swap_v2/configs` | `previous_work/reference_results/industrial_swap_configs` |
| 旧预处理脚本：归档不执行 | 6 | 15,014 | `scripts` | `previous_work/paper/source_scripts` |
| 旧实验比较预览：仅参考 | 2 | 7,294,103 | `outputs/comparison` | `previous_work/reference_results/previews` |
| 通用预训练 SAM ViT-H 权重 | 1 | 2,564,550,879 | `models/torch/hub/checkpoints/sam_vit_h_4b8939.pth` | `models/sam/sam_vit_h_4b8939.pth` |
| 通用预训练 OpenCLIP ViT-B/16 权重与配置 | 2 | 598,530,420 | `models/huggingface/hub/models--laion--CLIP-ViT-B-16-laion2B-s34B-b88K/snapshots/7288da5a0d6f0b51c4a2b27c624837a9236d0112` | `models/openclip_vit_b16` |

## 直接输入与兼容性处理

1. 从旧工程复制原视频、350 张提取图像、350 张去畸变图像、COLMAP 相机与稀疏模型。新流程直接读取 `data/images` 和 `data/colmap/sparse/0`，项目内 `data/sparse` 链接指向本项目副本。
2. 原视频为 2560×1440、约 29 fps、174.89655 秒；旧流程以约 2 fps 提取 1920×1080 图像。去畸变图像为 1875×1056。350 个相机全部注册，沿用已保存的 306 训练 / 44 测试划分；固定参考帧为 1、49、97、145、193、241、289、345。
3. 原最终 3DGS 包含 1,828,777 个三尺度椭球；官方 ReLaGS 2DGS 渲染接口使用两个尺度的面元。删除第三尺度不是无损适配，故旧 PLY 和检查点仅作审计与对照，使用复制的图像/COLMAP 重新完成官方 2DGS 30000 步训练。审计证据见 `outputs/relags_baseline/01_gaussian_scene/data/compatibility_audit.json`。新高斯及检查点位于该阶段 `data/model/`。
4. 复制的 SAM/OpenCLIP 是通用预训练编码器权重；本次重新从 RGB 计算全部 SAM 掩膜、CLIP 和 OpenSeg 特征。旧 LangSplat 特征、旧 SAM 分割、设备实例定位和编辑结果未进入新语义流程。
5. 保留原 COLMAP 坐标与原相机模型，未缩放、旋转或重定位输入。缺少独立公制尺度和重力标定。历史 LangSplat 地面仅保存在 `previous_work/reference_results/ground_reference.json` 供参考。场景坐标、范围、内外参、相机轨迹与划分的派生记录位于 `data/scene_information/` 和 Stage 00；派生文件不计入上述复制数量。

## 历史资料及排除范围

没有找到旧论文完整正文；保留现有报告、图表及实验说明，不补造无人机、相机型号或工业设备规格。历史配置里的绝对路径按原样归档，不作为新流程运行配置。

未迁移大量历史检查点、生成模型/扩散模型权重、环境缓存、旧语义数组和重复实验输出。初次候选复制中的 141 个重复历史图表副本经核验后，仅从新工程副本中移除；原工程文件未动。记录位于 `outputs/relags_baseline/00_data_check/data/excluded_duplicate_copies.json`。初始选择数量和后续补入最终检查点/通用编码器权重的历史记录均保留；以本文件、最终 manifest 和 `metrics/migration_summary_final.json` 为当前数量依据。

## 独立运行与审计

所有迁移均为复制，未移动、删除或写入原工程。最终核验覆盖全部 798 个复制文件：目标 SHA256 与迁移记录一致，全部源文件的大小和纳秒修改时间与初始只读清单一致，缺失审计覆盖项为 0。核验没有发现目标校验失败或源文件元信息变化。证据：`outputs/relags_baseline/00_data_check/metrics/final_integrity.json`；原工程完整清单：`outputs/relags_baseline/00_data_check/data/source_inventory.jsonl`。

数据、模型、输出目录中的 32 个运行期符号链接均有效并指向本项目内部。环境位于 `envs/`，权重缓存位于 `models/`；后续新权重通过本机代理经 SSH 转发下载，来源与校验记录单独保存在模型目录，不计入旧工程迁移表。整个复现无需读取旧工程语义结果或使用其环境。

本地 `E:\codex_projects\paper_in` 保存控制脚本、报告和少量预览副本；完整计算数据与约 49 GiB 的本次阶段输出保留在远程工作目录。最终执行状态见 [EXPERIMENT_REPORT.md](EXPERIMENT_REPORT.md)：Stage 00–07 完成，完整场景图失败，开放词汇查询完成、完整关系查询受阻。

## R1 续跑的数据复用

本次未再复制或修改 `paper_eli` 文件，798 个迁移文件与原 TSV 不变。`outputs/relags_obb_repair_r1/08_scene_graph/data/model/` 通过本项目内部只读使用的链接复用 Baseline 0 Stage 03 PLY 和 Stage 06 OpenSeg NAG；R1 Stage 09 链接复用原 12 项开放词汇数据和可视化。新写入项仅为排查、OBB 边界处理后的完整场景图、6 项关系查询和记录。原 Baseline 0 4298 个文件/链接经最终核验未改变。详见 `OBB_REPAIR_REPORT.md`。
