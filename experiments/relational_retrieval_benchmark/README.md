# Industrial relational retrieval benchmark

25 frozen category–relation–category queries; LangSplat, THGS, ReLaGS and frozen v2 Ours. Independent accuracy GT is pending.

- [Actual experiment report](EXPERIMENT_REPORT.md)
- [Complete qualitative gallery](docs/GALLERY.md)
- [Protocol and fairness conditions](EXPERIMENT_PROTOCOL.md)
- [Assets, versions and server paths](BASELINE_ASSETS.md)
- [Human GT interface](evaluation/ground_truth/README.md)

## Run on the existing server

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/relational_retrieval_benchmark
PYTHONDONTWRITEBYTECODE=1 ../../envs/relags/bin/python scripts/run_benchmark.py --method all --gpu 0
../../envs/relags/bin/python scripts/evaluate_metrics.py
../../envs/relags/bin/python scripts/generate_comparisons.py
../../envs/relags/bin/python scripts/finalize.py
```

`run_benchmark.py` resumes completed query records and offline THGS stages. It does not retrain models. Run individual adapters in their environment listed in inputs/assets.json; THGS uses envs/thgs. Failed run logs remain under logs/. Before regenerating predictions deliberately, use a new experiment directory rather than replacing this frozen benchmark.

Three-dimensional figures use `scripts/export_3d_views.py --method relags|thgs|ours` in the corresponding environment. Evaluation uses complete-scene contribution masks; isolated figures are display-only.

The light Git review bundle includes code/configs/reports/key images and raw numerical JSON. Large checkpoints, tensor arrays, PLY and caches remain on the server and are intentionally excluded. Official third-party code is identified by commit and actual patches, not vendored into the review bundle.

## SAM-assisted Pseudo-GT quantitative extension

Measured metrics are now available on 23 queries / 44 shared views. See [quantitative report](QUANTITATIVE_EVALUATION_REPORT.md) and [six-column gallery](docs/GALLERY.md). Run `scripts/evaluate_pseudo_metrics.py` and `scripts/publish_pseudo_evaluation.py` in the existing relags environment to regenerate these tables/figures. Original `evaluate_metrics.py` remains the separate human-GT interface; `finalize.py` documents the historical qualitative run and should not overwrite the updated reports.
