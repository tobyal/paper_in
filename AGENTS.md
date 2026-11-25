# ReLaGS industrial reproduction archive

- Read README.md, EXPERIMENT_REPORT.md and OBB_REPAIR_REPORT.md before changing the pipeline.
- Keep original Baseline 0 results and failure records immutable. New experiments use separate output directories.
- Preserve official grouping, ROFA, GNN and query rules unless a new experiment explicitly authorizes a method change.
- Never replace new semantic stages with historical LangSplat/SAM/localization/editing outputs.
- Record parameters, commands, raw intermediates, logs, timings and sampled GPU use. Do not equate nonempty queries with accuracy.
- Sources are pinned in UPSTREAM.lock.json; use scripts/bootstrap_sources.py and preserve upstream licenses.
- Environment snapshots contain historical paths, not portable pip requirements. Data and pretrained weights are not bundled.
