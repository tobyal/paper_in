# Baseline assets and reuse

All original assets are read-only. New writes are confined to this benchmark.

| Asset | Actual source |
|---|---|
| langsplat_source | /mnt/sda/ubuntu/lkx/papers/paper_eli/repos/LangSplat |
| langsplat_python | /mnt/sda/ubuntu/lkx/papers/paper_eli/envs/gsle_langsplat/bin/python |
| langsplat_models | /mnt/sda/ubuntu/lkx/papers/paper_eli/outputs/gsle/langsplat_1/chkpnt30000.pth<br>/mnt/sda/ubuntu/lkx/papers/paper_eli/outputs/gsle/langsplat_2/chkpnt30000.pth<br>/mnt/sda/ubuntu/lkx/papers/paper_eli/outputs/gsle/langsplat_3/chkpnt30000.pth |
| autoencoder | /mnt/sda/ubuntu/lkx/papers/paper_eli/repos/LangSplat/autoencoder/ckpt/industrial_gsle/best_ckpt.pth |
| language_features | /mnt/sda/ubuntu/lkx/papers/paper_eli/data/gsle_langsplat/language_features |
| relags_source | /mnt/sda/ubuntu/lkx/papers/paper_in/ReLaGS |
| relags_python | /mnt/sda/ubuntu/lkx/papers/paper_in/envs/relags/bin/python |
| relags_graph | /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_obb_repair_r1/08_scene_graph/data/model |
| relags_scene | /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/05_hierarchical_grouping/data/model |
| thgs_source | /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/relational_retrieval_benchmark/third_party/THGS |
| thgs_base_scene | /mnt/sda/ubuntu/lkx/papers/paper_in/outputs/relags_baseline/01_gaussian_scene/data/model |
| ours | /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v2/world_model |
| ours_python | /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v1/envs/saga/bin/python |
| native_ply | /mnt/sda/ubuntu/lkx/papers/paper_in/data/gaussian_scene/original_3dgs/point_cloud/iteration_30000/point_cloud.ply |
| clip_b16 | /mnt/sda/ubuntu/lkx/papers/paper_in/models/openclip_vit_b16/open_clip_pytorch_model.bin |

## Source revisions

- langsplat_source: `d70edb86df0fcbda19dc0d9739a3e5140a5e65fc`
- relags_source: `52cc0c98b0ccf9afebea31901bf79246650286b3`
- thgs_source: `c6423453fc7aa74772ca8883961ed696121b039c`

Actual pre-existing source changes and new THGS compatibility changes are retained in `docs/patches/`. Asset SHA-256 values are in `inputs/assets.json`. Existing R1 instrumentation/OBB fixes are retained; official query defaults are unchanged.

Validation: 44,930 existing files unchanged by size/mtime; all 9 critical model/config hashes unchanged.

THGS environment: isolated `envs/thgs` with read-only base `envs/relags` packages; official THGS CUDA rasterizer and graph extensions compiled in this benchmark. PyG `Data.keys` → `Data.keys()` is an API compatibility fix. Compilation temp files use `cache/tmp` after `/tmp` exhaustion.

Large outputs stay on the server: `outputs/*/Q*/gaussian_indices.npy`, `selected_gaussians.ply`, `raw_query.pt`, per-view `response.npz`, LangSplat `all_levels.npz`, THGS graph/hierarchy tensors, ReLaGS coordinate-alignment audit tensors, and native model/data references. They are excluded from the Git review bundle.
