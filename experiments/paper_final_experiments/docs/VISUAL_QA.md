# Figure inspection

Codex inspected F04—F09 from the actual exported PNGs. This is figure/layout review, not independent human segmentation certification.

- F04: verified the real scene, equipment crops, 306/44 camera counts, 33 coarse spatial identities and category counts. Increased top margin and separated category labels. Held-out cameras use larger orange markers.
- F05: checked identical cameras and frame extent within each row, actual SAM reference/prediction overlays and single-view IoU. Included Q001 where external methods work, and Q019 where Ours is unavailable. All 25 two-view boards remain available.
- F06: cropped coarse, affinity and refined renderings using the same coarse-image bounds for each camera; this changes display only. Verified actual structures, fixed affinity colorbar, count labels and the O09 conflict-removal label. Source rendering blur and floating Gaussians remain visible.
- F07: checked shared device colors, correct industrial direction axes, the six-to-one Q006 filtering trace and reference-anchor union. Moved legends to avoid overlapping axis labels. Unavailable fine instances remain explicit spatial nodes.
- F08: increased row spacing after the initial query/header overlap. Retained Q011 where the coarse mask covers more reference structure than the refined result. No mask or threshold changes were made during layout review.
- F09: verified fixed Gaussian sets across three directions and actual full-scene occlusion. Initial nearest-display selection favored large clipped targets; changed illustrative camera ranking to prefer complete target/anchor boxes, preserving query results and all fixed evaluation cameras. Previous display choices and all new candidate-view statistics are saved. Verified complete N02 target/anchor display and labelled the unsuccessful blue-bin extraction as a diagnostic attempt.

The figures do not claim missing geometry has been reconstructed. Point/camera distributions, relation arrows and affinity colors correspond to stored values. The final automated validation independently checks source hashes, masks, camera records, ID consistency, direction differences, image dimensions, SVG parsing and gallery links.
