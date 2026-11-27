# 基于 SAM-assisted Pseudo-GT 的工业关系检索定量评价

本轮已实际计算四种方法的投影指标。复用原有全部预测与计时，未重新训练、运行查询或调整分割参数。参考掩膜来自原始留出 RGB 的新 SAM 推理及 Codex 视觉检查，**不是人工精细真值**。

## 实际汇总

统一评价 23/25 条查询、44/50 个固定视角。两条查询没有可靠参考而被排除，另两条各保留一个视角；各方法使用完全相同的样本。数值单位为百分比。

| Method | Projection mIoU ↑ | Mean Precision ↑ | Mean Recall ↑ | Query Time ↓ | End-to-end ↓ |
|---|---:|---:|---:|---:|---:|
| LangSplat | 20.87% | 29.28% | 36.32% | 0.346610 s | 0.406716 s |
| THGS | 8.68% | 14.40% | 10.16% | 0.010730 s | 0.055572 s |
| ReLaGS | 0.35% | 11.00% | 0.35% | 0.106590 s | 0.127786 s |
| Ours | 63.70% | 84.33% | 70.21% | 0.002580 s | 0.020073 s |

在这个经过质量筛选的伪真值集合上，Ours 比最佳外部方法 LangSplat 的 Projection mIoU 高 **42.83 个百分点**。这是共享工业先验和 SAM 参考条件下的内部结果，不能直接写成独立人工 GT 上的优势。

## 参考数据如何获得

- 目标身份：直接读取 M0 r29 粗框、类别、工业坐标，与原始 RGB 和设备布局核对；新脚本逐对重新计算关系，未读取 Ours 关系图、查询返回 ID 或任一方法预测掩膜。
- 集合语义：与至少一个参照类别实例满足关系即可。方向采用 +X 右、+Y 前、+Z 上；严格轴向间隔 0.02，near 的 AABB 间距 <0.35，均为 SfM 相对单位。每对几何证据保存在 target_audit.json。
- 像素参考：既有 Meta SAM ViT-H，在固定原始 RGB 的 938×528 像素网格上重新推理。初始投影框仅作提示；通过原图补充正负点、收紧可见对象框、比较 SAM 三个候选。没有将粗框、已有三维实例或任何方法的预测直接作为参考。
- 逐个查看全部 66 个设备—视角组合。对混入相邻设备、错误选中背景、黑色工件与白色底座分离等问题进行最多三轮局部修订；首轮、每轮候选、提示、原始 SAM 分数与日志全部保留。
- 最终选用版本分布：{'initial': 31, 'review2': 10, 'review1': 23, 'review3': 2}；其中 6 个设备视角仍不可靠。SAM 预测 IoU 仅辅助候选查看，不当作实际评价 IoU。
- 多设备查询取可见掩膜的并集；某个必要目标的参考仍不可靠时，排除整个查询—视角，避免用不完整目标集合计分。
- 先保存并哈希锁定 REFERENCE_FROZEN.json，再读取冻结方法掩膜进行首次计分。全部既有查询、相机、预测与阈值保持原样。

M0 几何重新计算的“独立”是指不复制 Ours 返回结果，**不代表独立先验**：目标标签、坐标和关系定义仍与 Ours 共享 M0，可能使该评价更有利于 Ours。SAM 训练来源及边界偏好也是共同的参考偏差。

## 同一评价样本集合

| Query | Camera | 排除原因 |
|---|---|---|
| Q005 | frame_000217 | Distant panel/rack overlaps a separate workstation; object ownership and thin structure remain uncertain after prompts. |
| Q005 | frame_000065 | M0 box spans rear large panel/rack plus separate front workstation; visible ownership cannot be reliably resolved in this view after additional prompts. |
| Q009 | frame_000161 | Loaded fixture heavily occluded by pole and rack; SAM retains base but omits identifiable black-workpiece surfaces. Complete visible extent not reliable. |
| Q010 | frame_000129 | Distant bin group crossed by foreground beam: SAM repeatedly includes separate stand/workbench and misses bin surfaces; reference not reliable.; Rear multi-stack bins overlap front separate stack; SAM misses substantial mixed-material faces and leaks onto foreground fixture despite added points. |
| Q025 | frame_000217 | Distant panel/rack overlaps a separate workstation; object ownership and thin structure remain uncertain after prompts. |
| Q025 | frame_000121 | Overlapping open racks: SAM alternatives either fill substantial visible gaps or omit many visible rods. Cannot reliably define complete device-specific visible mask. |

Q005、Q025 的两个视角均被排除；Q009、Q010 各有一个视角被排除。不能把主表称为完整 25 查询精度。没有目标被确认完全不可见；这 6 个视角是参考可靠性不足，而非将方法的空预测排除。Q019 两个视角的 Ours 空预测均纳入零分。

被排除样本包含开放料架和复杂遮挡，可能改变各方法的平均表现，特别限制对料架类、left 和 near 的结论。原定性图中 Q005/Q025 的外部方法料架响应仍完整保留，不能因为当前无法可靠标注就宣称这些方法在该类查询无效。

## 指标及零值规则

