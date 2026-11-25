#!/usr/bin/env python3
"""Display actual predicted edges on the fixed cameras; never alter graph inference."""
import argparse, importlib.util, json, pathlib
import numpy as np
import torch
from PIL import Image, ImageDraw
from plyfile import PlyData

ROOT = pathlib.Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--audit', required=True)
p.add_argument('--gaussians', required=True)
p.add_argument('--output', required=True)
p.add_argument('--levels', type=int, nargs='+', default=[2,3])
a = p.parse_args()
source, out = pathlib.Path(a.audit), pathlib.Path(a.output)
data, vis = out/'data/camera_projections', out/'visualizations/camera_projections'
data.mkdir(parents=True, exist_ok=True)
vis.mkdir(parents=True, exist_ok=True)
spec = importlib.util.spec_from_file_location('colmap_loader', ROOT/'ReLaGS/scene/colmap_loader.py')
colmap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(colmap)
cameras = colmap.read_intrinsics_binary(ROOT/'data/colmap/sparse/0/cameras.bin')
images = {x.name: x for x in colmap.read_extrinsics_binary(ROOT/'data/colmap/sparse/0/images.bin').values()}
refs = json.loads((ROOT/'configs/reference_views.json').read_text())
width, height = refs['render_width'], refs['render_height']
vertices = PlyData.read(a.gaussians)['vertex'].data
xyz = np.stack([vertices[k] for k in ['x', 'y', 'z']], axis=1).astype(np.float64)
records = []
for level in a.levels:
    inputs = torch.load(source/f'level_{level}_graph_inputs.pt', map_location='cpu')
    pred = torch.load(source/f'level_{level}_edge_predictions.pt', map_location='cpu')
    pre = torch.load(source/f'level_{level}_pre_obb.pt', map_location='cpu')
    centered = np.asarray(pre['points_centered'], dtype=np.float64)
    assert centered.shape == xyz.shape
    differences = xyz - centered
    translation = differences.mean(0)
    residual = float(np.abs(differences - translation).max())
    assert residual < 1e-4, f'Unexpected point correspondence: {residual}'
    centers = np.asarray(inputs['centers'], dtype=np.float64) + translation
    ids = np.asarray(inputs['original_cluster_ids'], dtype=np.int64)
    src, dst = np.asarray(pred['src'], dtype=np.int64), np.asarray(pred['dst'], dtype=np.int64)
    similarities = np.asarray(pred['relation_similarities'])
    classes = similarities.argmax(1)
    confidence = similarities[np.arange(len(src)), classes]
    level_records = []
    for name in refs['image_names']:
        camera_image = images[name]
        intr = cameras[camera_image.camera_id]
        assert intr.model == 'PINHOLE'
        fx, fy, cx, cy = intr.params
        points_camera = centers @ colmap.qvec2rotmat(camera_image.qvec).T + camera_image.tvec
        depth = points_camera[:, 2]
        safe_depth = np.where(np.abs(depth) > 1e-12, depth, np.nan)
        uv = np.column_stack([(fx*points_camera[:, 0]/safe_depth+cx)*width/intr.width,
                              (fy*points_camera[:, 1]/safe_depth+cy)*height/intr.height])
        visible = (depth > 0) & np.isfinite(uv).all(1) & (uv[:, 0] >= 0) & (uv[:, 0] < width) & (uv[:, 1] >= 0) & (uv[:, 1] < height)
        candidate = np.flatnonzero(visible[src] & visible[dst])
        selected = candidate[np.argsort(-confidence[candidate], kind='stable')[:20]]
        stem = pathlib.Path(name).stem
        np.savez_compressed(data/f'level_{level}_{stem}.npz', cluster_ids=ids,
                            projected_centers=uv, camera_depth=depth, in_frustum=visible,
                            edge_source_rows=src, edge_target_rows=dst,
                            eligible_edge_indices=candidate, displayed_edge_indices=selected,
                            centered_to_original_translation=translation)
        with Image.open(ROOT/'data/images'/name) as im:
            canvas = im.convert('RGB').resize((width, height))
        draw = ImageDraw.Draw(canvas)
        for edge in selected:
            start, end = uv[src[edge]], uv[dst[edge]]
            draw.line([tuple(start), tuple(end)], fill=(255, 210, 30), width=2)
            direction = end - start
            length = np.linalg.norm(direction)
            if length > 12:
                unit = direction/length
                side = np.array([-unit[1], unit[0]])
                draw.polygon([tuple(end), tuple(end-9*unit+4*side), tuple(end-9*unit-4*side)], fill=(255, 210, 30))
        selected_nodes = np.unique(np.concatenate([src[selected], dst[selected]]))
        for row in selected_nodes:
            x, y = uv[row]
            draw.ellipse([x-3, y-3, x+3, y+3], fill=(255, 70, 70))
            draw.text((x+4, y+3), str(ids[row]), fill='white', stroke_width=1, stroke_fill='black')
        caption = f'L{level}: top {len(selected)} of {len(candidate)} in-frustum edges; no occlusion test'
        draw.rectangle([0, 0, width, 18], fill='black')
        draw.text((4, 2), caption, fill='white')
        canvas.save(vis/f'level_{level}_{stem}.png')
        displayed = [{'edge_index': int(e), 'source_id': int(ids[src[e]]), 'target_id': int(ids[dst[e]]),
                      'top1_relation': pred['relation_names'][classes[e]], 'cosine_similarity': float(confidence[e])} for e in selected]
        level_records.append({'image': name, 'in_frustum_nodes': int(visible.sum()), 'in_frustum_edges': len(candidate), 'displayed_edges': displayed})
    records.append({'level': level, 'centered_to_original_translation': translation.tolist(),
                    'translation_reconstruction_max_error': residual, 'views': level_records})
(out/'metrics/graph_projection_summary.json').write_text(json.dumps({
    'purpose': 'Fixed-camera display of actual GNN output; no graph or query changes',
    'limitations': 'At most 20 highest-cosine edges with both centers in camera frustum. No occlusion test. Full graph and raw projections retained. Cosine similarity is not a calibrated probability.',
    'levels': records}, indent=2))
print(json.dumps({'status': 'exported', 'levels': len(records), 'reference_views_per_level': len(refs['image_names'])}))
