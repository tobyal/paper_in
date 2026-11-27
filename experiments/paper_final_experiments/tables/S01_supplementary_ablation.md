# S01_supplementary_ablation

| Configuration | mIoU (%) | Precision (%) | Recall (%) | Evaluated_views |
| --- | --- | --- | --- | --- |
| Box-based (all 33) | 68.07 | 72.51 | 90.94 | 44 |
| Multi-view SAM (19 available) | 21.62 | 58.63 | 22.62 | 44 |
| Multi-view SAM (shared 17) | 21.62 | 58.63 | 22.62 | 44 |
| Ours (shared 17) | 46.01 | 58.08 | 50.06 | 44 |

All33 is an availability supplement, not the controlled main ablation. Historical SAM has 19 available devices, Ours has 30; shared17 pairs use exactly the same device availability and retain all 23 queries / 44 views, including zero predictions. Historical observation supervision differs (SAM 91 real object-views; SAGA shared74 real/virtual scene views plus frozen prompts); not an equal-observation training ablation.
