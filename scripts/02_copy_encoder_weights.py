#!/usr/bin/env python3
"""Copy only exact pretrained encoder weights, never prior image semantics."""
import pathlib,hashlib,shutil,json,csv
ROOT=pathlib.Path(__file__).resolve().parents[1]
SRC=pathlib.Path('/mnt/sda/ubuntu/lkx/papers/paper_eli')
S=ROOT/'outputs/relags_baseline/00_data_check'
manifest=json.loads((S/'data/migration_manifest.json').read_text())
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8388608),b''): h.update(b)
    return h.hexdigest()
def copy(s,d,purpose):
    d.parent.mkdir(parents=True,exist_ok=True);h=digest(s)
    if not d.exists() or digest(d)!=h:shutil.copy2(s,d,follow_symlinks=True)
    assert digest(d)==h and not d.is_symlink()
    r={'source':str(s),'resolved_source':str(s.resolve()),'destination':str(d),'relative_destination':str(d.relative_to(ROOT)),'bytes':d.stat().st_size,'sha256':h,'purpose':purpose,'reference_only':False,'source_unchanged_size_mtime':True}
    if not any(x['destination']==str(d) for x in manifest):manifest.append(r)
    print('VERIFIED',d,h,flush=True)
copy(SRC/'models/torch/hub/checkpoints/sam_vit_h_4b8939.pth',ROOT/'models/sam/sam_vit_h_4b8939.pth','Original pretrained Meta SAM ViT-H encoder weights; rerun segmentation from RGB')
snapshot=pathlib.Path('models/huggingface/hub/models--laion--CLIP-ViT-B-16-laion2B-s34B-b88K/snapshots/7288da5a0d6f0b51c4a2b27c624837a9236d0112')
for s in sorted((SRC/snapshot).rglob('*')):
    if s.is_file():copy(s,ROOT/'models/openclip_vit_b16'/s.relative_to(SRC/snapshot),'Exact pretrained OpenCLIP ViT-B16 laion2B-s34B-b88K snapshot; no scene features reused')
(S/'data/migration_manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False))
with (ROOT/'DATA_MIGRATION.tsv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(manifest[0]),delimiter='\t');w.writeheader();w.writerows(manifest)
with (ROOT/'DATA_MIGRATION.md').open('a') as f:f.write('\n## 预训练编码器\n\n仅额外复制官方 SAM ViT-H 权重与 OpenCLIP ViT-B/16 laion2B-s34B-b88K 原始快照。权重逐文件校验；所有工业图像的分割与特征仍须重新计算，没有复制旧场景的语义结果。完整路径与哈希已加入 TSV。\n')
