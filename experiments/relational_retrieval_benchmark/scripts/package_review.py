"""Prepare a Git-sized review tree; never include weights, PLY or tensor arrays."""
from common import *
import shutil,tarfile
dest=ROOT/'git_review/experiments/relational_retrieval_benchmark';dest.mkdir(parents=True,exist_ok=True);selected=[]
for folder in ['scripts','configs','docs','evaluation/metrics','evaluation/ground_truth']:
    for path in (ROOT/folder).rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.py','.md','.json','.csv','.jpg','.png','.patch','.diff','.yml','.yaml'} and '__pycache__' not in path.parts:selected.append(path)
selected += [ROOT/name for name in ['README.md','EXPERIMENT_REPORT.md','EXPERIMENT_PROTOCOL.md','BASELINE_ASSETS.md','AGENTS.md']]
if (ROOT/'QUANTITATIVE_EVALUATION_REPORT.md').exists():
    selected.append(ROOT/'QUANTITATIVE_EVALUATION_REPORT.md')
    pseudo=ROOT/'evaluation/pseudo_ground_truth'
    selected += [p for p in pseudo.glob('*') if p.is_file() and p.suffix in {'.json','.md','.jpg'}]
    selected += list(pseudo.glob('Q*/*/mask.png'))+list(pseudo.glob('Q*/*/quality_check.json'))+list(pseudo.glob('Q*/*/sam_prompts.json'))+list(pseudo.glob('Q*/*/camera.json'))
    selected += list(pseudo.glob('objects/*/final/mask.png'))+list(pseudo.glob('objects/*/final/review.json'))
selected += [ROOT/'inputs'/name for name in ['assets.json','generated_assets.json','compatibility.json','split_usage_audit.json','query_selection_audit.json','langsplat_source_record.json','autoencoder_source_record.json','language_validation_source_record.json']]
for method in ['langsplat','thgs','relags','ours']:
    selected.append(ROOT/'outputs'/method/'summary.json')
    selected += list((ROOT/'outputs'/method).glob('Q*/result.json'))
selected += list((ROOT/'outputs/thgs/build').glob('*.json'))
selected += list((ROOT/'outputs/comparisons').glob('Q*/display_crops.json'))
selected += [ROOT/'outputs/comparisons/representative_cases.json',ROOT/'logs/metadata_corrections.json']
selected += list((ROOT/'logs').glob('*/*/command.json'))+list((ROOT/'logs').glob('*/*/result.json'))
manifest=[]
for source in sorted(set(selected)):
    if not source.exists():continue
    assert source.stat().st_size<25_000_000,source
    target=dest/source.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);manifest.append(dict(path=str(source.relative_to(ROOT)),bytes=source.stat().st_size,sha256=sha(source)))
write(dest/'REVIEW_MANIFEST.json',dict(files=manifest,total_bytes=sum(r['bytes'] for r in manifest),large_assets='Server-only; see BASELINE_ASSETS.md',publication='Prepared only; not pushed by this script'))
with tarfile.open(ROOT/'review_bundle.tar.gz','w:gz') as archive:
    for p in dest.rglob('*'):
        if p.is_file():archive.add(p,arcname=str(p.relative_to(ROOT/'git_review')))
print('REVIEW_BUNDLE',len(manifest),sum(r['bytes'] for r in manifest),(ROOT/'review_bundle.tar.gz').stat().st_size,flush=True)
