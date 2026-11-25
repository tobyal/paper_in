#!/usr/bin/env python3
"""Remove only verified copies made by our migration that were over-inclusive."""
import json,pathlib,hashlib,csv
ROOT=pathlib.Path(__file__).resolve().parents[1]
S=ROOT/'outputs/relags_baseline/00_data_check'
manifest=json.loads((S/'data/migration_manifest.json').read_text())
kept=[];removed=[]
for r in manifest:
    p=pathlib.Path(r['destination'])
    d=pathlib.Path(r['relative_destination'])
    excluded=d.parts[:3]==('previous_work','paper','discovered') and any(x in d.parts[3:] for x in ['backups','_history','alternatives','tools','outputs','records'])
    if not excluded: kept.append(r); continue
    assert p.resolve().is_relative_to(ROOT/'previous_work/paper/discovered')
    assert p.resolve()!=pathlib.Path(r['source']).resolve() and not p.is_symlink()
    if p.exists():
        assert hashlib.sha256(p.read_bytes()).hexdigest()==r['sha256']
        p.unlink()
    removed.append(r)
(S/'data/excluded_duplicate_copies.json').write_text(json.dumps(removed,indent=2,ensure_ascii=False))
(S/'data/migration_manifest.json').write_text(json.dumps(kept,indent=2,ensure_ascii=False))
with (ROOT/'DATA_MIGRATION.tsv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(kept[0]),delimiter='\t'); w.writeheader(); w.writerows(kept)
summary=json.loads((S/'metrics/migration_summary.json').read_text())
summary.update(files_copied=len(kept),bytes_copied=sum(x['bytes'] for x in kept),excluded_duplicate_copies=len(removed),paper_files_retained=[r['relative_destination'] for r in kept if r['relative_destination'].startswith('previous_work/paper/discovered/')])
for p in [S/'metrics/migration_summary.json',S/'status.json']: p.write_text(json.dumps(summary,indent=2,ensure_ascii=False))
with (ROOT/'DATA_MIGRATION.md').open('a') as f: f.write('\n## 迁移范围复核\n\n最终保留 '+str(len(kept))+' 个文件，'+str(sum(x['bytes'] for x in kept))+' 字节。自动发现的旧图备份、重复历史输出和 Blender 资源已从本次副本中排除；仅删除本脚本拥有且哈希一致的目标副本，源工程仍未写入。逐项排除记录：`00_data_check/data/excluded_duplicate_copies.json`。完整历史发现清单继续保留用于审计。\n')
print(json.dumps({k:summary[k] for k in ['files_copied','bytes_copied','excluded_duplicate_copies']}))
