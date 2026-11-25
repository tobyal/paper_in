import os
from pathlib import Path

PROJECT = Path(os.environ.get('M0_PROJECT', Path(__file__).resolve().parents[1])).resolve()
ROOT = Path(os.environ.get('M0_DATA', PROJECT / 'industrial_scene_prior')).resolve()
ASSETS = ROOT / '.assets'
IMAGES = PROJECT / 'data/images'
COLMAP = PROJECT / 'data/colmap/sparse/0'
SPLIT = PROJECT / 'data/scene_information/camera_split.json'
GAUSSIANS = PROJECT / 'outputs/relags_baseline/03_gaussian_pruning/data/model/point_cloud/iteration_0/point_cloud.ply'
BASE_GAUSSIANS = PROJECT / 'outputs/relags_baseline/01_gaussian_scene/data/model/point_cloud/iteration_30000/point_cloud.ply'
SAM_WEIGHTS = PROJECT / 'models/sam/sam_vit_h_4b8939.pth'
STATIC = Path(__file__).parent / 'static'

