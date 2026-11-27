"""Freeze existing predictions before pseudo-reference work; verify without changing them."""
from common import *
import argparse,datetime
p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true');a=p.parse_args();dest=ROOT/'evaluation/pseudo_ground_truth/predictions_before.json';check_frozen()
if not a.verify:
    assert not dest.exists(),'Snapshot already exists'
    files=[p for m in ['langsplat','thgs','relags','ours'] for p in (ROOT/'outputs'/m).glob('Q*/*') if p.is_file() and p.name=='result.json']
    files += [p for m in ['langsplat','thgs','relags','ours'] for p in (ROOT/'outputs'/m).glob('Q*/*/*') if p.is_file() and p.name in ['mask.png','response.npz','camera.json','all_levels.npz']]
    write(dest,dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
    print('FROZEN PREDICTIONS',len(files))
else:
    original=read(dest)['sha256'];changed=[p for p,h in original.items() if sha(ROOT/p)!=h];write(ROOT/'evaluation/metrics/pseudo_prediction_preservation.json',dict(checked_files=len(original),changed=changed,original_configuration_hashes_valid=True));assert not changed;print('PREDICTIONS UNCHANGED',len(original))
