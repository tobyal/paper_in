#!/usr/bin/env python3
"""F10-F12: CPU-only descriptive plots of frozen CSV/JSON results.

Run from any directory: python scripts/plot_data_analysis.py --figure all
No model imports, rendering, prediction, thresholding, or metric re-evaluation.
Per-query metrics already average eligible views; queries are equally weighted.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'source_data/data_analysis'
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'cache/matplotlib'))
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.transforms import Bbox

WIDTH = 7.08
DPI = 450
METHODS = ['langsplat', 'thgs', 'relags', 'ours']
NAMES = {'langsplat': 'LangSplat', 'thgs': 'THGS', 'relags': 'ReLaGS', 'ours': 'Ours',
         'box_gated': 'Box-based', 'box_all33': 'Box-based (all 33)', 'no_relation': 'Ours w/o Relation'}
COLORS = {'langsplat': '#E69F00', 'thgs': '#009E73', 'relags': '#8E75B6', 'ours': '#0072B2'}
POS, NEG = '#0072B2', '#D55E00'
STAGES = ['category_candidates', 'relation_targets', 'fine_available']
STAGE_NAMES = ['Category candidates', 'Relation-matched targets', 'Available fine instances']
STAGE_COLORS = ['#909CA6', '#D89F35', '#0072B2']
RELATIONS = {'left_of': 'Left', 'right_of': 'Right', 'in_front_of': 'Front', 'behind': 'Behind', 'near': 'Near'}
FIGURES = {'F10': 'F10_query_performance', 'F11': 'F11_mechanism_contribution', 'F12': 'F12_candidate_reduction'}
INPUTS = ['E01_external_comparison/metrics/per_query.csv', 'E01_external_comparison/metrics/per_relation.csv',
          'E01_external_comparison/metrics/summary.csv', 'E02_ablation/mechanism_deltas.csv',
          'E02_ablation/metrics/per_query.csv', 'E02_ablation/metrics/summary.csv',
          'E04_relation_retrieval/query_statistics.csv', 'E04_relation_retrieval/query_statistics.json']
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 7, 'axes.titlesize': 8,
                     'axes.labelsize': 7, 'xtick.labelsize': 6, 'ytick.labelsize': 6,
                     'axes.linewidth': .6, 'lines.linewidth': .9, 'svg.fonttype': 'none',
                     'pdf.fonttype': 42, 'ps.fonttype': 42, 'savefig.dpi': DPI,
                     'figure.facecolor': 'white', 'axes.facecolor': 'white'})


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, obj):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def rows(path):
    with (ROOT / path).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def csvwrite(path, records):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        out = csv.DictWriter(f, fieldnames=list(records[0]))
        out.writeheader(); out.writerows(records)


def keyed(records):
    result = {(r['method'], r['query_id']): r for r in records}
    assert len(result) == len(records), 'Duplicate method/query rows'
    return result


def analyze():
    ext, abl = rows(INPUTS[0]), rows(INPUTS[4])
    e, a = keyed(ext), keyed(abl)
    qids = sorted({r['query_id'] for r in ext})
    assert qids == [f'Q{i:03d}' for i in range(1, 26)]
    assert {r['method'] for r in ext} == set(METHODS)
    assert len(ext) == 100 and len(abl) == 175
    rel = {q: e['ours', q]['relation'] for q in qids}
    assert set(rel.values()) == set(RELATIONS)
    valid = [q for q in qids if int(e['ours', q]['valid_views']) > 0]
    excluded = [q for q in qids if q not in valid]
    assert excluded == ['Q005', 'Q025'] and len(valid) == 23
    assert sum(int(e['ours', q]['valid_views']) for q in valid) == 44
    for records in [ext, abl]:
        for r in records:
            q = r['query_id']
            assert r['relation'] == rel[q] and r['valid_views'] == e['ours', q]['valid_views']
            for metric in ['iou', 'precision', 'recall']:
                assert bool(r[metric]) == (q in valid)
                if q in valid:
                    assert math.isfinite(float(r[metric])) and 0 <= float(r[metric]) <= 1
    # Check independently saved summary / relation tables, without re-running predictions.
    for data, path in [(ext, INPUTS[2]), (abl, INPUTS[5])]:
        for s in rows(path):
            selected = [r for r in data if r['method'] == s['method'] and r['query_id'] in valid]
            assert len(selected) == int(s['valid_queries']) == 23
            for metric in ['iou', 'precision', 'recall']:
                assert abs(np.mean([float(r[metric]) for r in selected]) - float(s[metric])) < 1e-12
    for s in rows(INPUTS[1]):
        selected = [r for r in ext if r['method'] == s['method'] and r['relation'] == s['relation'] and r['query_id'] in valid]
        assert len(selected) == int(s['valid_queries'])
        for metric in ['iou', 'precision', 'recall']:
            assert abs(np.mean([float(r[metric]) for r in selected]) - float(s[metric])) < 1e-12
    for q in valid:
        assert all(e['ours', q][k] == a['ours', q][k] for k in ['iou', 'precision', 'recall'])

    distribution, points = [], []
    rng = np.random.default_rng(20261127)
    for mi, m in enumerate(METHODS):
        values = np.array([100 * float(e[m, q]['iou']) for q in valid])
        q1, median, q3 = np.percentile(values, [25, 50, 75])
        iqr = q3 - q1
        distribution.append(dict(method=m, n=len(values), mean_iou_percent=float(values.mean()),
            q1_percent=float(q1), median_percent=float(median), q3_percent=float(q3),
            whisker_low_percent=float(values[values >= q1 - 1.5 * iqr].min()),
            whisker_high_percent=float(values[values <= q3 + 1.5 * iqr].max()),
            queries_iou_ge50=int((values >= 50).sum()), actual_zero_queries=int((values == 0).sum())))
        for q, value, jitter in zip(valid, values, rng.uniform(-.13, .13, len(values))):
            points.append(dict(method=m, query_id=q, iou_percent=float(value), x=mi + 1 + float(jitter)))
    wins = [q for q in valid if float(e['ours', q]['iou']) > max(float(e[m, q]['iou']) for m in METHODS[:-1])]
    heat = [dict(method=m, query_id=q, relation=rel[q], valid_views=int(e[m, q]['valid_views']),
                 evaluated=q in valid, iou_percent=100 * float(e[m, q]['iou']) if q in valid else '') for m in METHODS for q in qids]
    deltas, mechanism = [], {}
    saved = {r['query_id']: r for r in rows(INPUTS[3])}
    assert set(saved) == set(valid)
    for q in valid:
        d = dict(query_id=q, relation=rel[q], ours_iou_percent=100 * float(a['ours', q]['iou']),
                 box_iou_percent=100 * float(a['box_gated', q]['iou']),
                 no_relation_iou_percent=100 * float(a['no_relation', q]['iou']))
        d['fine_minus_box_iou_pp'] = d['ours_iou_percent'] - d['box_iou_percent']
        d['relation_gain_iou_pp'] = d['ours_iou_percent'] - d['no_relation_iou_percent']
        for key in ['fine_minus_box_iou_pp', 'relation_gain_iou_pp']:
            assert abs(d[key] - float(saved[q][key])) < 1e-10
        deltas.append(d)
    for kind, key, base in [('entity', 'fine_minus_box_iou_pp', 'box_gated'), ('relation', 'relation_gain_iou_pp', 'no_relation')]:
        values = np.array([r[key] for r in deltas])
        mechanism[kind] = dict(mean_iou_gain_pp=float(values.mean()), improved=int((values > 1e-10).sum()),
            declined=int((values < -1e-10).sum()), unchanged=int((abs(values) <= 1e-10).sum()),
            precision_gain_pp=float(np.mean([100 * (float(a['ours', q]['precision']) - float(a[base, q]['precision'])) for q in valid])),
            recall_gain_pp=float(np.mean([100 * (float(a['ours', q]['recall']) - float(a[base, q]['recall'])) for q in valid])))
    pr = [dict(method=m, iou_percent=float(np.mean([100 * float(a[m, q]['iou']) for q in valid])),
               precision_percent=float(np.mean([100 * float(a[m, q]['precision']) for q in valid])),
               recall_percent=float(np.mean([100 * float(a[m, q]['recall']) for q in valid])),
               availability='all_33_coarse_boxes' if m == 'box_all33' else 'shared_main_availability')
          for m in ['box_gated', 'no_relation', 'ours', 'box_all33']]
    counts = rows(INPUTS[6]); detail = {r['query_id']: r for r in read(ROOT / INPUTS[7])}
    assert [r['query_id'] for r in counts] == qids and set(detail) == set(qids)
    all_category, all_matched, all_fine, all_unavailable = set(), set(), set(), set()
    for r in counts:
        q = r['query_id']; d = detail[q]; r['relation'] = rel[q]
        for key in STAGES + ['unavailable']:
            r[key] = int(r[key])
        category, matched, fine, unavailable = [set(d[k]) for k in ['known_category_instances', 'matched_object_ids', 'renderable_object_ids', 'unavailable_object_ids']]
        assert r['category_candidates'] == len(category) == d['same_category_candidates_before']
        assert r['relation_targets'] == len(matched) == d['matches_after']
        assert r['fine_available'] == len(fine) and r['unavailable'] == len(unavailable)
        assert fine <= matched <= category and fine.isdisjoint(unavailable) and fine | unavailable == matched
        assert set(filter(None, r['returned_ids'].split(';'))) == fine
        assert set(filter(None, r['matched_ids'].split(';'))) == matched
        assert {edge['relation'] for edge in d['relation_evidence']} == {rel[q]}
        r['unavailable_ids'] = ';'.join(sorted(unavailable))
        all_category.update(category); all_matched.update(matched); all_fine.update(fine); all_unavailable.update(unavailable)
    totals = {k: sum(r[k] for r in counts) for k in STAGES + ['unavailable']}
    totals.update(relation_reduction_percent=100 * (1 - totals['relation_targets'] / totals['category_candidates']),
                  matched_fine_availability_percent=100 * totals['fine_available'] / totals['relation_targets'],
                  unique_category_devices=len(all_category), unique_matched_devices=len(all_matched),
                  unique_fine_devices=len(all_fine), unique_unavailable_devices=len(all_unavailable),
                  unavailable_queries=[r['query_id'] for r in counts if r['unavailable']])
    stats = dict(valid_queries=valid, excluded_queries=excluded, valid_views=44,
                 relation_by_query=rel, method_distributions=distribution, ours_strict_wins=wins,
                 mechanisms=mechanism, precision_recall=pr, candidate_totals=totals,
                 metric_aggregation='mean over eligible views per query, then equal mean over 23 queries',
                 reference='SAM-assisted Pseudo-GT; not independently human-verified',
                 box_statistics='NumPy linear percentiles; whiskers at extreme observations within 1.5 IQR; all 23 points shown',
                 jitter='horizontal only; numpy default_rng seed 20261127; exact x positions saved',
                 sign_zero_tolerance_pp=1e-10, significance_test='none; queries can share devices and views')
    csvwrite(DATA / 'F10_heatmap.csv', heat); csvwrite(DATA / 'F10_distribution.csv', distribution)
    csvwrite(DATA / 'F10_query_points.csv', points); csvwrite(DATA / 'F11_query_deltas.csv', deltas)
    csvwrite(DATA / 'F11_configuration_points.csv', pr); csvwrite(DATA / 'F12_query_counts.csv', counts)
    csvwrite(DATA / 'F12_stage_totals.csv', [dict(stage=k, label=n, candidate_occurrences=totals[k]) for k, n in zip(STAGES, STAGE_NAMES)])
    write(DATA / 'statistics.json', stats)
    return dict(stats=stats, e=e, a=a, qids=qids, valid=valid, rel=rel, heat=heat, points=points, deltas=deltas, counts=counts)


def style(ax, grid=True):
    ax.spines[['top', 'right']].set_visible(False)
    ax.tick_params(width=.6, length=2.5)
    if grid:
        ax.yaxis.grid(True, color='#E7E9EC', linewidth=.5)
        ax.set_axisbelow(True)


def groups(ax, qids, rel, y=1.035):
    previous = None; start = 0
    for i in range(len(qids) + 1):
        current = rel[qids[i]] if i < len(qids) else None
        if i and current != previous:
            ax.text((start + i - 1) / 2, y, RELATIONS[previous], transform=ax.get_xaxis_transform(),
                    ha='center', va='bottom', fontsize=6, color='#515960')
            if i < len(qids):
                ax.axvline(i - .5, color='#D3D7DB', lw=.6, zorder=0)
            start = i
        previous = current


def title(fig, text):
    fig.text(.10, .975, text, fontsize=9, fontweight='bold', ha='left', va='top')


def save_figure(code, fig, panel_bounds, data_files, details):
    name = FIGURES[code]; out = ROOT / 'figures' / name
    (out / 'subplots').mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    # Editable vector text, fixed physical dimensions, no tight-bbox width drift.
    for suffix in ['png', 'svg', 'pdf']:
        fig.savefig(out / f'{name}.{suffix}', dpi=DPI, facecolor='white')
    for panel, (bottom, top) in panel_bounds.items():
        crop = Bbox.from_extents(0, bottom * fig.get_figheight(), WIDTH, top * fig.get_figheight())
        for suffix in ['png', 'svg', 'pdf']:
            fig.savefig(out / 'subplots' / f'{panel}.{suffix}', bbox_inches=crop, dpi=DPI, facecolor='white')
    write(out / 'layout.json', dict(size_inches=list(fig.get_size_inches()), width_mm=WIDTH * 25.4,
        dpi=DPI, editable_text='SVG text and embedded TrueType PDF; DejaVu Sans',
        axes=[dict(title=ax.get_title(), position=list(ax.get_position().bounds)) for ax in fig.axes],
        subplot_vertical_bounds=panel_bounds, method_colors=COLORS, description=details))
    write(out / 'editable_text.json', [dict(text=t.get_text(), fontsize=t.get_fontsize())
        for t in fig.findobj(matplotlib.text.Text) if t.get_text()])
    # Bounding-box check for canvas clipping; intentional grid lines are excluded.
    renderer = fig.canvas.get_renderer(); canvas = fig.bbox
    outside = []
    for t in fig.findobj(matplotlib.text.Text):
        if not t.get_visible() or not t.get_text():
            continue
        b = t.get_window_extent(renderer)
        if b.x0 < -1 or b.y0 < -1 or b.x1 > canvas.width + 1 or b.y1 > canvas.height + 1:
            outside.append(t.get_text())
    assert not outside, (name, 'text outside canvas', outside)
    for data in data_files:
        shutil.copy2(DATA / data, out / data)
    sourcepaths = [ROOT / p for p in INPUTS] + [Path(__file__).resolve()] + [DATA / p for p in data_files]
    write(out / 'sources.json', {str(p): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sourcepaths})
    plt.close(fig)
    return dict(figure=name, experiment={'F10': 'E01_external_comparison', 'F11': 'E02_ablation', 'F12': 'E04_relation_retrieval'}[code],
                png=f'figures/{name}/{name}.png', svg=f'figures/{name}/{name}.svg', pdf=f'figures/{name}/{name}.pdf', description=details)


def f10(d):
    s = d['stats']; fig = plt.figure(figsize=(WIDTH, 5.6))
    title(fig, 'Query-wise retrieval performance')
    ax = fig.add_axes([.108, .65, .795, .22])
    values = np.array([[100 * float(d['e'][m, q]['iou']) if q in d['valid'] else np.nan for q in d['qids']] for m in METHODS])
    cmap = plt.get_cmap('viridis').copy(); cmap.set_bad('#DDDFE2')
    mesh = ax.pcolormesh(np.arange(26) - .5, np.arange(5) - .5, np.ma.masked_invalid(values),
                         cmap=cmap, vmin=0, vmax=100, edgecolors='white', linewidth=.45)
    ax.set_ylim(3.5, -.5); ax.set_yticks(range(4), [NAMES[m] for m in METHODS])
    ax.set_xticks(range(25), d['qids'], rotation=60, ha='right', fontsize=5.5)
    ax.tick_params(length=0, pad=3)
    for y, m in enumerate(METHODS):
        ax.get_yticklabels()[y].set_color(COLORS[m])
        ax.get_yticklabels()[y].set_fontweight('bold')
        for x, val in enumerate(values[y]):
            ax.text(x, y, 'N/A' if np.isnan(val) else f'{val:.1f}', fontsize=5.0, ha='center', va='center',
                    color='#60666C' if np.isnan(val) else ('white' if val < 54 else '#172026'))
    for spine in ax.spines.values(): spine.set_visible(False)
    groups(ax, d['qids'], d['rel'], 1.035)
    fig.text(.108, .925, '(a) Projection IoU per query (%)', fontweight='bold', fontsize=7.5)
    cbax = fig.add_axes([.928, .65, .012, .22]); cb = fig.colorbar(mesh, cax=cbax, ticks=[0, 25, 50, 75, 100]); cb.outline.set_linewidth(.4)
    cb.solids.set_rasterized(False)
    cbax.tick_params(labelsize=5.5, length=2, pad=2)
    fig.text(.108, .554, 'Gray N/A: no reliable reference (Q005, Q025). True zero scores remain on the color scale.', fontsize=6)
    ax = fig.add_axes([.108, .17, .795, .29]); style(ax)
    vals = [values[i, np.isfinite(values[i])] for i in range(4)]
    boxes = ax.boxplot(vals, widths=.42, whis=1.5, patch_artist=True, showfliers=False,
        medianprops=dict(color='#20262B', linewidth=1.2), boxprops=dict(linewidth=.75),
        whiskerprops=dict(linewidth=.75), capprops=dict(linewidth=.75))
    for patch, m in zip(boxes['boxes'], METHODS): patch.set_facecolor(COLORS[m]); patch.set_alpha(.17)
    for m in METHODS:
        pts = [r for r in d['points'] if r['method'] == m]
        ax.scatter([r['x'] for r in pts], [r['iou_percent'] for r in pts], s=10,
                   color=COLORS[m], edgecolors='white', linewidths=.25, zorder=3, clip_on=False)
    means = [r['mean_iou_percent'] for r in s['method_distributions']]
    ax.scatter(range(1, 5), means, marker='D', s=19, facecolors='white', edgecolors='#172026', linewidths=.8, zorder=5)
    ax.set_ylim(0, 100); ax.set_yticks(range(0, 101, 20)); ax.set_ylabel('Projection IoU (%)')
    labels = [f"{NAMES[r['method']]}\nMean {r['mean_iou_percent']:.2f}%\nIoU >= 50%: {r['queries_iou_ge50']}/23" for r in s['method_distributions']]
    ax.set_xticks(range(1, 5), labels, fontsize=6.2); ax.tick_params(axis='x', length=0, pad=5)
    fig.text(.108, .505, '(b) Query-wise distribution', fontsize=7.5, fontweight='bold')
    fig.text(.903, .505, f"Ours strictly highest: {len(s['ours_strict_wins'])}/23", ha='right', fontsize=6.5)
    ax.legend(handles=[Line2D([], [], marker='D', markerfacecolor='white', color='#172026', lw=0, label='Mean', markersize=4),
                       Line2D([], [], color='#172026', lw=1.2, label='Median')], loc='upper center', ncol=2,
              frameon=False, fontsize=5.8, bbox_to_anchor=(.57, 1.06), handlelength=1.2)
    fig.text(.108, .047, '23 evaluated queries; boxes: Q1-Q3; whiskers: 1.5 IQR; all query points shown (horizontal jitter only).', fontsize=6)
    fig.text(.108, .022, 'SAM-assisted reference masks, not independent human GT. Descriptive statistics; no significance test.', fontsize=6, color='#515960')
    return save_figure('F10', fig, {'a_heatmap': (.54, .945), 'b_distribution': (.01, .53)},
        ['F10_heatmap.csv', 'F10_distribution.csv', 'F10_query_points.csv'],
        dict(evaluated_queries=23, excluded_queries=s['excluded_queries'], original_query_order=d['qids'],
             zero_is_not_na=True, whisker_iqr=1.5, horizontal_jitter_seed=20261127, ours_strict_wins=len(s['ours_strict_wins'])))


def f11(d):
    s = d['stats']; fig = plt.figure(figsize=(WIDTH, 7.55))
    title(fig, 'Contribution of refined entities and spatial relations')
    # Same query order and range for both signed-difference panels.
    all_values = [r[k] for r in d['deltas'] for k in ['fine_minus_box_iou_pp', 'relation_gain_iou_pp']]
    lo = 10 * math.floor(min(all_values) / 10); hi = 10 * math.ceil(max(all_values) / 10)
    configs = [('entity', 'fine_minus_box_iou_pp', .725, '(a) Entity refinement: Ours - Box-based', ['Q007', 'Q011', 'Q022']),
               ('relation', 'relation_gain_iou_pp', .405, '(b) Relation constraint: Ours - Ours w/o Relation', ['Q006', 'Q007', 'Q013', 'Q017', 'Q018', 'Q024'])]
    for kind, key, bottom, heading, highlights in configs:
        ax = fig.add_axes([.105, bottom, .845, .165]); style(ax)
        values = np.array([r[key] for r in d['deltas']]); xs = np.arange(len(values))
        ax.bar(xs, values, width=.65, color=[POS if v > 0 else NEG for v in values], linewidth=.4, edgecolor='white', zorder=3)
        for i, v in enumerate(values):
            if abs(v) <= 1e-10: ax.plot(i, 0, 'o', ms=3, mfc='white', mec='#333A40', mew=.7, zorder=5)
            if d['valid'][i] in highlights:
                ax.text(i, v + (2 if v >= 0 else -2), f'{v:+.1f}', ha='center', va='bottom' if v >= 0 else 'top', fontsize=5.6)
        m = s['mechanisms'][kind]; avg = m['mean_iou_gain_pp']
        ax.axhline(0, color='#333A40', linewidth=.75, zorder=4)
        ax.axhline(avg, color='#303A40', linewidth=.8, ls=(0, (4, 3)), zorder=4)
        ax.set_xlim(-.6, len(values) - .4); ax.set_ylim(lo, hi); ax.set_yticks(np.arange(lo, hi + 1, 15))
        ax.set_ylabel('IoU difference (pp)')
        ax.set_xticks(xs, d['valid'], rotation=60, ha='right', fontsize=5.7)
        groups(ax, d['valid'], d['rel'], 1.03)
        fig.text(.105, bottom + .215, heading, fontweight='bold', fontsize=7.5)
        fig.text(.105, bottom - .073,
            f"Mean {avg:+.2f} pp (dashed)   |   {m['improved']} improved, {m['declined']} declined, {m['unchanged']} unchanged", fontsize=6.3)
    ax = fig.add_axes([.105, .105, .49, .16]); style(ax)
    records = {r['method']: r for r in s['precision_recall']}
    styles = {'box_gated': ('s', '#6F777E'), 'no_relation': ('^', '#D55E00'), 'ours': ('o', COLORS['ours']), 'box_all33': ('D', '#6F777E')}
    offsets = {'box_gated': (-5, -13), 'no_relation': (-10, -13), 'ours': (5, 5), 'box_all33': (0, 8)}
    for m, r in records.items():
        marker, color = styles[m]; x, y = r['recall_percent'], r['precision_percent']
        ax.scatter(x, y, s=36, marker=marker, edgecolors=color,
            facecolors='white' if m == 'box_all33' else color, linewidths=.9, zorder=5)
        dx, dy = offsets[m]
        label = 'Box (all 33)' if m == 'box_all33' else ('w/o Relation' if m == 'no_relation' else NAMES[m])
        ax.annotate(label, (x, y), xytext=(dx, dy), textcoords='offset points', ha='center' if m != 'ours' else 'left',
                    fontsize=6, color=color)
    target = records['ours']
    for m, col in [('box_gated', '#6F777E'), ('no_relation', POS)]:
        r = records[m]
        ax.annotate('', xy=(target['recall_percent'], target['precision_percent']), xytext=(r['recall_percent'], r['precision_percent']),
                    arrowprops=dict(arrowstyle='-|>', color=col, lw=.9, shrinkA=7, shrinkB=7), zorder=2)
    ax.set_xlim(62, 100); ax.set_ylim(50, 95); ax.set_xticks([65, 75, 85, 95]); ax.set_yticks([50, 60, 70, 80, 90])
    ax.set_xlabel('Mean Recall (%)'); ax.set_ylabel('Mean Precision (%)')
    fig.text(.105, .295, '(c) Discrete configuration means (not a PR curve)', fontsize=7.5, fontweight='bold')
    ent, rel = s['mechanisms']['entity'], s['mechanisms']['relation']
    fig.text(.635, .26, 'Entity refinement', fontsize=7, fontweight='bold', color='#515960')
    fig.text(.635, .234, f"Precision {ent['precision_gain_pp']:+.2f} pp\nRecall {ent['recall_gain_pp']:+.2f} pp\nIoU {ent['mean_iou_gain_pp']:+.2f} pp", fontsize=6.5, va='top', linespacing=1.5)
    fig.text(.635, .16, 'Relation constraint', fontsize=7, fontweight='bold', color=POS)
    fig.text(.635, .134, f"Precision {rel['precision_gain_pp']:+.2f} pp\nRecall {rel['recall_gain_pp']:+.2f} pp\nIoU {rel['mean_iou_gain_pp']:+.2f} pp", fontsize=6.5, va='top', linespacing=1.5)
    fig.text(.105, .037, '23 queries; SAM-assisted references. Main Box/Ours share availability. Hollow all-33 box: supplement only.', fontsize=6)
    fig.text(.105, .016, 'Blue: positive; vermilion: negative; open circles: unchanged. Arrows compare configurations, not thresholds.', fontsize=6, color='#515960')
    return save_figure('F11', fig, {'a_entity': (.635, .955), 'b_relation': (.315, .635), 'c_configurations': (.005, .31)},
        ['F11_query_deltas.csv', 'F11_configuration_points.csv'], dict(evaluated_queries=23, query_order=d['valid'],
            common_delta_ylim_pp=[lo, hi], positive_color=POS, negative_color=NEG, zero_tolerance_pp=1e-10,
            mechanisms=s['mechanisms'], discrete_configurations_not_pr_curve=True, all33_different_availability=True))


def f12(d):
    s = d['stats']; t = s['candidate_totals']; fig = plt.figure(figsize=(WIDTH, 5.65))
    title(fig, 'Equipment candidate reduction through spatial relations')
    ax = fig.add_axes([.105, .595, .845, .235]); style(ax)
    values = [t[k] for k in STAGES]
    bars = ax.bar(range(3), values, width=.49, color=STAGE_COLORS, edgecolor='#54616C', linewidth=.5)
    for bar, hatch, value in zip(bars, ['', '//', '..'], values):
        bar.set_hatch(hatch); ax.text(bar.get_x() + bar.get_width()/2, value + 3, str(value), fontsize=10, fontweight='bold', ha='center')
    ax.set_xlim(-.55, 2.55); ax.set_ylim(0, 140); ax.set_yticks([0, 35, 70, 105, 140]); ax.set_ylabel('Candidate occurrences')
    ax.set_xticks(range(3), ['Category\ncandidates', 'Relation-matched\ntargets', 'Available fine\ninstances'], fontsize=7)
    ax.tick_params(axis='x', length=0)
    fig.text(.105, .914, '(a) Accumulated counts across all 25 queries', fontsize=7.5, fontweight='bold')
    ax.annotate('', xy=(1, 126), xytext=(0, 126), arrowprops=dict(arrowstyle='->', color='#515960', lw=.9))
    ax.text(.5, 132, f"Relation filtering: -{t['relation_reduction_percent']:.1f}%", ha='center', fontsize=6.5)
    ax.annotate('', xy=(2, 75), xytext=(1, 75), arrowprops=dict(arrowstyle='->', color='#515960', lw=.9))
    ax.text(1.5, 86, f"Availability: {t['matched_fine_availability_percent']:.1f}%\n{t['unavailable']} matched occurrences unavailable", ha='center', fontsize=6.2, linespacing=1.4)
    fig.text(.105, .495, 'Counts are summed query-device occurrences, not unique devices; filtering is not an accuracy measure.', fontsize=6)
    ax = fig.add_axes([.105, .145, .845, .245]); style(ax)
    x = np.arange(25); width = .24
    for j, (key, label, col, hatch) in enumerate(zip(STAGES, STAGE_NAMES, STAGE_COLORS, ['', '//', '..'])):
        vals = [r[key] for r in d['counts']]
        ax.bar(x + (j - 1) * width, vals, width=width, label=label, color=col, hatch=hatch, edgecolor='#54616C', linewidth=.3, zorder=3)
        for i, v in enumerate(vals):
            if v == 0: ax.plot(i + (j - 1)*width, 0, 'o', ms=3.2, mfc='white', mec=col, clip_on=False, zorder=5)
    ymax = max(r['category_candidates'] for r in d['counts'])
    ax.set_ylim(0, ymax + 1); ax.set_yticks(range(0, ymax + 2)); ax.set_xlim(-.7, 24.7)
    labels = [q + ('*' if q in t['unavailable_queries'] else '') for q in d['qids']]
    ax.set_xticks(x, labels, rotation=60, ha='right', fontsize=5.6); ax.set_ylabel('Devices per query')
    groups(ax, d['qids'], d['rel'], 1.035)
    fig.text(.105, .454, '(b) Per-query stage counts (including Q005 and Q025)', fontsize=7.5, fontweight='bold')
    ax.legend(loc='upper center', bbox_to_anchor=(.52, 1.005), ncol=3, frameon=False, fontsize=5.7,
              handlelength=1.3, columnspacing=1.1, borderpad=.2)
    for tick, r in zip(ax.get_xticklabels(), d['counts']):
        if r['unavailable']: tick.set_color(NEG); tick.set_fontweight('bold')
    fig.text(.105, .052, '* Matched equipment lacks fine output: Q005, Q010, Q019, Q025. Q019 returns zero fine instances.', fontsize=6)
    fig.text(.105, .025, 'Relation filtering and instance availability are separate stages. Q005/Q025 require no reference mask here.', fontsize=6, color='#515960')
    return save_figure('F12', fig, {'a_accumulated': (.475, .94), 'b_per_query': (.01, .47)},
        ['F12_query_counts.csv', 'F12_stage_totals.csv'], dict(queries=25, original_query_order=d['qids'],
            count_unit='query-device occurrences for totals; devices per individual query', totals=t,
            stage_colors=dict(zip(STAGES, STAGE_COLORS)), relation_and_availability_separate=True))


def captions(s):
    means = ', '.join(f"{NAMES[r['method']]} {r['mean_iou_percent']:.2f}%" for r in s['method_distributions'])
    entity, relation, t = s['mechanisms']['entity'], s['mechanisms']['relation'], s['candidate_totals']
    return {
        'F10_query_performance': dict(title_zh='不同方法的空间关系引导实例检索性能分布',
            title_en='Query-wise performance distribution of spatial relation-guided instance retrieval.',
            caption_zh=f"(a) 25条查询按原顺序展示，Q005/Q025缺少可靠参考，标灰N/A；真实零值保留在色标中。(b) 23条有效查询逐查询IoU分布，均值为{means}；Ours在{len(s['ours_strict_wins'])}/23条中严格最高。箱体为Q1—Q3、中线为中位数、菱形为均值，须端为1.5 IQR范围内的实际极值；展示全部查询点，仅进行固定种子水平抖动。两阶段平均：先有效视角、后等权查询。参考为SAM辅助伪真值，非独立人工真值；查询可能共享设备或视角，不进行显著性检验。",
            caption_en=f"(a) All 25 queries retain their original order. Q005/Q025 lack reliable references and are gray N/A; genuine zeros remain on the color scale. (b) All 23 evaluated query IoUs are shown. Means: {means}. Ours is strictly highest on {len(s['ours_strict_wins'])}/23 queries. Boxes span Q1-Q3, center lines are medians, diamonds are means, and whiskers end at observations within 1.5 IQR. Jitter is horizontal only with a fixed seed. Metrics average eligible views first, then queries equally. References are SAM-assisted Pseudo-GT, not independent human GT. Queries can share devices/views; no significance test is performed."),
        'F11_mechanism_contribution': dict(title_zh='精细三维实体表达与空间关系约束的贡献分析',
            title_en='Contribution analysis of refined entity representation and spatial relation constraints.',
            caption_zh=f"(a,b) 同23条查询、同纵轴范围的有符号IoU差值。精细实体相对同可用性粗框平均{entity['mean_iou_gain_pp']:+.2f} pp，{entity['improved']}升/{entity['declined']}降/{entity['unchanged']}不变；关系约束平均{relation['mean_iou_gain_pp']:+.2f} pp，{relation['improved']}升/{relation['declined']}降/{relation['unchanged']}不变，保留所有负值和零值。(c) 四种配置的离散Precision/Recall均值，非PR曲线；箭头仅表示两个主要机制配置差异。精细实体Precision {entity['precision_gain_pp']:+.2f} pp、Recall {entity['recall_gain_pp']:+.2f} pp；关系约束Precision {relation['precision_gain_pp']:+.2f} pp、Recall {relation['recall_gain_pp']:+.2f} pp。空心all-33粗框使用不同可用性，仅作补充，不能当作单一机制对照。SAM辅助伪真值。",
            caption_en=f"(a,b) Signed IoU differences use the same 23-query order and axis range. Entity refinement versus availability-matched boxes averages {entity['mean_iou_gain_pp']:+.2f} pp ({entity['improved']} improved/{entity['declined']} declined/{entity['unchanged']} unchanged); relation constraints average {relation['mean_iou_gain_pp']:+.2f} pp ({relation['improved']}/{relation['declined']}/{relation['unchanged']}). All negatives and zeros remain. (c) Discrete configuration means, not a precision-recall curve. Arrows show only the two main configuration contrasts. Entity refinement changes precision/recall by {entity['precision_gain_pp']:+.2f}/{entity['recall_gain_pp']:+.2f} pp; relations change them by {relation['precision_gain_pp']:+.2f}/{relation['recall_gain_pp']:+.2f} pp. The hollow all-33 box point has different availability and is a supplement, not a single-mechanism contrast. Evaluation uses SAM-assisted Pseudo-GT."),
        'F12_candidate_reduction': dict(title_zh='空间关系约束下的工业设备候选筛选分析',
            title_en='Equipment candidate reduction through spatial relation constraints.',
            caption_zh=f"(a) 全25条查询累计类别候选{t['category_candidates']}→关系匹配{t['relation_targets']}→可用精细实例{t['fine_available']}，前一步减少{t['relation_reduction_percent']:.1f}%，后一步为{t['matched_fine_availability_percent']:.1f}%可用性，{t['unavailable']}次目标匹配无精细输出。这是查询—设备累计次数，不是独立设备数，也不是精度。(b) 完整25条逐查询整数计数，Q005/Q025不依赖图像参考因此仍纳入。Q006/Q007保留唯一目标；Q009/Q024保留多目标；Q010部分不可用，Q019有身份匹配但无精细输出。星号仅标示可用性缺失，不能解释为关系筛选错误。",
            caption_en=f"(a) Across all 25 queries, accumulated category candidates ({t['category_candidates']}) reduce to relation matches ({t['relation_targets']}) and available fine instances ({t['fine_available']}). Relation filtering reduces occurrences by {t['relation_reduction_percent']:.1f}%; subsequent fine-instance availability is {t['matched_fine_availability_percent']:.1f}%, with {t['unavailable']} matched occurrences unavailable. Totals count query-device occurrences, not distinct equipment or accuracy. (b) Integer stage counts for all queries, including reference-independent Q005/Q025. Q006/Q007 retain a unique target; Q009/Q024 retain multiple targets; Q010 has partial availability and Q019 has an identity match but no fine output. Asterisks denote availability limitations, not relation-filtering errors.")}


def replace_section(path, body):
    path = Path(path); start, end = '<!-- DATA_ANALYSIS_F10_F12_START -->', '<!-- DATA_ANALYSIS_F10_F12_END -->'
    text = path.read_text(encoding='utf-8') if path.exists() else ''
    section = start + '\n' + body.strip() + '\n' + end
    if start in text:
        i, j = text.index(start), text.index(end) + len(end); text = text[:i] + section + text[j:]
    else:
        text = text.rstrip() + '\n\n' + section + '\n'
    path.write_text(text, encoding='utf-8')


def publish(d, entries):
    s = d['stats']; caps = captions(s)
    manifest = read(ROOT / 'figures/manifest.json')
    for entry in entries:
        manifest = [m for m in manifest if m['figure'] != entry['figure']] + [entry]
    manifest.sort(key=lambda m: m['figure']); write(ROOT / 'figures/manifest.json', manifest)
    existing = read(ROOT / 'configs/captions.json')
    for m in manifest:
        if m['figure'] in caps:
            c = caps[m['figure']]; existing[m['figure']] = c
            (ROOT / 'figures' / m['figure'] / 'CAPTION.md').write_text(
                f"# {c['title_zh']}\n\n{c['title_en']}\n\n{c['caption_zh']}\n\n{c['caption_en']}\n", encoding='utf-8')
    write(ROOT / 'configs/captions.json', existing)
    present = [m for m in manifest if m['figure'] in caps]
    index = '|编号|内容|实验|文件|数据与来源|\n|---|---|---|---|---|\n'
    gallery = '## F10—F12：冻结实验数据分析\n\n只重读原有CSV/JSON并绘图，未运行新实验。图中文字与标记为可编辑矢量；PNG为450 dpi。\n\n'
    for m in present:
        n = m['figure']; c = caps[n]
        index += f"|{n[:3]}|{c['title_zh']}|{m['experiment']}|[PNG]({m['png']}) · [SVG]({m['svg']}) · [PDF]({m['pdf']})|[数据](figures/{n}/) · [来源](figures/{n}/sources.json)|\n"
        gallery += f"### {n}: {c['title_zh']}\n\n{c['title_en']}\n\n![{n}](../{m['png']})\n\n{c['caption_zh']}\n\n{c['caption_en']}\n\n[SVG](../{m['svg']}) · [PDF](../{m['pdf']}) · [独立子图](../figures/{n}/subplots/) · [数据/来源](../figures/{n}/sources.json)\n\n"
    replace_section(ROOT / 'FIGURE_INDEX.md', '## F10—F12 数据分析补充\n\n' + index + '\n绘图脚本：[plot_data_analysis.py](scripts/plot_data_analysis.py)。')
    replace_section(ROOT / 'docs/GALLERY.md', gallery)
    t = s['candidate_totals']; ent, rel = s['mechanisms']['entity'], s['mechanisms']['relation']
    report = f"""## F10—F12：冻结结果的描述性数据分析

