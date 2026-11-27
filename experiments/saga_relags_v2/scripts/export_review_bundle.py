"""Small code/report/evidence bundle; large industrial arrays remain on server."""
from pathlib import Path
import tarfile
ROOT=Path(__file__).resolve().parents[1]
files=[]
for pattern in ['*.md','src/*.py','scripts/*.py','configs/*.json','docs/*.md','docs/figures/*','inputs/provenance.json','outputs/A/final_summary.json','outputs/A/v1_comparison.json','outputs/A/frozen_manifest.json','outputs/B/*.json','outputs/C/*.json','outputs/D/*.json','outputs/validation/*.json','logs/*/*/*.json','logs/*/*/run.log','logs/*/*/gpu.csv']:
    files.extend(p for p in ROOT.glob(pattern) if p.is_file())
dest=ROOT/'review_bundle.tar.gz'
with tarfile.open(dest,'w:gz') as tar:
    for p in sorted(set(files)):tar.add(p,arcname=str(p.relative_to(ROOT)))
print(dest,len(set(files)),dest.stat().st_size)
