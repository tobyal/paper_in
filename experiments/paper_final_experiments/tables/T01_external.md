# T01_external

| Method | Projection mIoU (%) | Precision (%) | Recall (%) |
| --- | --- | --- | --- |
| LangSplat | 20.87 | 29.28 | 36.32 |
| THGS | 8.68 | 14.40 | 10.16 |
| ReLaGS | 0.35 | 11.00 | 0.35 |
| Ours | 63.70 | 84.33 | 70.21 |

SAM-assisted Pseudo-GT, not independent human GT. 23 valid queries / 44 valid query-view pairs from frozen 25 / 50. Mean over valid views within query, then equal query weight; empty prediction Precision=0. External methods lack equipment M0 priors; Ours uses them.
