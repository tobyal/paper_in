# T02_relations

| Relation | Queries | Views | LangSplat | THGS | ReLaGS | Ours | Best |
| --- | --- | --- | --- | --- | --- | --- | --- |
| left_of | 4 | 8 | 24.35 | 20.32 | 0.36 | 65.91 | Ours |
| right_of | 5 | 8 | 19.61 | 12.54 | 0.08 | 64.61 | Ours |
| in_front_of | 5 | 10 | 18.37 | 0.00 | 0.00 | 70.57 | Ours |
| behind | 5 | 10 | 23.22 | 11.13 | 1.23 | 49.14 | Ours |
| near | 4 | 8 | 19.14 | 0.00 | 0.00 | 69.94 | Ours |

Projection IoU (%); equal query weight within relation. Best column is computed from actual values. SAM-assisted Pseudo-GT, not independent human GT. 23 valid queries / 44 valid query-view pairs from frozen 25 / 50. Mean over valid views within query, then equal query weight; empty prediction Precision=0. External methods lack equipment M0 priors; Ours uses them.
