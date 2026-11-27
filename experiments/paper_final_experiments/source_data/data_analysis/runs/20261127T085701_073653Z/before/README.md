# Paper final experiments: industrial relational instance retrieval

实际完成 E01—E06。冻结 v2 / 25 queries / SAM-assisted Pseudo-GT；主指标23查询、44视角。

优先看 [正式图集](docs/GALLERY.md)、[实验报告](EXPERIMENT_REPORT.md)、[图表索引](FIGURE_INDEX.md)。

实测 mIoU：Box-based 62.95%，w/o Relation 46.52%，Ours 63.70%。精细提取主要提高Precision，明显损失Recall；允许33粗框输出时68.07%，作为可用性补充单列。外部方法旧数值独立重算一致。ReLaGS50次重渲染一致，未发现索引或坐标错误。

## Re-run on the authoritative server

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/paper_final_experiments
export PYTHONDONTWRITEBYTECODE=1
PY=../saga_relags_v1/envs/saga/bin/python
$PY scripts/run_stage.py E02 $PY scripts/ablation.py
$PY scripts/run_stage.py SAM_supplement $PY scripts/sam_supplement.py
$PY scripts/run_stage.py evaluate $PY scripts/evaluate.py
$PY scripts/run_stage.py E03 $PY scripts/export_entities.py
$PY scripts/run_stage.py E04_E05 $PY scripts/export_applications.py
$PY scripts/run_stage.py nearest_display $PY scripts/refine_nearest_display.py
$PY scripts/run_stage.py E06 $PY scripts/efficiency.py
$PY scripts/run_stage.py figures $PY scripts/plot_figures.py
$PY scripts/run_stage.py publish $PY scripts/publish.py
$PY scripts/run_stage.py validate $PY scripts/validate.py
```

ReLaGS audit uses `../../envs/relags/bin/python scripts/audit_relags.py` through run_stage.py. Initialization is one-shot; do not overwrite configs/FROZEN.json. Prediction scripts resume by completed result.json. New scientific changes should use another version, not overwrite frozen v2 or benchmark.

Independent human GT does not yet exist. The 50-sample RGB/reference-only review package stays under E01_external_comparison/human_review. Formal figures use English labels, editable SVG text, and configs/captions.json for bilingual captions; layout/source metadata is per figure.

Models, PLY, response/affinity arrays and full renders remain on the server. Git archive contains code/configs/reports/tables/figure assets and lightweight masks/metadata only. Server references and SHA256 are recorded, and v1/v2/benchmark are read-only dependencies.

<!-- DATA_ANALYSIS_F10_F12_START -->
## Frozen-data analysis (F10-F12)

[Figures and captions](docs/GALLERY.md) · [Index](FIGURE_INDEX.md) · [Exact plotting data](source_data/data_analysis/)

```bash
../saga_relags_v1/envs/saga/bin/python scripts/plot_data_analysis.py --figure all
# Individual figures: --figure F10, --figure F11, or --figure F12
```

CPU-only analysis of frozen CSV/JSON, with no model or query execution. Run this script after legacy plot_figures.py/publish.py if rebuilding documentation, because the legacy generators recreate their six-figure index. Preserve the scientific outputs; new method experiments belong in a separate version.
<!-- DATA_ANALYSIS_F10_F12_END -->