逐视角计算 TP、FP、FN；IoU=TP/(TP+FP+FN)，Precision=TP/(TP+FP)，Recall=TP/(TP+FN)。目标可见而预测为空时三个指标均为 0。先在查询内平均有效视角，再对有有效视角的查询等权平均。排除样本不是零分，不进入分母。每条查询、每个视角、每种关系均保存 CSV 和 JSON。

正式四种方法的最终查询均成功执行；早期环境/接口调试失败日志保留，未混作正常空结果。本轮首次 SAM 记录序列化失败已修复并重试，失败日志同样保留。

| Method | 有效查询/视角 | 正常空掩膜：有效集合 | 正常空掩膜：全部50 | 最终查询运行失败 |
|---|---|---:|---:|---:|
| LangSplat | 23/44 | 0 | 0 | 0 |
| THGS | 23/44 | 11 | 11 | 0 |
| ReLaGS | 23/44 | 30 | 31 | 0 |
| Ours | 23/44 | 2 | 2 | 0 |

## 各关系类型 Projection mIoU

按该关系下有效查询等权平均，不是像素池化。

| Relation | Queries / views | LangSplat | THGS | ReLaGS | Ours | Ours − best external |
|---|---|---:|---:|---:|---:|---:|
| left_of | 4 / 8 | 24.35% | 20.32% | 0.36% | 65.91% | +41.56 pp |
| right_of | 5 / 8 | 19.61% | 12.54% | 0.08% | 64.61% | +45.00 pp |
| in_front_of | 5 / 10 | 18.37% | 0.00% | 0.00% | 70.57% | +52.20 pp |
| behind | 5 / 10 | 23.22% | 11.13% | 1.23% | 49.14% | +25.92 pp |
| near | 4 / 8 | 19.14% | 0.00% | 0.00% | 69.94% | +50.79 pp |

## 实际结果分析

- 优势主要出现在前方、邻近与右侧关系：在本次有效样本中，已知设备身份和几何关系帮助 Ours 避免同时选择同类设备、参照类别或其他架体。该优势包含 M0 先验贡献，不能全部归因为精细三维提取算法。
- LangSplat 是本轮最强外部方法。Q001 冷风机的查询平均 IoU 为 84.07%，THGS 为 81.26%，说明外部方法在清晰类别上可以有效。两者对复合关系句仍常激活参照类别或多个同类区域。
- Q019 是明确反例：LangSplat 63.08%、THGS 55.66%、Ours 0%。Ours 命中身份但精细实例缺失，被如实记零；Q010 的 Ours 也只有 10.20%，低于 LangSplat 51.18% 和 THGS 26.85%。
- ReLaGS 有效集合中 30/44 个视角为空；非空输出也常仅有极少目标像素。因此其 Recall 为 0.35%，mIoU 为 0.35%。Precision 11.00% 不代表较完整检索，极小但命中目标的片段也可能有较高 Precision。保留其官方回退和原始投影规则，未为改善数值重新调参。
- Ours 的 Mean Precision 84.33% 高于 Recall 70.21%，提示在当前参考下，剩余问题更多表现为设备部分结构未保留、可用实例缺失或局部可见区域不足。参考中镂空结构被 SAM 填实也会人为降低稀疏三维投影的 Recall；因此不能把所有差距直接归结为算法漏检。

## 时间、验证与复用

主表 Query Time 和 End-to-end 沿用上一轮同一 A6000 GPU 0 的 25 查询实测，1 次预热、3 次测量取中位数后平均；不含模型加载和导出 I/O。LangSplat 查询计时包含两个视角的解码/后处理。另在 summary.csv 保存有效23查询子集的 Query Time，避免混淆。

评价器检查 TP/FP/FN、空预测、忽略像素、查询等权；另从逐视角记录独立重算聚合结果并断言一致。参考锁哈希和原配置锁通过；750 个既有预测/相机/响应文件的保留检查记录在 pseudo_prediction_preservation.json。

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/relational_retrieval_benchmark
PYTHONDONTWRITEBYTECODE=1 ../../envs/relags/bin/python scripts/evaluate_pseudo_metrics.py
PYTHONDONTWRITEBYTECODE=1 ../../envs/relags/bin/python scripts/publish_pseudo_evaluation.py
PYTHONDONTWRITEBYTECODE=1 ../../envs/relags/bin/python scripts/snapshot_predictions.py --verify
```

已冻结参考后不要直接重跑 finalize_pseudo_reference.py 或覆盖掩膜。新参考修订应创建版本，并对全部方法同步重算。独立人工 GT 接口保留在 evaluation/ground_truth/；本轮已有真实数值，正式人工 GT 仍需后续独立标注。

## 文件入口

- [全部定量对比图](docs/GALLERY.md)：Original RGB / Reference Mask / LangSplat / THGS / ReLaGS / Ours，逐视角标注 IoU，排除样本显示 N/A。
- [汇总 CSV](evaluation/metrics/summary.csv)、[逐视角](evaluation/metrics/per_view.csv)、[逐查询](evaluation/metrics/per_query.csv)、[逐关系](evaluation/metrics/per_relation.csv)。
- evaluation/pseudo_ground_truth/ 下保存原图、目标 IDs、相机、提示、候选、最终参考、叠加图、质量记录和锁文件。
