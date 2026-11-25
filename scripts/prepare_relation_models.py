#!/usr/bin/env python3
import json,pathlib,hashlib
import requests,open_clip
from huggingface_hub import snapshot_download
ROOT=pathlib.Path(__file__).resolve().parents[1]
repo='jinaai/jina-embeddings-v3'
meta=requests.get('https://huggingface.co/api/models/'+repo,timeout=60);meta.raise_for_status();meta=meta.json()
(ROOT/'references/jina_model_listing.json').write_text(json.dumps(meta,indent=2))
revision='ab036b023d30b4d1138c4c3bfa9f0c445ab455d6'  # Verified baseline revision, independent of later HF updates.
path=snapshot_download(repo,revision=revision,cache_dir=ROOT/'models/huggingface/hub',allow_patterns=['*.json','*.py','*.safetensors','*.txt','*.model'],ignore_patterns=['onnx/*','coreml/*'])
manifest={'jina_repo':repo,'jina_revision':revision,'jina_snapshot':path,'task':'text-matching','truncate_dim':512,'jina_code_repo':'jinaai/xlm-roberta-flash-implementation','jina_code_revision':'bd55a5ec8e6c0fb1d6c26efb4b6a4a74ce8a88d3'}
(ROOT/'models/relags/jina_model.json').write_text(json.dumps(manifest,indent=2))
cfg=open_clip.get_pretrained_cfg('ViT-L-14-336','openai')
weights=open_clip.pretrained.download_pretrained(cfg,cache_dir=str(ROOT/'models/openclip_text'))
h=hashlib.sha256()
with open(weights,'rb') as f:
    for b in iter(lambda:f.read(8388608),b''):h.update(b)
(ROOT/'models/relags/clip_l14_model.json').write_text(json.dumps({'model':'ViT-L-14-336','pretrained':'openai','config':cfg,'path':weights,'sha256':h.hexdigest()},indent=2))
print(json.dumps(manifest));print(weights)
