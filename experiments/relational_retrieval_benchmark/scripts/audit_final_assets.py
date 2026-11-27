from common import *
import torch
paths=[ROOT/'outputs/thgs/model/sai_nag.pt',ROOT/'outputs/relags/model/jina_edges_predicted.pt',PROJECT/'models/relags/graph_transformer_512_80.pth',PROJECT/'models/openclip_text/ViT-L-14-336px.pt',PROJECT/'models/openclip_vit_b16/open_clip_pytorch_model.bin']
nag=torch.load(paths[0],map_location='cpu');assert all(torch.isfinite(f).all() for f in nag['nag_feat'])
stats=dict(gaussians=len(nag['nag'][0]),level_cluster_counts=[len(torch.unique(v)) for v in nag['nag']],feature_shapes=[list(v.shape) for v in nag['nag_feat']],all_semantic_features_finite=True,zero_feature_nodes=[int((v.norm(dim=-1)==0).sum()) for v in nag['nag_feat']],source='Actual official THGS output, no ReLaGS hierarchy reused')
write(ROOT/'inputs/generated_assets.json',dict(sha256={str(path):sha(path) for path in paths},thgs_statistics=stats,offline_reproducibility_note='Official merge_proj Scene shuffling has no explicit seed. This actual output is frozen by hash; offline rebuilding may vary. Queries and projection timings use the frozen artifact.'))
print(stats)
