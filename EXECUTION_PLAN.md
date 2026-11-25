# ReLaGS Baseline 0 实际执行方案

工作目录为远程 `/mnt/sda/ubuntu/lkx/papers/paper_in`，不是本机可视化临时目录。原工程只读。版本：ReLaGS `52cc0c98b0ccf9afebea31901bf79246650286b3`；2DGS 作者仓库 `hbb1/2d-gaussian-splatting` 的版本记录于环境清单。ReLaGS README 中的 plumerai 链接当前返回 404，失败日志保留。

## 数据与表示

复用原视频、350 张 COLMAP 去畸变图像、相机与稀疏模型、306/44 划分。原始 3DGS 有 1,828,777 个高斯和 3 个 scale 属性；ReLaGS CUDA 将 scale 解释为 `glm::vec2`，其几何是二维面元。删除第三维不是无损格式适配，因此重新训练官方 2DGS 30000 步。保留同一 COLMAP 坐标规范、同一划分、SH3，训练分辨率 `-r 2` 与旧基础训练一致。默认 2DGS 正则化与致密化参数不修改。

## 按源码实际顺序执行

1. **00**：全工程元信息清单、精选物理复制、逐文件 SHA256、划分验证、原始 RGB 与相机轨迹预览。
2. **01**：表示兼容性证据、独立依赖环境、官方 2DGS 训练及 7000/15000/30000 检查点、统一相机 RGB/深度/法线、留出视角重建指标。
3. **02**：官方 `scripts/image_encoding.py`，重新运行 SAM ViT-H + OpenCLIP ViT-B/16 laion2b_s34b_b88k；保存四层 SAM mask 与 512D 特征。OpenSeg 分支按作者指向的 `scene_graph/data_anno/scan3r_packer.py::extract_openseg_img_feature` 进行工业图像接口适配，使用原 OpenSeg 模型和 768D 特征，不以另一 CLIP 模型替代。
4. **03**：`max_weight_pruning.py`，使用论文及 launcher 的阈值 `0.0005`（不是 CLI 默认 0.1，也不是配置文件中未实际使用的 0.005）。保存每点最大贡献、保留索引、移除与保留高斯、统一视角裁剪前后比较。
5. **04**：第一次 `sp_partition.py -a --iteration 0` 实际只生成 `neighbor.pt`；保存邻接索引与距离。随后为该阶段保留一次使用原始邻接的 Cut Pursuit 诊断输出，如需要时明确它不进入主流程。
6. **05**：官方 `graph_weight.py --level 1 --config configs/lerf.yml`、第二次 `sp_partition.py -k neighbor_new.pt --pcp_regularization 0.1 --pcp_spatial_weight 0.1 -a`，再 `merge_proj.py --thres_connect 0.9,0.7,0.7 --thres_merge 20 --tau 3 --iteration 0`。保存重加权统计、Cut Pursuit 划分、逐视角投影标签、逐层邻接与成员索引。参数采用实际 LERF launcher，作为工业自定义数据初始设置，不进行调参。
7. **06**：ROFA 在 `merge_proj.py` 各层合并后执行，属于交替依赖，不能错误宣称是完全独立的官方 CLI。仅增加输出钩子，保存聚合前逐视角特征、视角 ID、权重、离群值判定与聚合后特征；提供使用保存输入重放官方函数的入口。
8. **07**：从官方输出导出对象/部件层次、索引、着色 PLY、成员关系与统一视角图；不以旧语义结果或手工分割代替。
9. **08**：使用官方预训练 GNN 与其 768D OpenSeg 输入、512D Jina 关系嵌入，保留节点 OBB、边候选、预测分数、关系与场景图。该数据没有公制标定，官方 5.0 距离阈值只能按原 COLMAP 单位执行并明确记录域差异。
10. **09**：调用官方 `SemanticNAG` 和 `utils/triplet_search_utils.py::search_triplet_subjects`；固定工业对象、部件、重复实例和关系查询清单，保存全量分数、索引与可视化。没有真实语义/关系标注时不报告虚构 mIoU 或准确率。

## 工程与保存约定

- `previous_work` 永不进入新语义流程。旧 LangSplat 地面平面仅作参考，不用于调整输入坐标系。
- 独立环境和模型缓存位于本工程。GPU 共享，优先使用空闲 GPU 3；不停止他人进程。
- 保留原始官方源码、所有实际接口/记录补丁、命令、配置、失败尝试、运行耗时和每 5 秒显存采样。阶段状态由实际文件与返回码核验。
- 固定参考相机见 `configs/reference_views.json`。中间数据与可视化分开保存。
- 每阶段独立输出路径；声明的输入或配置指纹变化使相应缓存失效，旧尝试的命令与日志保留。共享导入代码未必自动列入输入；修改后应使用 --force 或新的实验输出目录。恢复训练使用官方 checkpoint 参数，二维特征按完整的 mask/feature 对恢复。
- 作者确认 OpenSeg 与同维度 CLIP 不可替换，见 https://github.com/dfki-av/ReLaGS/issues/4#issuecomment-4903379261 。关系 GNN 对尺度与训练域存在迁移风险，见 https://github.com/dfki-av/ReLaGS/issues/3#issuecomment-4507638043 。仅记录问题，不修改核心算法。

## 最终执行状态

Stage 00–07 已完成并核验；350 帧 SAM/CLIP/OpenSeg 全部重新计算，两个分支的 ROFA 重放误差为 0。Stage 08 完整 L2/L3 图在官方 OBB 构建处失败：5 个 L2 分组只有 1 或 3 个原始点，失败输入、索引及完整日志保留。独立 L3 图完成，仅作为诊断，不替代完整图。Stage 09 完成 12 个开放词汇查询；6 个完整关系查询因上游缺失未执行。

本次有限调度任务已结束，没有仍在运行的阶段作业。最终证据、问题分析及待执行关系查询命令见 `EXPERIMENT_REPORT.md`、`BASELINE_STATUS.json` 和各阶段目录。没有为跑通流程修改退化节点处理规则。

## R1 续跑执行完成

按用户新增要求，独立封存 Baseline 0 元信息与报告；重放官方 L2 并重现 OBB 失败；为 1–3 点补充退化 PCA 包围盒；验证正常节点逐值一致；使用验证过的官方边分批参数完成完整 L2/L3 图；执行原 6 项关系查询并保存全部中间结果；最后核验原基线未变。结果与限制见 `OBB_REPAIR_REPORT.md`。
