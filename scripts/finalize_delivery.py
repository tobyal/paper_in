#!/usr/bin/env python3
"""Finalize documentation from verified results; never run or alter scientific stages."""
import collections
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'outputs/relags_baseline'
rows = json.loads((BASE / '00_data_check/data/migration_manifest.json').read_text())
audit = json.loads((BASE / '00_data_check/metrics/final_integrity.json').read_text())
assert all(audit['checks'].values()) and not audit['source_inventory_not_available_for']
groups = collections.defaultdict(list)
for row in rows:
    groups[row['purpose']].append(row)
labels = [
    '原始采集视频', '去畸变前的提取图像及完成标记', '去畸变 RGB：新流程直接输入',
    '去畸变 COLMAP 相机、位姿与点云', '原始 SfM 重建：溯源',
    '原始未编辑 3DGS PLY：兼容性和视觉参考', '原始最终检查点及模型元数据：归档',
    '采集、相机、划分及重建记录', '旧研究报告及场景描述：参考',
    '发现的旧论文图表和源文件：参考', '旧语义、定位和编辑记录：仅参考',
    '旧 LangSplat 地面估计：仅参考', '旧实验配置：仅参考', '旧预处理脚本：归档不执行',
    '旧实验比较预览：仅参考', '通用预训练 SAM ViT-H 权重', '通用预训练 OpenCLIP ViT-B/16 权重与配置',
]
assert len(groups) == len(labels)

def common_path(items, key, base):
    paths = [str(Path(x[key]).relative_to(base)) for x in items]
    return os.path.commonpath(paths) if len(paths) > 1 else paths[0]

table = ['| 内容与用途 | 文件数 | 字节数 | 源相对路径 | 目标相对路径 |', '|---|---:|---:|---|---|']
for label, (_, items) in zip(labels, groups.items()):
    src = common_path(items, 'source', '/mnt/sda/ubuntu/lkx/papers/paper_eli')
    dst = common_path(items, 'destination', ROOT)
    table.append(f'| {label} | {len(items)} | {sum(x["bytes"] for x in items):,} | `{src}` | `{dst}` |')
