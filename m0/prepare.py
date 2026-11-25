"""Read ONLY RGB, COLMAP, original split and Gaussian geometry; generate fresh M0 assets."""
import hashlib
import importlib.util
import json
from pathlib import Path
import numpy as np
from PIL import Image
from plyfile import PlyData
from .settings import ASSETS, PROJECT, IMAGES, COLMAP, SPLIT, GAUSSIANS, BASE_GAUSSIANS, SAM_WEIGHTS


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''): h.update(b)
    return h.hexdigest()


def build():
    ASSETS.mkdir(parents=True, exist_ok=True)
    loader = PROJECT / 'ReLaGS/scene/colmap_loader.py'
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
    xyz = np.column_stack([ply[x] for x in ('x', 'y', 'z')])
    ids = np.unique(np.linspace(0, len(xyz) - 1, min(24000, len(xyz))).astype(int))
    colors = np.clip(np.column_stack([ply[f'f_dc_{i}'][ids] for i in range(3)]) * .28209479177387814 + .5, 0, 1)
    points = dict(point_ids=ids.tolist(), xyz=xyz[ids].round(6).tolist(), rgb=(colors * 255).astype(int).tolist(),
                  total_gaussians=len(xyz), coordinate_frame='colmap_raw', units='sfm_relative', sampling='deterministic evenly spaced original Gaussian indices')
    (ASSETS / 'scene_points.json').write_text(json.dumps(points))
    (ASSETS / 'images.json').write_text(json.dumps(records))
    files = [SPLIT, COLMAP / 'cameras.bin', COLMAP / 'images.bin', GAUSSIANS, BASE_GAUSSIANS, SAM_WEIGHTS]
    provenance = dict(schema_version='m0-1.0', images=len(records), train=len(train), heldout=len(test),
                      source_files=[dict(path=str(p.relative_to(PROJECT)), bytes=p.stat().st_size, sha256=sha(p)) for p in files],
                      allowed_inheritance=['undistorted_rgb', 'colmap_cameras', 'original_train_test_split', 'base_2dgs', 'mwp_geometry', 'sam_weights'],
                      inherited_semantic_or_spatial_annotations=False,
                      pixel_coordinates='original undistorted image: x right, y down; integer pixel centers; xyxy boxes with exclusive right/bottom',
                      geometry_correspondence=dict(image_camera_dimensions='all exact', image_count=len(records), gaussian_frame='original COLMAP world frame', visual_confirmation_required=True))
    (ASSETS / 'source_manifest.json').write_text(json.dumps(provenance, indent=2))
    print(json.dumps(provenance, indent=2))


if __name__ == '__main__': build()
