# 定量评价已补充（SAM-assisted Pseudo-GT）

本轮主表精度采用统一的 23 条查询 / 44 个视角；25/25 是各方法的执行数，不是全部查询均有可靠参考。6 个视角统一排除。参考和预测均已锁定。

[完整定量报告](QUANTITATIVE_EVALUATION_REPORT.md) · [带参考与 IoU 的全部结果图](docs/GALLERY.md)

# 工业场景关系检索外部对比：实际运行报告

本轮执行统一的 25 条关系查询，包含五种空间关系、八类工业设备。原始结果、失败日志、相机与参数均保存；本报告不将自动预测作为真值。

## 汇总

| Method | Completed Queries | Projection mIoU | Precision | Recall | Query Time (s) | Render (s) | End-to-end (s) |
|---|---:|---|---|---|---:|---:|---:|
| LangSplat | 25/25 | 20.87% | 29.28% | 36.32% | 0.346610 | 0.053795 | 0.406716 |
| THGS | 25/25 | 8.68% | 14.40% | 10.16% | 0.010730 | 0.044890 | 0.055572 |
| ReLaGS | 25/25 | 0.35% | 11.00% | 0.35% | 0.106590 | 0.021297 | 0.127786 |
| Ours | 25/25 | 63.70% | 84.33% | 70.21% | 0.002580 | 0.017453 | 0.020073 |

耗时为每查询 3 次同步测量中位数的跨查询平均；1 次预热，使用同一 A6000 GPU 0，导出 I/O 不计入在线时间。LangSplat 的查询时间包含所有选定视角的语义解码和掩膜后处理，其他方法在场景级选择集合。端到端时间实际测量，不只相加阶段均值。模型加载见下表，GPU 占用采样见 logs/*/*/gpu.csv（设备总占用含原有常驻进程）。

| Method | Load (s) | View masks | Empty view masks | Official fallback queries | Fine-instance-unavailable queries |
|---|---:|---:|---:|---:|---:|
| LangSplat | 7.441 | 50 | 0 | 0 | 0 |
| THGS | 8.321 | 50 | 11 | 0 | 0 |
| ReLaGS | 56.588 | 50 | 31 | 14 | 0 |
| Ours | 4.098 | 50 | 2 | 0 | 4 |

空视角掩膜可以由对象不在该视角、遮挡、选中极小区域或检索错误产生，不能直接视为查询失败。正常空输出、执行失败及精细实例不可用在记录中分开。

## 输入与方法

- LangSplat：连续三维语言特征场，复用 paper_eli 的三层 iteration 30000 模型与 AE。已有 306/44 划分与当前数据一致，位置与原生场景逐点相同。调用官方编码/渲染，按官方层次选择与 0.4 阈值输出二维掩膜，不发明三维集合。
- THGS：无需额外训练的超点图/层次表达，使用独立新克隆的官方源码，从未裁剪 2DGS、306 张训练图像已有 SAM/CLIP 特征重新构建 KNN、重加权、cut-pursuit 和层次特征。不是用 ReLaGS 分组代替。
- ReLaGS：复用 R1 语义/层次及官方关系 GNN，在独立副本中对几何输入做全局工业坐标旋转并重算关系，沿用 R1 的五个退化 OBB 工程处理。保存官方层次节点、关系分数、排名和阈值回退。
- Ours：直接加载冻结 v2 的真实查询引擎及实例。已有类别别名与 M0 关系先验均保留；局部实例按实际高斯参与，精细实例不可用仅保留粗位置，不用粗框生成预测掩膜。

本实验对比的是不同输入条件下的工业应用，不是等先验、等底层表示的消融。Ours 使用已知类别/身份/粗几何，其他方法无设备先验。ReLaGS 仅共享全局方向标定。

## 查询、视角和输出

