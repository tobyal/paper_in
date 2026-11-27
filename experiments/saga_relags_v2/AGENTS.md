# SAGA + ReLaGS v2

- The complete v2 user request in docs/USER_REQUEST.md governs this independent experiment.
- Keep v1, original M0 r29, source 3DGS and old modules/results read-only. New writes stay in this directory.
- Freeze v1 iteration_10000; no new SAGA training. Preserve original Gaussian row IDs and geometry.
- Process all 33 objects. Reuse the 9 previously usable instances initially; record conflicts separately.
- Train-split views may supply new prompts. The 44 held-out images must never influence prompts, scales, thresholds or instance revisions.
- Separate reconstruction status, extraction status, automatic checks, Codex visual review and independent human truth.
- Query all 33 equipment nodes before considering instance availability. Never substitute another equipment item to obtain a renderable result.
- Preserve actual failures and bounded unsuccessful comparisons. Do not upload industrial images or use external visual services.
- No changes to old modules or automatic Git publishing in this task.
