# Paper final experiments

- Follow docs/USER_REQUEST.md. This directory holds supplemental experiments and paper assets, not a new method version.
- Frozen saga_relags_v1/v2, M0 r29, native 3DGS and relational_retrieval_benchmark are read-only dependencies.
- Keep the 25 queries, 50 fixed views, and the 23-query / 44-view SAM-assisted reference evaluation subset unchanged. Do not tune using scores.
- Main Box-based and Ours must share identical equipment availability. All-33 coarse boxes and shared-17 historical SAM comparisons are separate supplements.
- Images, scores, affinity, masks and geometry must come from saved actual data. Distinguish threshold selections, conflict assignment and final availability.
- SAM-assisted Pseudo-GT and Codex visual review are not independent human GT.
- Preserve all large arrays and source references on the server. Git contains lightweight data and figures only.
- Future method or reference changes require a new version. Do not overwrite frozen source outputs.
