# 不同方法的空间关系引导实例检索性能分布

Query-wise performance distribution of spatial relation-guided instance retrieval.

(a) 25条查询按原顺序展示，Q005/Q025缺少可靠参考，标灰N/A；真实零值保留在色标中。(b) 23条有效查询逐查询IoU分布，均值为LangSplat 20.87%, THGS 8.68%, ReLaGS 0.35%, Ours 63.70%；Ours在21/23条中严格最高。箱体为Q1—Q3、中线为中位数、菱形为均值，须端为1.5 IQR范围内的实际极值；展示全部查询点，仅进行固定种子水平抖动。两阶段平均：先有效视角、后等权查询。参考为SAM辅助伪真值，非独立人工真值；查询可能共享设备或视角，不进行显著性检验。

(a) All 25 queries retain their original order. Q005/Q025 lack reliable references and are gray N/A; genuine zeros remain on the color scale. (b) All 23 evaluated query IoUs are shown. Means: LangSplat 20.87%, THGS 8.68%, ReLaGS 0.35%, Ours 63.70%. Ours is strictly highest on 21/23 queries. Boxes span Q1-Q3, center lines are medians, diamonds are means, and whiskers end at observations within 1.5 IQR. Jitter is horizontal only with a fixed seed. Metrics average eligible views first, then queries equally. References are SAM-assisted Pseudo-GT, not independent human GT. Queries can share devices/views; no significance test is performed.
