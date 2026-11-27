"""Copy only the review archive into the existing server publication repository."""
from common import *
import shutil,subprocess,re
repo=PROJECT/'publication/repository';source=ROOT/'git_review/experiments/paper_final_experiments';target=repo/'experiments/paper_final_experiments'
assert subprocess.run(['git','-C',str(repo),'status','--porcelain'],capture_output=True,text=True,check=True).stdout.strip()==''
assert not target.exists(),'Do not overwrite a previous archived experiment'
manifest=read(source/'ARCHIVE_MANIFEST.json')
for row in manifest:assert sha(source/row['path'])==row['sha256']
for p in source.rglob('*'):
    if not p.is_file():continue
    assert p.suffix not in ['.pt','.pth','.npy','.npz','.ply','.ckpt','.safetensors']
    assert p.stat().st_size<50_000_000
    if p.suffix in ['.py','.md','.json','.csv','.tex','.log']:
        text=p.read_text(errors='replace');assert not re.search(r'(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)',text),str(p)
shutil.copytree(source,target)
readme=repo/'README.md';body=readme.read_text();anchor='## External comparison: SAM-assisted Pseudo-GT evaluation'
section='''## Paper experiments: controlled ablations and publication figures

The [paper experiment package](experiments/paper_final_experiments/README.md) completes E01—E06 with six PNG/SVG paper figures, four principal quantitative tables, 350 ablation/supplement masks, full 25-query comparison galleries and real affinity/relationship traces.

| Configuration | mIoU | Precision | Recall |
|---|---:|---:|---:|
| Box-based (same availability) | 62.95% | 70.33% | 83.72% |
| Ours w/o Relation | 46.52% | 59.18% | 70.54% |
| Ours | 63.70% | 84.33% | 70.21% |

On the same 23-query / 44-view **SAM-assisted reference**, relations add 17.18 percentage points mIoU. Fine extraction improves Precision but sacrifices Recall, with only 0.75 points mIoU gain over gated coarse boxes. The separate all-33 coarse-box supplement reaches 68.07% mIoU; instance availability remains a material limitation. These are not independent human-GT results.

[F04—F09 gallery](experiments/paper_final_experiments/docs/GALLERY.md) · [Full experiment report](experiments/paper_final_experiments/EXPERIMENT_REPORT.md) · [Tables and figure index](experiments/paper_final_experiments/FIGURE_INDEX.md). Existing v2 and benchmark results are preserved; ReLaGS indexing and all 50 projections were checked without changing predictions. Large arrays and models stay on the server.

'''
assert anchor in body;readme.write_text(body.replace(anchor,section+anchor,1))
attributes=repo/'.gitattributes';content=attributes.read_text();line='experiments/paper_final_experiments/** -text !eol'
if line not in content:attributes.write_text(content+'\n'+line+'\n')
print('Prepared',len(manifest),'manifested files in',target,flush=True)