[完整协议](EXPERIMENT_PROTOCOL.md) 和 configs/*.json 给出全部冻结参数、类别、关系及相机。M0 的确定性几何只用于查询候选设计和相机覆盖参考，尚未成为人工 GT。冻结发生于所有正式批量查询之前。
共 29 个不同保留相机、50 个查询—视角组合；统一 938×528。

每个 `outputs/<method>/Qxxx/` 保存 result.json、原始查询、精细索引/PLY（适用方法）及每相机响应、掩膜、热图、叠加图、相机。THGS 离线中间结果在 outputs/thgs/model/，ReLaGS 适配中间结果在 outputs/relags/coordinate_adaptation/。

[全部结果图集](docs/GALLERY.md) 覆盖五种关系和全部查询的固定视角，另有跨八类设备的代表性案例与三维独立区域图。具体目视观察见 [VISUAL_REVIEW](docs/VISUAL_REVIEW.md)。

## 兼容性与失败记录

所有失败尝试保存在 logs 中，未覆盖旧实验。必要修复仅涉及：THGS 独立环境编译及 TMPDIR、PyG keys API；适配脚本的模块搜索路径和真实权重路径；ReLaGS 全局方向标定和既有 OBB 边界处理。THGS 官方初始 KNN 报告 226 个负邻居条目，其官方后续处理保持原样，不据此调整算法。具体实际源码差异见 docs/patches。

| Stage | Exit | Seconds | Log record |
|---|---:|---:|---|
| asset_audit | 0 | 18.79 | logs/asset_audit/20261127T020011323316Z/ |
| comparison_gallery | 0 | 13.55 | logs/comparison_gallery/20261127T023130218521Z/ |
| comparison_gallery | 0 | 23.98 | logs/comparison_gallery/20261127T023459472665Z/ |
| comparison_gallery_final | 0 | 12.40 | logs/comparison_gallery_final/20261127T024044499317Z/ |
| evaluate_interface | 0 | 0.19 | logs/evaluate_interface/20261127T022422276917Z/ |
| generated_asset_audit | 0 | 5.04 | logs/generated_asset_audit/20261127T023454353717Z/ |
| langsplat_queries | 1 | 22.14 | logs/langsplat_queries/20261127T021418857215Z/ |
| langsplat_queries | 1 | 4.59 | logs/langsplat_queries/20261127T021528624634Z/ |
| langsplat_queries | 0 | 159.30 | logs/langsplat_queries/20261127T021551610971Z/ |
| ours_3d_display | 0 | 5.48 | logs/ours_3d_display/20261127T023124659874Z/ |
| ours_queries | 0 | 16.17 | logs/ours_queries/20261127T023047223889Z/ |
| output_validation_report | 0 | 24.56 | logs/output_validation_report/20261127T023143854373Z/ |
| protocol_selection | 0 | 15.47 | logs/protocol_selection/20261127T020704077557Z/ |
| relags_3d_display | 0 | 5.39 | logs/relags_3d_display/20261127T022641233571Z/ |
| relags_coordinate_alignment | 1 | 10.29 | logs/relags_coordinate_alignment/20261127T020826827581Z/ |
| relags_coordinate_alignment | 0 | 103.63 | logs/relags_coordinate_alignment/20261127T021006542119Z/ |
| relags_queries | 1 | 3.78 | logs/relags_queries/20261127T021150245144Z/ |
| relags_queries | 0 | 85.94 | logs/relags_queries/20261127T021252855916Z/ |
| thgs_3d_display | 0 | 5.59 | logs/thgs_3d_display/20261127T023107392390Z/ |
| thgs_environment | 1 | 42.59 | logs/thgs_environment/20261127T020712341630Z/ |
| thgs_environment_tmpfix | 0 | 59.04 | logs/thgs_environment_tmpfix/20261127T020844195045Z/ |
| thgs_graph_extensions | 0 | 67.87 | logs/thgs_graph_extensions/20261127T021214968560Z/ |
| thgs_grid_extension | 0 | 1.57 | logs/thgs_grid_extension/20261127T021322910072Z/ |
| thgs_hierarchy | 0 | 409.62 | logs/thgs_hierarchy/20261127T022335744153Z/ |
| thgs_neighbors | 1 | 9.68 | logs/thgs_neighbors/20261127T021831194483Z/ |
| thgs_neighbors | 0 | 12.38 | logs/thgs_neighbors/20261127T022015310232Z/ |
| thgs_partition | 1 | 19.70 | logs/thgs_partition/20261127T022118207478Z/ |
| thgs_partition | 0 | 25.50 | logs/thgs_partition/20261127T022310164597Z/ |
| thgs_queries | 0 | 21.68 | logs/thgs_queries/20261127T023025463012Z/ |
| thgs_reweight | 0 | 50.35 | logs/thgs_reweight/20261127T022027773356Z/ |

## 评价与后续人工工作

独立人工 GT 的指标仍待标注；本轮 SAM-assisted Pseudo-GT 的实际投影 mIoU、Precision、Recall 已计算，见定量报告。评价器已验证 TP/FP/FN、空预测、忽略像素及查询等权平均；不允许用自动分割或 M0 粗框填充真值。需对冻结查询独立确认参照与正确目标集合，再标注每个固定 RGB 视角中可见设备像素，包含 Ours 精细实例缺失的正确目标。接口见 evaluation/ground_truth/README.md。

当前已获得伪真值上的实际数值；该排名和差值受共享 M0 先验、SAM 参考偏差及统一样本排除影响，不能当作独立人工真值结论。工业坐标下关系与通用数据集学习关系可能不同；对象粒度、遮挡、几何缺失、类别描述和有限节点选择都可能影响结果。

保护检查：44,930 个原有文件大小/mtime 未变，所有关键资产 SHA-256 一致；查询冻结哈希通过。输出尺寸、相机、掩膜阈值和索引已核对。

## THGS 实际生成资产

官方离线构建从 865,920 个高斯得到 22,317 个初始超点，后续层次节点为 9,367 / 2,433 / 1,140；三个语义层均为 512 维，检查无 NaN/Inf 或零特征。实际资产哈希及检查结果见 `inputs/generated_assets.json`。官方合并入口未显式固定随机视角顺序，重建可能产生差异；后续查询应复用本次冻结产物。
