"""Inference-only interface to the exact Jina encoding used by the official training dataset module."""
import json,pathlib
import torch
import torch.nn.functional as F
from transformers import AutoModel
ROOT=pathlib.Path(__file__).resolve().parents[1]
def load_relationship_embeddings(names,keep_model=False):
    cfg=json.loads((ROOT/'models/relags/jina_model.json').read_text())
    cache=ROOT/'models/relags/relationship_jina_features.pt'
    cached=None
    if cache.exists():
        cached=torch.load(cache,map_location='cpu')
        if cached['names']!=names or cached['revision']!=cfg['jina_revision']:cached=None
    encoder=None
    if cached is None or keep_model:
        model=AutoModel.from_pretrained(cfg['jina_snapshot'],trust_remote_code=True,code_revision=cfg['jina_code_revision']).to(torch.bfloat16).cuda()
        encoder=lambda x:model.encode(x,task='text-matching',truncate_dim=512)
    if cached is None:
        features=F.normalize(torch.from_numpy(encoder(names)),dim=1,p=2)
        cached={'names':names,'features':features.cpu(),'revision':cfg['jina_revision'],'task':'text-matching','truncate_dim':512}
        torch.save(cached,cache)
    return cached['features'],encoder
