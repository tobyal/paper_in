"""Read-only official 2DGS rendering; no Scene constructor and no semantic loaders."""
import argparse
import json
import math
import sys
import numpy as np
from PIL import Image
from .settings import PROJECT, ASSETS, GAUSSIANS


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('image_id'); args = parser.parse_args()
    images = json.loads((ASSETS / 'images.json').read_text()); v = next(x for x in images if x['image_id'] == args.image_id)
    sys.path.insert(0, str(PROJECT / 'ReLaGS'))
    import torch
    from scene import GaussianModel
    from scene.cameras import Camera
    from gaussian_renderer import render
    from arguments import PipelineParams
    g = GaussianModel(3); g.load_ply(str(GAUSSIANS)); g.active_sh_degree = 3
    k = v['K']; w, h = round(v['width']/2), round(v['height']/2)
    # Official renderer uses centered intrinsics. Check rather than silently shifting rays.
    assert abs(k[0][2]-v['width']/2) < 1 and abs(k[1][2]-v['height']/2) < 1, 'Off-center camera requires explicit renderer adaptation'
    camera = Camera(colmap_id=v['colmap_image_id'], R=np.asarray(v['world_to_camera_R']).T, T=np.asarray(v['world_to_camera_t']),
                    FoVx=2*math.atan(v['width']/(2*k[0][0])), FoVy=2*math.atan(v['height']/(2*k[1][1])),
                    image=None, gt_alpha_mask=None, image_name=args.image_id, uid=0, width=w, height=h, data_device='cpu')
    with torch.inference_mode(): result = render(camera, g, PipelineParams(argparse.ArgumentParser()), torch.zeros(3, device='cuda'))
    out = ASSETS / 'renders'; out.mkdir(exist_ok=True)
    pixels = (result['render'].clamp(0, 1).permute(1, 2, 0).cpu().numpy()*255+.5).astype('uint8')
    Image.fromarray(pixels).save(out / (args.image_id + '.jpg'), quality=94)
    np.savez_compressed(out / (args.image_id + '_geometry.npz'), depth=result['surf_depth'].cpu().numpy(), alpha=result['rend_alpha'].cpu().numpy())
    print(json.dumps(dict(image_id=args.image_id, width=w, height=h, inherited_semantics=False)))


if __name__ == '__main__': main()
