# T03_ablation

| Configuration | Refined | Relation | mIoU (%) | Precision (%) | Recall (%) |
| --- | --- | --- | --- | --- | --- |
| Box-based | No | Yes | 62.95 | 70.33 | 83.72 |
| Ours w/o Relation | Yes | No | 46.52 | 59.18 | 70.54 |
| Ours | Yes | Yes | 63.70 | 84.33 | 70.21 |

Box-based and Ours have identical matched and renderable equipment IDs; only Gaussian membership differs. SAM-assisted Pseudo-GT, not independent human GT. 23 valid queries / 44 valid query-view pairs from frozen 25 / 50. Mean over valid views within query, then equal query weight; empty prediction Precision=0. External methods lack equipment M0 priors; Ours uses them.
