# Archive scope

This directory contains code, frozen configuration, reports, PNG/SVG/PDF paper figures, editable text/layout metadata, standalone panels, all 25-query external and ablation boards, binary masks, and lightweight intermediate records.

The authoritative server directory is `/mnt/sda/ubuntu/lkx/papers/paper_in/experiments/paper_final_experiments`. Full response/affinity/XYZ/index arrays, all native rendering assets, original RGB human-review packages and model weights remain there or at the explicit v1/v2/benchmark references. See SERVER_ARRAYS.json and configs/FROZEN.json. No new training was performed.

The human_review folder in this archive contains masks and prompts/metadata; its original RGB and full overlays are server-local. Formal figure panels and complete query boards provide the viewable reference comparisons here. CSV/TSV/LaTeX values are generated from actual saved binary predictions. SAM-assisted references are not independent human ground truth.

Verify byte hashes against ARCHIVE_MANIFEST.json. The publication repository preserves archive bytes via .gitattributes. Reproduction requires the authoritative read-only dependencies; this is not a self-contained model/data release.
