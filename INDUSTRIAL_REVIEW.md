# 工业场景检查：R1 更新

完整图与六项关系查询现已执行；具体查询返回、阈值回退及几何边界限制见 `OBB_REPAIR_REPORT.md`。此前的分割、粗层合并、标线/地面混淆等问题不因流程跑通而消失。

## 关系查询的实际视觉检查

已查看六查询总图、放大对照图、relation_00 的第 241 帧原尺寸叠加图，以及完整 L2 图的第 49 帧投影。放大图只用于显示已存在的浮点投影，不改变原查询掩膜。

- relation_00（蓝箱靠近设备）、relation_01（灰色容器位于地面上）和 relation_05（蓝箱在灰色容器左侧）返回完全相同的 L2 组 2208，共 52 个高斯。第 241 帧可见红色只覆盖蓝色堆箱的局部小片段；没有分出完整箱体。灰色容器查询也选中这个蓝箱片段，属于明确需要标注核查的类别混淆。三者在该视角投影大于 0.5 的像素均为 95。
- relation_02（控制柜附着于设备）触发官方回退：关系相似度 0.25844，小于 0.4；图预测类别为 smaller than。所选主体在第 241 帧主要落于右边界附近的局部结构，不能凭该结果确认控制柜身份或附着关系。
- relation_03（滚筒是输送带的部件）触发官方回退：主体相似度 0.48776，小于 0.55，只选中 13 个高斯。最佳固定视角第 241 帧最大投影权重仅 0.17342，超过 0.5 的像素为 0；未形成可辨识的完整滚筒定位。图预测类别为 front，不能把请求中的 part of 当成预测结果。
- relation_04（金属框架连接设备）包含 L2 399 和 L3 261，共 1,372 个高斯；第 1 帧可见选中上方/背景金属结构。类别外观与框架有一定对应，但选中边的图类别为 front / close by，无法据此确认 connected to。
- 完整 L2 场景图在第 49 帧能投影显示节点和边；画面只展示 269,134 条两端在视锥内边中的 20 条，未做遮挡判断。投影可查看不代表边具有真实物理关系，完整原始边和分数另存。

六项查询中选中边均不直接涉及本次五个退化 OBB 节点；原分组与语义特征均未修改。上述语义/关系问题不能简单归因于 OBB 修复。它们提示层次叶组选择、领域外语义表征、关系原型相似度及官方回退规则仍需后续独立评估。本次只记录，不调整查询或网络。

证据：`09_relational_query/metrics/relational_review.json`、`relational_localization_diagnostics.json`、原始 `data/relation_*/raw_query.pt`、`visualizations/relational_query_overview.jpg` 和 `relational_query_crops.jpg`（相对于 R1 输出目录）。投影统计不是定位准确率。


## 原始 Baseline 0 检查（历史记录）

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
