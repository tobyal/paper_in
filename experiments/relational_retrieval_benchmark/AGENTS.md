# Industrial relational retrieval benchmark

- USER_REQUEST.md governs this comparison of exactly LangSplat, THGS, ReLaGS and frozen v2 Ours.
- All new writes stay here. Existing experiments, paper_eli, M0, weights, environments and source trees are read-only.
- External methods receive no device boxes, IDs, masks or graph from M0; only shared images/cameras and documented global coordinate calibration when needed.
- Reuse existing trained assets; do not redesign external query algorithms or tune on results.
- Freeze class/relation mapping, queries and evaluation cameras before batch queries. No numbered anchors.
- Preserve empty/error/unavailable states separately. No independent masks: metrics Pending GT.
- Use native full-scene occlusion compositing. Preserve all raw predictions and real timings.
- Keep scientific data private except explicitly requested local processing and key Git result figures.

## User-authorized pseudo-GT extension

- The user subsequently requested SAM-assisted Pseudo-GT evaluation. Actual pseudo-reference metrics are in evaluation/metrics/summary.json and QUANTITATIVE_EVALUATION_REPORT.md; only independent human-GT metrics remain pending.
- Existing model predictions and configs stay frozen. Reference generation must never use any method's predicted masks or copy Ours query results as target truth.
- evaluation/pseudo_ground_truth/REFERENCE_FROZEN.json locks the visually reviewed reference and common exclusions before scoring. Do not alter it to improve a method's metrics.
- Codex visual review is not human certification. Preserve failed SAM attempts and unreliable samples. All methods use the same accepted sample set.
