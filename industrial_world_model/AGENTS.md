# Industrial world model, first implementation

- The 2026-11-26 user request defines this separate M1–M5 method. It supersedes the old requirement to execute unchanged ReLaGS for this new experiment only.
- Read the immutable M0 input snapshot. Do not change M0, paper_eli, native source PLY, Baseline 0, R1, or their outputs.
- Run GPU work remotely in the existing compatible environment, on the explicitly configured GPU. Never stop shared jobs.
- Reuse only original RGB/cameras/split/native 3DGS and generic SAM/CLIP weights. Generate all masks, associations, features and relations afresh.
- Keep original Gaussian row IDs, object IDs and image IDs. Unknown/occluded observations are not negative votes; invalid upstream objects stay unavailable.
- This method uses no MWP, 2DGS, Superpoints, THGS, OpenSeg or GNN. Save all submodule diagnostics, failures, parameters and commands.
- Internal reprojection consistency and cosine similarities are not ground-truth accuracy or probabilities.
- Publish code/config/docs only, never annotations, model weights, raw data, logs or experiment artifacts.