本次仅使用E01/E02/E04已有CSV/JSON，未重训、重渲染、重运行查询、修改参考或预测阈值。原F04—F09保留。完整精度绘图数据及交叉校验位于[source_data/data_analysis](source_data/data_analysis/)，来源SHA256记录于每图sources.json。

**F10，E01逐查询分布。** 25列保留原查询顺序，Q005/Q025为无可靠参考的N/A，不能填零。箱图使用相同23条有效查询、44个有效视角；先视角后等权查询平均。四种方法均值依次为{', '.join(f"{NAMES[r['method']]} {r['mean_iou_percent']:.2f}%" for r in s['method_distributions'])}。IoU≥50%的查询数依次为{'、'.join(str(r['queries_iou_ge50']) for r in s['method_distributions'])}；Ours严格最高{len(s['ours_strict_wins'])}/23条。Q010中Ours仅{100 * float(d['e']['ours', 'Q010']['iou']):.2f}%，Q019为真实0，均保留。表中零值与显示四舍五入至0.0的微小正数可通过CSV区分。

**F11，E02机制贡献。** 相同查询/可用性下，精细实体IoU均值仅{ent['mean_iou_gain_pp']:+.2f}个百分点（{ent['improved']}升/{ent['declined']}降/{ent['unchanged']}不变），Precision {ent['precision_gain_pp']:+.2f}、Recall {ent['recall_gain_pp']:+.2f}个百分点；主要表现为降低污染并损失可见结构，而非普遍提高IoU。Q007受益，Q011/Q022明显下降，且后两条可能共享设备与评价图像。关系约束IoU均值{rel['mean_iou_gain_pp']:+.2f}个百分点（{rel['improved']}升/{rel['declined']}降/{rel['unchanged']}不变），Precision {rel['precision_gain_pp']:+.2f}、Recall {rel['recall_gain_pp']:+.2f}个百分点，优势主要体现为同类候选筛选。正负差值共用纵轴，未删除失败查询。离散Precision/Recall点不是PR曲线；all-33粗框可用性不同，仅作补充，无单机制箭头。

