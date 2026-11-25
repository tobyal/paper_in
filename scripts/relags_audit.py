"""Serialization-only hooks for unchanged official computation."""
import json,os,pathlib
import torch
ROOT=pathlib.Path(__file__).resolve().parents[1]
def cpu(value):
    if torch.is_tensor(value):return value.detach().cpu()
    if isinstance(value,dict):return {k:cpu(v) for k,v in value.items()}
    if isinstance(value,(list,tuple)):return [cpu(v) for v in value]
    return value
def save(stage,name,value):
    attempt=os.environ.get('RELAGS_ATTEMPT_ID','manual')
    base=ROOT/'outputs/relags_baseline'/stage/'data'/attempt
    base.mkdir(parents=True,exist_ok=True)
    p=base/(name+'.pt');torch.save(cpu(value),p)
    (base.parent/'audit_latest.json').write_text(json.dumps({'attempt':attempt,'directory':str(base)},indent=2))
