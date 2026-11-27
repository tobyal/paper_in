# SAM-assisted Pseudo-GT

Fresh SAM ViT-H masks from fixed original RGB, checked by Codex. **Not independent human ground truth.**

`target_audit.json`: separately recomputed M0 relation evidence; no Ours query output. `tasks.json` and `object_labels.json`: device/view IDs. `objects/Txxx/{initial,review1,review2,review3}`: actual SAM candidates, prompts and scores. `objects/Txxx/final/`: selected mask and quality review. `Qxxx/frame_xxxxxx/`: original RGB, union mask, overlay, camera, prompts and quality record. `REFERENCE_FROZEN.json`: lock created before first metric calculation.

44 accepted views / 23 queries; 6 unreliable views excluded for all four methods. Excluded masks are provisional inspection aids, not evaluation targets. Shared M0 target definitions and SAM errors limit interpretation. See the [report](../../QUANTITATIVE_EVALUATION_REPORT.md).
