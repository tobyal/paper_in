"""M0 RGB-only adapter around the unmodified, pinned native 3DGS renderer."""
import sys
from types import SimpleNamespace
import numpy as np
from .settings import GAUSSIANS, NATIVE_GS

sys.path.insert(0, str(NATIVE_GS))
import torch
from scene.gaussian_model import GaussianModel
from scene.cameras import MiniCam
from gaussian_renderer import render
from utils.graphics_utils import getWorld2View2, getProjectionMatrix

PIPELINE = SimpleNamespace(debug=False, compute_cov3D_python=False, convert_SHs_python=False)


def load_model():
    model = GaussianModel(3)
    model.load_ply(str(GAUSSIANS))
    assert model.get_scaling.shape[1] == 3, 'M0 requires native three-axis 3DGS'
    model.active_sh_degree = 3
    return model


def subset_model(base, ids):
    model = GaussianModel(3)
    model.active_sh_degree = base.active_sh_degree
    ids = torch.as_tensor(np.asarray(ids, dtype='int64'), device='cuda')
    for name in ('_xyz', '_features_dc', '_features_rest', '_opacity', '_scaling', '_rotation'):
        setattr(model, name, getattr(base, name)[ids])
    return model


def camera(width, height, rotation, translation, fovx, fovy):
    """rotation/translation are COLMAP world-to-camera (right, down, forward)."""
    near, far = .01, 100.
    view = torch.as_tensor(getWorld2View2(np.asarray(rotation).T, np.asarray(translation))).T.cuda()
    projection = getProjectionMatrix(znear=near, zfar=far, fovX=fovx, fovY=fovy).T.cuda()
    return MiniCam(width, height, fovy, fovx, near, far, view, view @ projection)


def render_rgb(view, model):
    # Native RGB rasterizer has no ReLaGS semantic/depth outputs or 2D covariance conversion.
    return render(view, model, PIPELINE, torch.zeros(3, device='cuda'))