total = sum(x['bytes'] for x in rows)
text = f'''# Baseline 0 数据迁移记录

最终保留 **{len(rows)} 个物理复制文件，共 {total:,} 字节（{total / 2**30:.3f} GiB）**。该数字仅指从旧工程迁移的文件，不包含本次生成的中间结果、独立环境及新下载权重。

源工程：`/mnt/sda/ubuntu/lkx/papers/paper_eli`。目标工程：`/mnt/sda/ubuntu/lkx/papers/paper_in`。下表路径分别相对于这两个根目录；逐文件绝对路径、解析后的源路径、目标路径、用途、大小、SHA256 及是否仅作参考，见 [DATA_MIGRATION.tsv](DATA_MIGRATION.tsv) 和 `outputs/relags_baseline/00_data_check/data/migration_manifest.json`。

## 最终迁移内容

''' + '\n'.join(table) + '''

## 直接输入与兼容性处理

1. 从旧工程复制原视频、350 张提取图像、350 张去畸变图像、COLMAP 相机与稀疏模型。新流程直接读取 `data/images` 和 `data/colmap/sparse/0`，项目内 `data/sparse` 链接指向本项目副本。
2. 原视频为 2560×1440、约 29 fps、174.89655 秒；旧流程以约 2 fps 提取 1920×1080 图像。去畸变图像为 1875×1056。350 个相机全部注册，沿用已保存的 306 训练 / 44 测试划分；固定参考帧为 1、49、97、145、193、241、289、345。
3. 原最终 3DGS 包含 1,828,777 个三尺度椭球；官方 ReLaGS 2DGS 渲染接口使用两个尺度的面元。删除第三尺度不是无损适配，故旧 PLY 和检查点仅作审计与对照，使用复制的图像/COLMAP 重新完成官方 2DGS 30000 步训练。审计证据见 `outputs/relags_baseline/01_gaussian_scene/data/compatibility_audit.json`。新高斯及检查点位于该阶段 `data/model/`。
4. 复制的 SAM/OpenCLIP 是通用预训练编码器权重；本次重新从 RGB 计算全部 SAM 掩膜、CLIP 和 OpenSeg 特征。旧 LangSplat 特征、旧 SAM 分割、设备实例定位和编辑结果未进入新语义流程。
5. 保留原 COLMAP 坐标与原相机模型，未缩放、旋转或重定位输入。缺少独立公制尺度和重力标定。历史 LangSplat 地面仅保存在 `previous_work/reference_results/ground_reference.json` 供参考。场景坐标、范围、内外参、相机轨迹与划分的派生记录位于 `data/scene_information/` 和 Stage 00；派生文件不计入上述复制数量。

## 历史资料及排除范围

没有找到旧论文完整正文；保留现有报告、图表及实验说明，不补造无人机、相机型号或工业设备规格。历史配置里的绝对路径按原样归档，不作为新流程运行配置。

未迁移大量历史检查点、生成模型/扩散模型权重、环境缓存、旧语义数组和重复实验输出。初次候选复制中的 141 个重复历史图表副本经核验后，仅从新工程副本中移除；原工程文件未动。记录位于 `outputs/relags_baseline/00_data_check/data/excluded_duplicate_copies.json`。初始选择数量和后续补入最终检查点/通用编码器权重的历史记录均保留；以本文件、最终 manifest 和 `metrics/migration_summary_final.json` 为当前数量依据。

## 独立运行与审计

所有迁移均为复制，未移动、删除或写入原工程。最终核验覆盖全部 798 个复制文件：目标 SHA256 与迁移记录一致，全部源文件的大小和纳秒修改时间与初始只读清单一致，缺失审计覆盖项为 0。核验没有发现目标校验失败或源文件元信息变化。证据：`outputs/relags_baseline/00_data_check/metrics/final_integrity.json`；原工程完整清单：`outputs/relags_baseline/00_data_check/data/source_inventory.jsonl`。

数据、模型、输出目录中的 32 个运行期符号链接均有效并指向本项目内部。环境位于 `envs/`，权重缓存位于 `models/`；后续新权重通过本机代理经 SSH 转发下载，来源与校验记录单独保存在模型目录，不计入旧工程迁移表。整个复现无需读取旧工程语义结果或使用其环境。

本地 `E:\\codex_projects\\paper_in` 保存控制脚本、报告和少量预览副本；完整计算数据与约 49 GiB 的本次阶段输出保留在远程工作目录。最终执行状态见 [EXPERIMENT_REPORT.md](EXPERIMENT_REPORT.md)：Stage 00–07 完成，完整场景图失败，开放词汇查询完成、完整关系查询受阻。
'''
history = BASE / '00_data_check/data/migration_document_before_finalization.md'
if not history.exists():
    history.write_text((ROOT / 'DATA_MIGRATION.md').read_text())
(ROOT / 'DATA_MIGRATION.md').write_text(text)

plan = ROOT / 'EXECUTION_PLAN.md'
t = plan.read_text()
t = t[:t.index('## 当前状态')] + '''## 最终执行状态

Stage 00–07 已完成并核验；350 帧 SAM/CLIP/OpenSeg 全部重新计算，两个分支的 ROFA 重放误差为 0。Stage 08 完整 L2/L3 图在官方 OBB 构建处失败：5 个 L2 分组只有 1 或 3 个原始点，失败输入、索引及完整日志保留。独立 L3 图完成，仅作为诊断，不替代完整图。Stage 09 完成 12 个开放词汇查询；6 个完整关系查询因上游缺失未执行。

本次有限调度任务已结束，没有仍在运行的阶段作业。最终证据、问题分析及待执行关系查询命令见 `EXPERIMENT_REPORT.md`、`BASELINE_STATUS.json` 和各阶段目录。没有为跑通流程修改退化节点处理规则。
'''
t = t.replace('7000/30000 检查点', '7000/15000/30000 检查点')
t = t.replace('上游产物指纹或配置变化使下游缓存失效，不覆盖旧运行。', '声明的输入或配置指纹变化使相应缓存失效，旧尝试的命令与日志保留。共享导入代码未必自动列入输入；修改后应使用 --force 或新的实验输出目录。')
plan.write_text(t)

