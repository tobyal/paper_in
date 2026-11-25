import os
from pathlib import Path

PROJECT = Path(os.environ.get('M0_PROJECT', Path(__file__).resolve().parents[1])).resolve()
ROOT = Path(os.environ.get('M0_DATA', PROJECT / 'industrial_scene_prior_3dgs')).resolve()
ASSETS = ROOT / '.assets'
IMAGES = PROJECT / 'data/images'
COLMAP = PROJECT / 'data/colmap/sparse/0'
SPLIT = PROJECT / 'data/scene_information/camera_split.json'
MODEL_DIR = PROJECT / 'data/gaussian_scene/original_3dgs'
GAUSSIANS = MODEL_DIR / 'point_cloud/iteration_30000/point_cloud.ply'
NATIVE_GS = Path(__file__).parent / 'vendor/gaussian_splatting'
SAM_WEIGHTS = PROJECT / 'models/sam/sam_vit_h_4b8939.pth'
STATIC = Path(__file__).parent / 'static'

