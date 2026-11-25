"""Read-only native 3DGS RGB rendering at an original COLMAP camera."""
import argparse
import json
import math
import numpy as np
from PIL import Image
from .settings import ASSETS


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('image_id'); args = parser.parse_args()
    images = json.loads((ASSETS / 'images.json').read_text()); v = next(x for x in images if x['image_id'] == args.image_id)
    import torch
    from .native_3dgs import load_model,camera,render_rgb
    g = load_model()
    k = v['K']; w, h = round(v['width']/2), round(v['height']/2)
    # Official renderer uses centered intrinsics. Check rather than silently shifting rays.
    assert abs(k[0][2]-v['width']/2) < 1 and abs(k[1][2]-v['height']/2) < 1, 'Off-center camera requires explicit renderer adaptation'
    view = camera(w,h,v['world_to_camera_R'],v['world_to_camera_t'],
                  2*math.atan(v['width']/(2*k[0][0])),2*math.atan(v['height']/(2*k[1][1])))
    with torch.inference_mode(): result = render_rgb(view,g)
    out = ASSETS / 'renders'; out.mkdir(exist_ok=True)
    pixels = (result['render'].clamp(0, 1).permute(1, 2, 0).cpu().numpy()*255+.5).astype('uint8')
    Image.fromarray(pixels).save(out / (args.image_id + '.jpg'), quality=94)
    metadata=dict(image_id=args.image_id,width=w,height=h,renderer='official-3dgs',gaussians=len(g.get_xyz),
                  visible_gaussians=int(result['visibility_filter'].sum()),inherited_semantics=False,
                  outputs=['RGB'],depth_available=False)
    (out/(args.image_id+'.json')).write_text(json.dumps(metadata,indent=2))
    print(json.dumps(metadata))


if __name__ == '__main__': main()