**F12，E04候选变化。** 全25条累计{t['category_candidates']}→{t['relation_targets']}→{t['fine_available']}次查询—设备候选，关系筛选减少{t['relation_reduction_percent']:.1f}%；后续精细实例可用性{t['matched_fine_availability_percent']:.1f}%。4次不可用出现在Q005/Q010/Q019/Q025，涉及{t['unique_unavailable_devices']}台独立设备。累计候选涉及{t['unique_category_devices']}台不同设备，不应把108次解释为108台。Q006/Q007筛选唯一目标，Q009/Q024保留多目标，Q010部分匹配无精细输出，Q019保留位置身份但不能返回精细实例。该计数是机制与可用性分析，不是定位准确率；不需要参考掩膜，故保留Q005/Q025。

**适用范围。** F10/F11基于SAM-assisted Pseudo-GT，未经独立人工真值认证；查询可共享设备和视角，仅作本集合描述性统计，不进行独立样本显著性检验。数量收缩本身不证明关系正确或分割更准确。正式人工GT与更独立的测试集仍为后续工作。

运行：`../saga_relags_v1/envs/saga/bin/python scripts/plot_data_analysis.py --figure all`；可改为`--figure F10`、`F11`、`F12`。仅CPU绘图，输出PNG/SVG/PDF、独立子图、CSV、双语图注、布局/来源和运行记录。图见[图集](docs/GALLERY.md)。
"""
    replace_section(ROOT / 'EXPERIMENT_REPORT.md', report)
    replace_section(ROOT / 'README.md', '''## Frozen-data analysis (F10-F12)

[Figures and captions](docs/GALLERY.md) · [Index](FIGURE_INDEX.md) · [Exact plotting data](source_data/data_analysis/)

```bash
../saga_relags_v1/envs/saga/bin/python scripts/plot_data_analysis.py --figure all
# Individual figures: --figure F10, --figure F11, or --figure F12
```

CPU-only analysis of frozen CSV/JSON, with no model or query execution. Run this script after legacy plot_figures.py/publish.py if rebuilding documentation, because the legacy generators recreate their six-figure index. Preserve the scientific outputs; new method experiments belong in a separate version.
''')


def scientific_snapshot():
    protected = {}
    for folder in sorted(ROOT.glob('E0*')) + sorted((ROOT / 'figures').glob('F0*')) + [ROOT / 'tables', ROOT / 'method_figure_assets']:
        for p in folder.rglob('*'):
            if p.is_file():
                st = p.stat(); protected[str(p)] = [st.st_size, st.st_mtime_ns]
    return protected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--figure', choices=['all', 'F10', 'F11', 'F12'], default='all')
    args = parser.parse_args(); start = time.perf_counter()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    run = DATA / 'runs' / stamp; run.mkdir(parents=True)
    shutil.copy2(__file__, run / 'plot_data_analysis.py')
    before = scientific_snapshot(); write(run / 'scientific_before.json', before)
    sources = {str(ROOT / p): dict(bytes=(ROOT / p).stat().st_size, sha256=sha(ROOT / p)) for p in INPUTS}
    write(run / 'inputs.json', sources)
    for rel in ['figures/manifest.json', 'configs/captions.json', 'README.md', 'FIGURE_INDEX.md', 'docs/GALLERY.md', 'EXPERIMENT_REPORT.md']:
        p = ROOT / rel; target = run / 'before' / rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p, target)
    write(run / 'command.json', dict(argv=sys.argv, cwd=str(Path.cwd()), python=sys.executable,
          start_utc=stamp, gpu_used=False, model_or_query_execution=False))
    try:
        d = analyze(); selected = list(FIGURES) if args.figure == 'all' else [args.figure]
        entries = [dict(F10=f10, F11=f11, F12=f12)[code](d) for code in selected]
        publish(d, entries)
        assert scientific_snapshot() == before, 'Frozen scientific data or earlier figures changed'
        assert all(sha(path) == meta['sha256'] for path, meta in sources.items())
        result = dict(status='passed', generated=selected, seconds=time.perf_counter()-start,
            protected_files=len(before), scientific_files_modified=0, source_hashes_verified=len(sources),
            summary_and_relation_crosschecks=True, saved_mechanism_delta_crosscheck=True,
            candidate_csv_json_and_identity_sets_crosscheck=True, gpu_used=False,
            numpy=np.__version__, matplotlib=matplotlib.__version__, python=sys.version,
            visual_review='pending separate inspection', run=str(run))
        write(run / 'result.json', result); write(DATA / 'latest_run.json', result)
        output = json.dumps(dict(result=result, distributions=d['stats']['method_distributions'],
            mechanisms=d['stats']['mechanisms'], candidate_totals=d['stats']['candidate_totals']), indent=2)
        (run / 'run.log').write_text(output + '\n', encoding='utf-8'); print(output, flush=True)
    except Exception:
        import traceback
        error = traceback.format_exc(); (run / 'run.log').write_text(error, encoding='utf-8')
        write(run / 'result.json', dict(status='failed', seconds=time.perf_counter()-start, error=error)); raise


if __name__ == '__main__':
    main()
