# 精细三维实体表达与空间关系约束的贡献分析

Contribution analysis of refined entity representation and spatial relation constraints.

(a,b) 同23条查询、同纵轴范围的有符号IoU差值。精细实体相对同可用性粗框平均+0.75 pp，12升/10降/1不变；关系约束平均+17.18 pp，20升/1降/2不变，保留所有负值和零值。(c) 四种配置的离散Precision/Recall均值，非PR曲线；箭头仅表示两个主要机制配置差异。精细实体Precision +14.00 pp、Recall -13.52 pp；关系约束Precision +25.15 pp、Recall -0.33 pp。空心all-33粗框使用不同可用性，仅作补充，不能当作单一机制对照。SAM辅助伪真值。

(a,b) Signed IoU differences use the same 23-query order and axis range. Entity refinement versus availability-matched boxes averages +0.75 pp (12 improved/10 declined/1 unchanged); relation constraints average +17.18 pp (20/1/2). All negatives and zeros remain. (c) Discrete configuration means, not a precision-recall curve. Arrows show only the two main configuration contrasts. Entity refinement changes precision/recall by +14.00/-13.52 pp; relations change them by +25.15/-0.33 pp. The hollow all-33 box point has different availability and is a supplement, not a single-mechanism contrast. Evaluation uses SAM-assisted Pseudo-GT.
