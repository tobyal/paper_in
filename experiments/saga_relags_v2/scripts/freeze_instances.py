"""Freeze actual all-object extraction before any held-out visualization."""
from pathlib import Path
import sys,datetime,collections
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
quality=read(ROOT/'configs/quality_review.json');reviews={r['object_id']:r for r in quality['objects']}
folder=ROOT/'outputs/A/extractions/refined';summary=read(folder/'summary.json');objects={o['object_id']:o for o in read(ROOT/'inputs/objects.json')}
assert len(reviews)==len(summary['objects'])==33
old={r['object_id']:r for r in read(existing_instances()/'summary.json')['objects']};frozen=[];comparisons=[]
refs=read(ROOT/'outputs/A/refinement_prompts/records.json');oldrefs=read(V1/'outputs/A/reference_prompts/records.json')
for row in summary['objects']:
    oid=row['object_id'];review=dict(reviews[oid]);review['fine_instance_available']=review['extraction_status'] in ['usable','partial_usable'] and row['gaussian_count']>0
    prompt=read(folder/'objects'/oid/'prompt.json');real=virtual=0
    for p in prompt['prompts']:
        source=p.get('source_type',p['camera'].get('source_type','real'));real+=source=='real';virtual+=source!='real'
    row.update(review,effective_real_views=real,effective_virtual_views=virtual,extra_optimization=review.get('extra_optimization',False),quality_reviewer='Codex visual inspection')
    indices=ROOT/row['gaussian_indices'];ids=np.load(indices);frozen.append(dict(object_id=oid,indices=row['gaussian_indices'],sha256=sha(indices),ply=row['ply'],ply_sha256=sha(ROOT/row['ply']),fine_instance_available=review['fine_instance_available']))
    if oid in old:
        previous=np.load(V1/old[oid]['gaussian_indices']);same=np.array_equal(ids,previous)
        if row['reused_v1']:assert same,oid
        comparisons.append(dict(object_id=oid,reused_v1=row['reused_v1'],same_original_ids=same,v1_count=len(previous),v2_count=len(ids),removed=len(np.setdiff1d(previous,ids)),added=len(np.setdiff1d(ids,previous))))
write(folder/'quality_review.json',quality);write(ROOT/'outputs/A/final_summary.json',summary)
write(ROOT/'outputs/A/v1_comparison.json',comparisons)
write(ROOT/'outputs/A/frozen_manifest.json',dict(frozen_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source_extraction='outputs/A/extractions/refined',objects=frozen,threshold=.85,gate_rule='unchanged v1',heldout_used_for_selection=False,status_counts=dict(collections.Counter(r['extraction_status'] for r in summary['objects']))))
print('FROZEN',collections.Counter(r['extraction_status'] for r in summary['objects']))
