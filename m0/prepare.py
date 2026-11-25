"""Read ONLY RGB, COLMAP, original split and Gaussian geometry; generate fresh M0 assets."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from PIL import Image
from plyfile import PlyData
from .settings import ASSETS, PROJECT, IMAGES, COLMAP, SPLIT, GAUSSIANS, MODEL_DIR, NATIVE_GS, SAM_WEIGHTS


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def build():
    ASSETS.mkdir(parents=True, exist_ok=True)
    loader = NATIVE_GS / 'scene/colmap_loader.py'
    spec = importlib.util.spec_from_file_location('m0_colmap_loader', loader)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    cams = module.read_intrinsics_binary(str(COLMAP / 'cameras.bin'))
    views = module.read_extrinsics_binary(str(COLMAP / 'images.bin'))
    split = json.loads(SPLIT.read_text())
    train, test = set(split['train']), set(split['test'])
    assert not train & test, 'Train/test overlap'
    records = []
    thumbs = ASSETS / 'thumbs'; thumbs.mkdir(exist_ok=True)
    for v in sorted(views.values(), key=lambda v: v.name):
        path = IMAGES / v.name
        assert path.parent.resolve() == IMAGES.resolve() and path.is_file()
        cam = cams[v.camera_id]
        with Image.open(path) as im:
            width, height = im.size
            assert (width, height) == (cam.width, cam.height), (v.name, im.size, cam)
            thumb = im.convert('RGB'); thumb.thumbnail((240, 150)); thumb.save(thumbs / v.name, quality=82)
        assert cam.model in ('PINHOLE', 'SIMPLE_PINHOLE'), 'M0 requires undistorted pinhole images'
        fx, fy, cx, cy = cam.params if cam.model == 'PINHOLE' else (cam.params[0], cam.params[0], cam.params[1], cam.params[2])
        R = v.qvec2rotmat(); t = v.tvec; center = -R.T @ t
        assert (v.name in train) != (v.name in test), v.name
        records.append(dict(image_id=Path(v.name).stem, filename=v.name, width=width, height=height,
                            split='train' if v.name in train else 'heldout', camera_id=int(v.camera_id),
                            colmap_image_id=int(v.id), K=[[float(fx), 0, float(cx)], [0, float(fy), float(cy)], [0, 0, 1]],
                            world_to_camera_R=R.tolist(), world_to_camera_t=t.tolist(), center=center.tolist(),
                            forward=(R.T @ np.array([0., 0., 1.])).tolist(), sha256=sha(path)))
    assert len(records) == len(train) + len(test)
    ply = PlyData.read(str(GAUSSIANS))['vertex']
    assert all(f'scale_{i}' in ply.data.dtype.names for i in range(3)), 'Expected native 3DGS with three scales'
    xyz = np.column_stack([ply[x] for x in ('x', 'y', 'z')])
    ids = np.unique(np.linspace(0, len(xyz) - 1, min(24000, len(xyz))).astype(int))
    colors = np.clip(np.column_stack([ply[f'f_dc_{i}'][ids] for i in range(3)]) * .28209479177387814 + .5, 0, 1)
    points = dict(point_ids=ids.tolist(), xyz=xyz[ids].round(6).tolist(), rgb=(colors * 255).astype(int).tolist(),
                  total_gaussians=len(xyz), coordinate_frame='colmap_raw', units='sfm_relative', sampling='deterministic evenly spaced original Gaussian indices')
    (ASSETS / 'scene_points.json').write_text(json.dumps(points))
    (ASSETS / 'images.json').write_text(json.dumps(records))
    files = [SPLIT, COLMAP / 'cameras.bin', COLMAP / 'images.bin', COLMAP / 'points3D.bin', GAUSSIANS, MODEL_DIR / 'cfg_args', MODEL_DIR / 'cameras.json', SAM_WEIGHTS]
    provenance = dict(schema_version='m0-1.0', images=len(records), train=len(train), heldout=len(test),
                      source_files=[dict(path=str(p.relative_to(PROJECT)), bytes=p.stat().st_size, sha256=sha(p)) for p in files],
                      allowed_inheritance=['undistorted_rgb', 'colmap_cameras', 'original_train_test_split', 'original_native_3dgs', 'sam_weights'],
                      inherited_semantic_or_spatial_annotations=False,
                      pixel_coordinates='original undistorted image: x right, y down; integer pixel centers; xyxy boxes with exclusive right/bottom',
                      geometry_correspondence=dict(image_camera_dimensions='all exact', image_count=len(records), gaussian_frame='original COLMAP world frame', visual_confirmation_required=True))
    provenance['geometry_source'] = {**next(x for x in provenance['source_files'] if x['path']==str(GAUSSIANS.relative_to(PROJECT))),
                                     'representation':'native_3dgs','iteration':30000,'gaussians':len(xyz),'scale_dimensions':3}
    provenance['renderer'] = dict(name='official-3dgs',upstream=json.loads((NATIVE_GS/'UPSTREAM.json').read_text())['commit'])
    # V2 displays every finite Gaussian center, not the legacy 24k-point overview.
    from .spatial import initialize
    finite = np.isfinite(xyz).all(axis=1)
    display_ids = np.flatnonzero(finite)
    full_rgb = np.clip(np.column_stack([ply[f'f_dc_{i}'] for i in range(3)]) * .28209479177387814 + .5, 0, 1)
    xyz[finite].astype('<f4').tofile(ASSETS / 'positions.bin')
    (full_rgb[finite]*255).astype('uint8').tofile(ASSETS / 'colors.bin')
    np.save(ASSETS / 'display_indices.npy', display_ids)
    initial = initialize(xyz[finite], records)
    initial.update(count=int(finite.sum()), total_gaussians=len(xyz), representation='native 3DGS; all finite centers for scene overview/picking, SH degree 3 splatting for object navigation',
                   position_format='little-endian float32 xyz', color_format='uint8 rgb', units='sfm_relative')
    (ASSETS / 'initial_scene.json').write_text(json.dumps(initial, indent=2))
    provenance['schema_version'] = 'm0-2.0'
    (ASSETS / 'source_manifest.json').write_text(json.dumps(provenance, indent=2))
    print(json.dumps(initial, indent=2))


if __name__ == '__main__': build()
