#!/usr/bin/env python3
"""Validate F10-F12 without executing models, queries, or scientific pipelines."""
from pathlib import Path
import json
import re
import subprocess
import xml.etree.ElementTree as ET
from PIL import Image
from plot_data_analysis import ROOT, DATA, FIGURES, read, write, sha, scientific_snapshot


def main():
    latest = read(DATA / 'latest_run.json')
    assert latest['status'] == 'passed'
    before = read(Path(latest['run']) / 'scientific_before.json')
    assert scientific_snapshot() == before, 'Scientific source or F04-F09 changed'
    project = ROOT.parents[1]
    historical = read(ROOT / 'source_data/protected_before.json')
    for path, expected in historical.items():
        st = (project / path).stat()
        assert [st.st_size, st.st_mtime_ns] == expected, path
    bench = ROOT.parent / 'relational_retrieval_benchmark'
    locks = [(bench / 'configs', bench / 'configs/FROZEN.json'),
             (bench, bench / 'evaluation/pseudo_ground_truth/REFERENCE_FROZEN.json'),
             (project, ROOT / 'configs/FROZEN.json')]
    for base, lock in locks:
        for rel, expected in read(lock)['sha256'].items():
            assert sha(base / rel) == expected, (str(lock), rel)
    prior = read(ROOT / 'source_data/final_validation.json')
    assert prior['status'] == 'passed'
    for f in prior['figures']:
        if f['figure'].startswith('F0'):
            p = ROOT / 'figures' / f['figure'] / (f['figure'] + '.png')
            assert sha(p) == f['png_sha256'], str(p)
    manifest = read(ROOT / 'figures/manifest.json')
    assert len(manifest) == 9 and len({m['figure'] for m in manifest}) == 9
    figures = []; review = ROOT / 'review/data_analysis'; review.mkdir(parents=True, exist_ok=True)
    for name in FIGURES.values():
        folder = ROOT / 'figures' / name
        layout = read(folder / 'layout.json')
        assert layout['dpi'] == 450 and 170 <= layout['width_mm'] <= 180
        png = folder / (name + '.png')
        im = Image.open(png); im.verify(); im = Image.open(png)
        assert abs(im.info['dpi'][0] - 450) < .1
        assert im.width == 3186 and abs(im.width / 450 * 25.4 - layout['width_mm']) < .01
        svg = ET.parse(folder / (name + '.svg'))
        texts = svg.findall('.//{http://www.w3.org/2000/svg}text'); assert len(texts) > 30
        for p, record in read(folder / 'sources.json').items():
            assert Path(p).stat().st_size == record['bytes'] and sha(p) == record['sha256'], p
        pdf = folder / (name + '.pdf')
        info = subprocess.check_output(['pdfinfo', str(pdf)], text=True)
        assert re.search(r'Pages:\s+1\b', info)
        width, height = map(float, re.search(r'Page size:\s+([\d.]+) x ([\d.]+)', info).groups())
        assert abs(width / 72 * 25.4 - layout['width_mm']) < .02
        text = subprocess.check_output(['pdftotext', '-layout', str(pdf), '-'], text=True)
        # Poppler splits rotated query labels into one glyph per line.
        raw = subprocess.check_output(['pdftotext', '-raw', str(pdf), '-'], text=True)
        compact = re.sub(r'\s+', '', raw)
        assert all(q in compact for q in ['Q001', 'Q024', 'Q019'])
        fonts = subprocess.check_output(['pdffonts', str(pdf)], text=True)
        assert 'TrueType' in fonts and 'DejaVuSans' in fonts
        images = subprocess.check_output(['pdfimages', '-list', str(pdf)], text=True)
        assert not re.search(r'^\s*1\s+\d+\s+image', images, re.M), 'Unexpected rasterized PDF plot'
        (review / (name + '_pdfinfo.txt')).write_text(info, encoding='utf-8')
        (review / (name + '_pdftotext.txt')).write_text(text, encoding='utf-8')
        subprocess.run(['pdftoppm', '-r', '150', '-singlefile', '-png', str(pdf), str(review / name)], check=True)
        p = Image.open(review / (name + '.png')).convert('RGB')
        p.save(review / (name + '.jpg'), quality=95)
        p.convert('L').save(review / (name + '_gray.jpg'), quality=95)
        panels = []
        for panel in layout['subplot_vertical_bounds']:
            for suffix in ['png', 'svg', 'pdf']:
                assert (folder / 'subplots' / (panel + '.' + suffix)).stat().st_size > 1000
            ET.parse(folder / 'subplots' / (panel + '.svg'))
            Image.open(folder / 'subplots' / (panel + '.png')).verify()
            panels.append(panel)
        figures.append(dict(figure=name, width_mm=layout['width_mm'], png_size=list(im.size),
            png_sha256=sha(png), pdf_sha256=sha(pdf), svg_text_elements=len(texts),
            pdf_vector_only=True, pdf_embedded_truetype=True, subplots=panels))
    links = 0
    for p in [ROOT / 'README.md', ROOT / 'FIGURE_INDEX.md', ROOT / 'EXPERIMENT_REPORT.md', ROOT / 'docs/GALLERY.md']:
        for link in re.findall(r'\]\(([^)]+)\)', p.read_text(encoding='utf-8')):
            if '://' not in link:
                assert (p.parent / link.split('#')[0]).exists(), (str(p), link)
                links += 1
    result = dict(status='passed', frozen_current_experiment_files=len(before), frozen_historical_files=len(historical),
        changed_scientific_files=0, critical_source_locks_passed=True, original_F04_F09_png_hashes_unchanged=True,
        data_crosschecks=latest, figures=figures, links_checked=links,
        GPU_used=False, model_or_query_execution=False,
        visual_review='See visual_review.json; automated structure checks do not replace visual inspection.')
    write(DATA / 'validation.json', result)
    print(json.dumps(dict(status='passed', historical_files=len(historical), current_files=len(before),
        figures=len(figures), subplots=sum(len(f['subplots']) for f in figures), links=links), indent=2))


if __name__ == '__main__':
    main()
