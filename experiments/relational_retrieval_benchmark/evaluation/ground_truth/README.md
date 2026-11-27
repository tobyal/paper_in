# Independent manual ground truth (currently pending)

For each frozen query and camera, supply `Q001/frame_000329.png` (938×528, 0/255) and a same-stem JSON record:

```json
{"status":"confirmed","source":"independent_manual_annotation","reviewer":"human reviewer name","target_visible":true,"correct_target_ids":[],"notes":"Manual verification of target, anchor and industrial-frame relation"}
```

The mask is the visible union of all correct target instances, with real scene occlusion. Confirm target identities and relation independently before drawing pixels. Correct targets unavailable in Ours still belong in GT. Do not substitute M0 boxes, SAM masks, or method predictions. Optional `ignore_mask` names a binary PNG in the query directory; white pixels are excluded. Keep provenance and an annotation date.

Run `python scripts/evaluate_metrics.py` in the benchmark environment. Each view is averaged within its query, then queries receive equal weight. Empty predictions on visible GT score zero. Missing predictions are unavailable, not successful empty predictions. Unconfirmed or non-visible target views remain unevaluated. The script refuses mismatched sizes and nonbinary masks. The frozen query list defines the requested views; no predictions may affect annotation selection.
