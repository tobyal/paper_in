"""Copy source and explicitly selected evidence into an existing publication checkout."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', required=True)
    args = parser.parse_args()
    repo = Path(args.repository).resolve()
    assert (repo / '.git').is_dir(), repo
    assert subprocess.check_output(['git', '-C', str(repo), 'remote', 'get-url', 'origin'], text=True).strip() in (
        'git@github.com:tobyal/paper_in.git', 'https://github.com/tobyal/paper_in.git')
    dest = repo / 'experiments/saga_relags_v1'
    assert not dest.exists(), 'Refuse to overwrite an existing experiment publication'
    records = []

    def copy(source, target, purpose):
        source, target = Path(source), Path(target)
        assert source.is_file() and source.stat().st_size < 5_000_000, source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
        records.append(dict(source=str(source), destination=str(target.relative_to(repo)),
                            bytes=source.stat().st_size, sha256=digest, purpose=purpose))

    for name in ['AGENTS.md', 'README.md', 'EXPERIMENT_REPORT.md']:
        copy(ROOT / name, dest / name, 'Experiment documentation')
    for directory in ['src', 'scripts', 'configs', 'docs']:
        for p in sorted((ROOT / directory).rglob('*')):
            if p.is_file() and p.suffix in {'.py', '.sh', '.json', '.md', '.patch'}:
                copy(p, dest / p.relative_to(ROOT), 'Source, configuration or documented adaptation')
    # Existing shared helpers match the tracked versions; this projection helper is newly required.
    for name in ['__init__.py', 'geometry.py']:
        rel = Path('industrial_world_model/hybrid_views') / name
        assert not (repo / rel).exists(), rel
        copy(PROJECT / rel, repo / rel, 'Shared projection dependency used by the new experiment')

    figure_sources = [
        ('outputs/gallery/instances.jpg', 'instances.jpg', 'Nine reviewed usable Gaussian instances'),
        ('outputs/A/extractions/iteration_10000/independent_objects_overview.jpg', 'all_ten_objects.jpg', 'All ten attempts, including the failed rack'),
        ('outputs/A/extractions/iteration_10000/training_projection_overview.jpg', 'training_projections.jpg', 'Training-view projections; not ground truth'),
        ('outputs/A/training_curves.png', 'training_curves.png', 'Recorded training statistics'),
        ('outputs/B/visual_representatives.jpg', 'category_representatives.jpg', 'Real crops used for category shared semantics'),
        ('outputs/C/som_overview.jpg', 'som_review.jpg', 'Visual relation evidence; no reliable new edges'),
        ('outputs/C/visualizations/instance_graph_gallery.jpg', 'instance_graph.jpg', 'Isolated Gaussian instance map with selected geometry edges'),
        ('outputs/C/visualizations/scene_graph_gallery.jpg', 'scene_graph.jpg', 'Full-scene context with occlusion retained'),
        ('outputs/gallery/query_examples.jpg', 'query_examples.jpg', 'Four held-out projection examples'),
        ('outputs/D/query_gallery.jpg', 'all_queries.jpg', 'All five category and five relation queries'),
    ]
    for source, name, purpose in figure_sources:
        copy(ROOT / source, dest / 'docs/figures' / name, purpose)

    evidence = [
        'outputs/summary.json', 'outputs/A/extractions/iteration_10000/summary.json',
        'outputs/A/extractions/iteration_10000/quality_review.json',
        'outputs/A/saga_model/training_metrics.csv', 'outputs/A/saga_model/training_contract.json',
        'outputs/A/prompt_refinement_review.json', 'outputs/B/validation.json',
        'outputs/B/summary.json', 'outputs/B/text_prompts.json', 'outputs/B/categories.json',
        'outputs/C/summary.json', 'outputs/C/scene_graph.json', 'outputs/C/visual_quality_review.json',
        'outputs/C/grounding_review.json', 'outputs/C/semantic_relations.json',
        'outputs/C/visualizations/displayed_relations.json', 'outputs/D/summary.json',
        'outputs/D/example_selection.json', 'outputs/D/heldout_display_visibility.json',
        'outputs/validation/checks.json', 'outputs/validation/portable_render.json',
        'outputs/validation/query_logic.json', 'inputs/environment_final.txt',
        'inputs/upstream_submodules.txt', 'inputs/dataset_summary.json', 'inputs/manifest.json',
    ]
    for relative in evidence:
        copy(ROOT / relative, dest / 'evidence' / relative, 'Recorded experiment result or reproducibility metadata')
    for pattern in ['logs/*/*/command.json', 'logs/*/*/result.json', 'outputs/C/som/*/*.json', 'outputs/D/query_*/result.json']:
        for p in sorted(ROOT.glob(pattern)):
            copy(p, dest / 'evidence' / p.relative_to(ROOT), 'Actual command, status or inference evidence')

    upstream = ROOT / 'third_party/SegAnyGAussians'
    commit = subprocess.check_output(['git', '-C', str(upstream), 'rev-parse', 'HEAD'], text=True).strip()
    diff = subprocess.check_output(['git', '-C', str(upstream), 'diff', 'HEAD', '--',
                                   'extract_segment_everything_masks.py', 'scene/dataset_readers.py',
                                   'train_contrastive_feature.py', 'utils/camera_utils.py'])
    (dest / 'docs/patches/saga_complete.patch').write_bytes(diff)
    copy(upstream / 'LICENSE', dest / 'licenses/SAGA_LICENSE', 'Upstream license')
    copy(upstream / 'third_party/segment-anything/LICENSE', dest / 'licenses/SAM_LICENSE', 'Upstream license')
    copy(upstream / 'submodules/diff-gaussian-rasterization/LICENSE.md', dest / 'licenses/Gaussian_Splatting_LICENSE.md', 'Original Gaussian Splatting component license')
    lock = dict(saga=dict(url='https://github.com/Jumpat/SegAnyGAussians.git', commit=commit,
                          patch='docs/patches/saga_complete.patch', patch_sha256=hashlib.sha256(diff).hexdigest()),
                sam=dict(url='https://github.com/facebookresearch/segment-anything.git', commit='6fdee8f2727f4506cfbbe553e23b895e27956588'),
                kmeans=dict(url='https://github.com/subhadarship/kmeans_pytorch.git', commit='f7f36bd1cb4e3a761d73d584866d0a9c6b4d2805'),
                notes='Official sources and compiled binaries are not bundled; preserve all nested licenses.')
    (dest / 'UPSTREAM.lock.json').write_text(json.dumps(lock, indent=2) + '\n')
    (dest / '.gitignore').write_text('/envs/\n/cache/\n/third_party/\n/inputs/\n/outputs/\n/logs/\n/world_model/\n/review/\n')

    gallery = ['# SAGA + ReLaGS：关键实际结果', '',
               '10个对象尝试中9个可用于设备级查询展示；1个多层料架失败。图中保留实际缺失和伪影。',
               '场景图有33个M0节点，查询目标只包含9个审核可用实例。视觉语义新增边为0。',
               '关系图仅展示部分几何边；没有人工分割真值，不把提示一致性解释为准确率。', '',
               '图像为服务器结果的原样复制，来源和SHA-256见 [PUBLICATION_MANIFEST.json](../PUBLICATION_MANIFEST.json)。', '']
    captions = ['9个审核可用实例', '全部10次提取（含失败料架）', '训练视角投影检查', '实际训练曲线',
                '8类代表图像', 'SoM视觉关系检查', '独立实例与几何关系', '完整场景中的实例与关系',
                '类别及关系查询示例', '全部10项查询']
    for (_, name, _), caption in zip(figure_sources, captions):
        gallery += [f'## {caption}', '', f'![{caption}](figures/{name})', '']
    (dest / 'docs/GALLERY.md').write_text('\n'.join(gallery))
    publication = '''# 仓库归档范围与恢复

本目录提交代码、配置、报告、关键结果图和轻量数值证据。`evidence/`按服务器相对路径归档实际记录；报告中的`outputs/`、`inputs/`、`logs/`和`world_model/`路径指服务器完整实验。

未上传原始图像集、M0数据库、PLY、Gaussian索引/特征张量、模型权重、环境及检查点。Git克隆不能直接复现完整运行，需要按原始实验README准备相应输入。代码使用同仓库已发布的`m0`及`industrial_world_model`通用渲染/几何接口。

## 获取本次固定上游及完整适配

在本实验目录执行（新目录；已有上游修改请先检查，不要覆盖）：

```bash
git clone https://github.com/Jumpat/SegAnyGAussians.git third_party/SegAnyGAussians
git -C third_party/SegAnyGAussians checkout 2d4c5d77c857c956d747e4775d3d72c4ec5dfe16
git -C third_party/SegAnyGAussians -c url.https://github.com/.insteadOf=git@github.com: submodule update --init --recursive
git -C third_party/SegAnyGAussians apply --check ../../docs/patches/saga_complete.patch
git -C third_party/SegAnyGAussians apply ../../docs/patches/saga_complete.patch
bash scripts/setup_environment.sh
```

完整补丁与服务器四个改动文件逐字节对应，包含相机主点/缩放、CPU张量读取、RGB及断点记录适配。`patch_official.py`是实验准备阶段入口；已应用完整补丁时不重复执行。环境脚本需要兼容的基础Python/Torch/PyTorch3D，未包含权重和平台二进制。

SAGA/SAM许可证保存在`licenses/`；其他嵌套组件保留原许可证。上游版权不属于本项目，本仓库不为工业图像另行授予开放许可。

- [运行说明](README.md)
- [完整实验报告](EXPERIMENT_REPORT.md)
- [关键结果图集](docs/GALLERY.md)
- [实际数值及执行记录](evidence/)
'''
    (dest / 'PUBLICATION.md').write_text(publication)
    readme = dest / 'README.md'
    text = readme.read_text()
    text = text.replace('## 环境', '## GitHub阅读入口\n\n[关键结果图集](docs/GALLERY.md) · [归档范围与恢复](PUBLICATION.md) · [轻量结果证据](evidence/)\n\n仓库只包含精选结果；下文的完整数据和检查点路径指服务器实验目录。\n\n## 环境', 1)
    readme.write_text(text)
    main_readme = repo / 'README.md'
    text = main_readme.read_text()
    marker = '## 工业空间先验与原生 3DGS：M1—M5'
    text = text.replace(marker, '''## SAGA + ReLaGS：工业对象实例与关系查询

新增独立实验 [saga_relags_v1](experiments/saga_relags_v1/README.md)：官方SAGA完成10,000步共享亲和训练；10个对象尝试中9个可用于设备级查询展示、1个料架失败；8类共享语义；33节点几何图；5项类别查询和5项关系查询。视觉关系提升已运行，但没有得到可靠新增语义边，不能视为该部分验证成功。

[完整报告](experiments/saga_relags_v1/EXPERIMENT_REPORT.md) · [关键结果图集](experiments/saga_relags_v1/docs/GALLERY.md) · [版本、补丁及归档范围](experiments/saga_relags_v1/PUBLICATION.md)。原工程及既有结果未改动，模型权重和完整数据保留在服务器。

''' + marker, 1)
    main_readme.write_text(text)
    for record in records:
        record['published_sha256'] = hashlib.sha256((repo / record['destination']).read_bytes()).hexdigest()
        record['publication_edited'] = record['published_sha256'] != record['sha256']
    (dest / 'PUBLICATION_MANIFEST.json').write_text(json.dumps(dict(source_root=str(ROOT), files=records), ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(copied_files=len(records), copied_bytes=sum(r['bytes'] for r in records), destination=str(dest))))


if __name__ == '__main__':
    main()
