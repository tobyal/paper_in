# M0 development boundary

- Read README.md and docs/REQUIREMENTS.zh.md. The remote project is authoritative; preserve the earlier Baseline 0/R1 directories and the original paper_eli project.
- M0 inherits only RGB, COLMAP, original train/test split, base 2DGS/MWP geometry, renderer interfaces and generic SAM weights/environments. Never load legacy masks, language features, groups, semantic locations, relations, ground planes or regions as M0 inputs.
- Keep modeling priors and independent ground truth separate. Never turn an automated test or Codex candidate into a claimed human confirmation.
- Keep runtime data under industrial_scene_prior or an explicit isolated M0_DATA directory. Exclude datasets, masks, image caches, SQLite databases, logs and screenshots from source publication.
- Run GPU work only on the remote server. Own service: paper-in-m0; default GPU 3, loopback port 28760. Do not stop other users' jobs or services.
- Preserve native-resolution masks, original SAM candidates, edits, provenance, revision history and immutable frozen snapshots. Record failures honestly.
- M2–M5 algorithms are outside this platform's scope. Coarse ROI is only a search bound, never final Gaussian instance membership.
