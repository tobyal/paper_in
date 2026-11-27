"""Lightweight review/archive; all scientific full outputs remain authoritative."""
from common import *
import os,shutil,tarfile,re
assert read(ROOT/'source_data/final_validation.json')['status']=='passed'
dest=ROOT/'git_review/experiments/paper_final_experiments';dest.mkdir(parents=True,exist_ok=True)
def included(p):
    rel=p.relative_to(ROOT);parts=rel.parts
    if parts[0] in ['git_review','cache','review'] or p.is_symlink():return False
    if p.suffix.lower() in ['.md','.json','.csv','.tsv','.tex']:return True
    if parts[0]=='scripts' and p.suffix=='.py':return True
    if parts[0]=='logs' and p.name=='run.log':return True
    if p.suffix.lower() not in ['.png','.jpg','.svg']:return False
    if parts[0] in ['figures','method_figure_assets']:return True
    if 'gallery' in parts:return True
    if p.name in ['mask.png','reference_mask.png']:return True
    if parts[0]=='E03_entity_construction' and (p.name in ['original_crop.png','coarse_oblique.png','affinity_oblique.png','refined_oblique.png','refined_side.png','removed_oblique.png','threshold_oblique.png'] or p.name=='crop.png'):return True
    if parts[0]=='E04_relation_retrieval' and p.name in ['frame_000329_instances.png','oblique_colored.png','top_colored.png']:return True
    if parts[0]=='E05_multiview_application' and p.name in ['scene.png','highlight.png','isolated.png']:return True
    return False
paths=[]
for folder,dirs,files in os.walk(ROOT):
    dirs[:]=[d for d in dirs if d not in ['git_review','cache','review','__pycache__']]
    for name in files:
        p=Path(folder)/name
        if included(p):paths.append(p)
manifest=[]
for p in sorted(paths):
    rel=p.relative_to(ROOT);q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);manifest.append(dict(path=str(rel),bytes=p.stat().st_size,sha256=sha(p)))
write(dest/'ARCHIVE_MANIFEST.json',manifest)
large=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size) for p in ROOT.rglob('*') if p.is_file() and 'git_review' not in p.parts and 'cache' not in p.parts and p.suffix in ['.npy','.npz','.ply','.pt','.pth']]
write(dest/'SERVER_ARRAYS.json',dict(authoritative_root=str(ROOT),files=large,external_models=read(ROOT/'configs/FROZEN.json')))
(dest/'ARCHIVE.md').write_text('''# Archive scope

This directory contains code, frozen configuration, reports, PNG/SVG paper figures, editable text/layout metadata, standalone panels, all 25-query external and ablation boards, binary masks, and lightweight intermediate records.

The authoritative server directory is `/mnt/sda/ubuntu/lkx/papers/paper_in/experiments/paper_final_experiments`. Full response/affinity/XYZ/index arrays, all native rendering assets, original RGB human-review packages and model weights remain there or at the explicit v1/v2/benchmark references. See SERVER_ARRAYS.json and configs/FROZEN.json. No new training was performed.

The human_review folder in this archive contains masks and prompts/metadata; its original RGB and full overlays are server-local. Formal figure panels and complete query boards provide the viewable reference comparisons here. CSV/TSV/LaTeX values are generated from actual saved binary predictions. SAM-assisted references are not independent human ground truth.

Verify byte hashes against ARCHIVE_MANIFEST.json. The publication repository preserves archive bytes via .gitattributes. Reproduction requires the authoritative read-only dependencies; this is not a self-contained model/data release.
''')
archive=ROOT/'review_bundle.tar.gz'
with tarfile.open(archive,'w:gz') as t:
    for p in sorted(dest.rglob('*')):
        if p.is_file():t.add(p,arcname=str(p.relative_to(dest.parent.parent)))
print(json.dumps(dict(files=len(manifest),bytes=sum(r['bytes'] for r in manifest),bundle_bytes=archive.stat().st_size,largest=max(manifest,key=lambda r:r['bytes']),destination=str(dest)),indent=2),flush=True)