readme = ROOT / 'README.md'
t = readme.read_text()
marker = '## 执行'
status = '''## 本次实际结果

**Stage 00–07 完成；完整 Stage 08 失败；Stage 09 仅完成 12 个开放词汇查询，6 个关系查询未执行。** 失败原因是官方 OBB 对 5 个极小 L2 分组无法构造包围盒。原始失败和完整输入均保留；`08_scene_graph/diagnostics/root_only/` 的 1189 节点、359928 边是独立根层诊断，不代表完整图成功。阶段作业已全部结束。

查看顺序：`EXPERIMENT_REPORT.md`（状态、实际命令与结果）→ `INDUSTRIAL_REVIEW.md`（工业问题）→ `DATA_MIGRATION.md` / `.tsv`（数据溯源）。机器可读状态为 `BASELINE_STATUS.json`，最终审计为 `outputs/relags_baseline/00_data_check/metrics/final_integrity.json`。

主要可视化：Stage 01 的 `visualizations/reconstruction/`，Stage 05 的层次着色图与 `reference049_pair_levels.jpg`，Stage 07 的分支 PLY，Stage 08 的 `diagnostics/root_only/visualizations/`，Stage 09 的 `visualizations/query_overview.jpg`。每个阶段的 README 给出完整数据、指标和运行记录位置。根目录下的路径均相对于本远程项目。

'''
if '## 本次实际结果' not in t:
    t = t.replace(marker, status + marker, 1)
t = t.replace('成功输出与输入/参数指纹匹配时复用。', '成功输出与声明的输入/参数指纹匹配时复用。共享导入代码不保证自动发现；修改这类代码后应使用 `--force`，并为改进实验使用独立输出目录。旧运行的配置、日志和输入快照保留，常规阶段产物路径可能被新的运行更新。')
t += '''
## 从本次结果继续

原始失败无需重复编码即可复查：完整 Stage 08 命令和失败日志见该阶段 README；原始失败分组位于 `diagnostics/obb/`。在另立改进实验并解决极小分组问题后，可从已保存的 Stage 07 继续运行受影响的 08–09。原法不变时再次执行会遇到相同 OBB 输入限制。

`scripts/query_baseline.py --mode open` 可以独立运行开放词汇分支；`--mode relational` 要求完整 L2/L3 关系文件。六个未执行查询、依赖和原定命令保存在 `09_relational_query/metrics/relational_query_blocked.json`，该相对路径位于 `outputs/relags_baseline/` 下。
'''
readme.write_text(t)

script = ROOT / 'scripts/update_report.py'
t = script.read_text().replace('`01_gaussian_scene/data/compatibility_audit.json`（生成后可查）', '`outputs/relags_baseline/01_gaussian_scene/data/compatibility_audit.json`')
script.write_text(t)
script = ROOT / 'scripts/stage_evidence.py'
t = script.read_text()
t = t.replace('；关系阈值回退 {sum(x.get("official_threshold_fallback_used",False) for x in q)}', '；完整关系查询未执行，其阈值回退统计不适用')
script.write_text(t)
notes = BASE / '00_data_check/NOTES.md'
marker = '### 最终交付审计'
t = notes.read_text() if notes.exists() else ''
if marker not in t:
    t += '''

### 最终交付审计

798 个目标复制文件 SHA256 全部一致；798 个源文件大小和纳秒修改时间均与初始清单一致，无审计覆盖缺失。数据/模型/输出下 32 个链接全部有效且在新工程内部；未检测到运行中的阶段作业。结果见 `metrics/final_integrity.json`。这验证文件完整性，不代表语义准确率或完整关系流程成功。

记录器曾出现任务元信息文件与科学统计同名的冲突，已修正命名；Stage 00 从原始字节副本恢复统计，Stage 02 重新只读统计后 SHA256 与首次统计一致。历史日志未删除，修复证据见根目录 `logs/runner_metric_collision.json`。
'''
notes.write_text(t)
subprocess.run(['python3', str(ROOT / 'scripts/update_report.py')], check=True, cwd=ROOT)

manifest = ROOT / 'logs/final_source_manifest.json'
j = json.loads(manifest.read_text())
j['time_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
j['controller_and_config_files'] = {
    str(p.relative_to(ROOT)): {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    for folder in ['scripts', 'configs'] for p in sorted((ROOT / folder).rglob('*'))
    if p.is_file() and '__pycache__' not in p.parts
}
manifest.write_text(json.dumps(j, indent=2))
print(json.dumps({'files':len(rows), 'bytes':total, 'status':'documentation_finalized'}, ensure_ascii=False))
