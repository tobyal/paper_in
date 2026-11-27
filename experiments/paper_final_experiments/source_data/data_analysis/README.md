# F10-F12 frozen-data analysis

Read-only analysis of eight saved CSV/JSON sources from E01, E02 and E04. No GPU, models, new queries, mask generation, threshold tuning or experimental reruns.

- `statistics.json`: exact means, quartiles, sign counts, winner IDs and candidate totals.
- `F10_*.csv`, `F11_*.csv`, `F12_*.csv`: actual plot inputs, including horizontal jitter coordinates and full-precision numbers.
- `validation.json`: source locks, historical/current file protection, previous figure hashes, PDF/SVG/PNG structure and links.
- `visual_review.json`: final artifact hashes and Codex visual inspection, not human GT certification.
- `runs/`: commands, exact script snapshots (server), timing/logs, protected-file snapshots and documentation backups.
- `integration_before/`: server copies of pre-change archive/validation scripts.

From the authoritative experiment directory:

```bash
PYTHONDONTWRITEBYTECODE=1 ../saga_relags_v1/envs/saga/bin/python scripts/plot_data_analysis.py --figure all
PYTHONDONTWRITEBYTECODE=1 ../saga_relags_v1/envs/saga/bin/python scripts/validate_data_analysis.py
```

Use `--figure F10`, `--figure F11`, or `--figure F12` to regenerate one figure. Inspect new artifacts again before archiving; visual review hashes identify the reviewed revision. Source records use authoritative absolute server paths. Reproduction needs the existing read-only experiment inputs; drawing itself imports only NumPy/Matplotlib and the standard library.

F10/F11 use 23 evaluated queries (44 eligible views), with views averaged within query before an equal query mean. Q005/Q025 are missing-reference N/A, not zero. The 25-query heatmap still displays them. F12 uses all 25 queries and counts query-device occurrences (108/39/35), not unique equipment (33/27/25). Queries can share equipment/views, so no significance tests are used.

References are SAM-assisted Pseudo-GT, not independently human-verified. The all-33 box configuration has a different availability condition and cannot be interpreted as a single-mechanism ablation. Relation filtering and fine-output availability are distinct from accuracy.
