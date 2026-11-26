"""Explicit, reversible data-interface patches; preserve official SAGA losses."""
from pathlib import Path
import difflib,json
ROOT=Path(__file__).resolve().parents[1];repo=ROOT/'third_party/SegAnyGAussians';backups=ROOT/'docs/upstream_original';backups.mkdir(parents=True,exist_ok=True)
def change(name,edits):
    p=repo/name;backup=backups/name;backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():backup.write_bytes(p.read_bytes())
    before=backup.read_text();after=before
    for old,new in edits:
        assert old in after,(name,old);after=after.replace(old,new)
    p.write_text(after)
    patch=ROOT/'docs/patches'/Path(name).with_suffix('.patch');patch.parent.mkdir(parents=True,exist_ok=True)
    patch.write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/'+name,tofile='b/'+name)))

change('extract_segment_everything_masks.py',[
 ('        img = cv2.imread(os.path.join(IMAGE_DIR, path))','        if os.path.exists(os.path.join(OUTPUT_DIR, name+".pt")):\n            continue\n        img = cv2.cvtColor(cv2.imread(os.path.join(IMAGE_DIR, path)), cv2.COLOR_BGR2RGB)'),
 ('torch.save(masks, os.path.join(OUTPUT_DIR, name+\'.pt\'))','torch.save(masks.cpu(), os.path.join(OUTPUT_DIR, name+\'.pt\'))')])
change('utils/camera_utils.py',[
 ('resolution = round(orig_w/(resolution_scale * args.resolution)), round(orig_h/(resolution_scale * args.resolution))','resolution = int(orig_w/(resolution_scale * args.resolution)), int(orig_h/(resolution_scale * args.resolution))'),
 ('cx=cam_info.cx, cy=cam_info.cy,','cx=(cam_info.cx * resolution[0] / orig_w + 0.5) if cam_info.cx is not None else None, cy=(cam_info.cy * resolution[1] / orig_h + 0.5) if cam_info.cy is not None else None,')])
change('scene/dataset_readers.py',[
 ('image_name.split(\'.\')[0] + ".pt"))','image_name.split(\'.\')[0] + ".pt"), map_location="cpu")')])
print('Applied documented RGB, CPU tensor serialization/resume and exact camera-principal-point adaptations.')
change('train_contrastive_feature.py',[
 ('import os\n','import os\nimport saga_hooks\n'),
 ('    for iteration in range(first_iter, opt.iterations + 1):','    saga_hooks.initialize(feature_gaussians, scale_gate, scene, opt, all_scales)\n    first_iter, viewpoint_stack = saga_hooks.restore(feature_gaussians, scale_gate, scene)\n    for iteration in range(first_iter, opt.iterations + 1):'),
 ('        iter_end.record()','        iter_end.record()\n        saga_hooks.record(iteration, feature_gaussians, scale_gate, scene, opt, loss, cosine_pos, cosine_neg, rendered_feature_norm, viewpoint_stack)')])
print('Added exact KNN cache, frozen geometry gradient guard, real loss logs and resumable checkpoints; contrastive loss, feature smoothing and scale gating expressions unchanged.')
