# M0 v2 development boundary

- Read README.md and docs/REQUIREMENTS_V2.zh.md. The user-approved v2 requirements supersede the original seven-step workflow.
- The 2026-11-26 user request supersedes the AABB-only device editor: Step 02 is one 3D viewport with movable/scalable/rotatable OBBs, per-object visibility and atomic save-all. Preserve the already-confirmed Step 01 and every pending user draft.
- The server project is authoritative. Preserve Baseline 0/R1, original Gaussian files, paper_eli, the complete V1 backup, and industrial_scene_prior/.
- V2 uses industrial_scene_prior_v2/. Never promote V1 drafts or old ReLaGS semantic/spatial outputs to V2 priors.
- Only RGB, COLMAP, original 306/44 split, base 2DGS/MWP geometry, official renderer and generic SAM weights may be inherited.
- M0 ends at scene extent, coarse object boxes, basic bilingual descriptions and an optional single training-reference mask. No final object indices, multi-view fusion, semantic features, relation computation, scene graph or evaluation tasks.
- Do not restore old anchor_image_id, region, multi-view-mask or seven-step requirements in validation.
- Every coordinate is in SfM relative units, with a right-handed frame and explicit version. Bind scene indices to original PLY hash and vertex order.
- Treat automatic coordinate/plane estimates and Codex descriptions as candidates. Test confirmations belong only to isolated logs/m0_v2_contract_* directories, never production.
- GPU work runs remotely; own service is paper-in-m0 on loopback 28760, default GPU 3. Do not stop other users' jobs.
- Preserve original SAM candidates, native pixel masks, edits, drafts, revisions and frozen versions. Publish code/docs only; exclude all datasets, images, annotations, backups, SQLite, logs and screenshots.
