"""Copy the final, portable data product. Never symlink input annotations/weights."""
import shutil
from .common import *


def run(ctx):
 root=ctx.path('package');nodes=read(ctx.path('M4','nodes.json'));observations=ctx.segmentation();copied={}
 def cp(source,relative):
  source=Path(source);dest=root/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);copied[str(relative)]=dict(bytes=dest.stat().st_size,sha256=sha(dest));return str(relative)
 cp(ctx.source('ply'),'geometry/full_native_3dgs.ply');cp(ctx.path('M2.6','semantic_native_3dgs.ply'),'geometry/semantic_native_3dgs.ply');cp(ctx.path('M2.6','gaussian_to_object.npy'),'geometry/gaussian_to_object.npy');labels=read(ctx.path('M2.6','label_lookup.json'))
 cp(ctx.source('clip'),'models/open_clip_pytorch_model.bin');cp(ctx.out/'config/m0_state.json','metadata/m0_snapshot.json');cp(ctx.out/'config/images.json','metadata/cameras.json');cp(ctx.out/'config/reference_cameras.json','metadata/reference_cameras.json');cp(ctx.out/'config/input_review.json','metadata/input_review.json');cp(ctx.path('M3.4','features.npz'),'semantics/features.npz');cp(ctx.path('M4','relations.json'),'graph/relations.json');cp(ctx.path('M4','pair_geometry.json'),'graph/pair_geometry.json');cp(ctx.path('M4','distance_matrix.npy'),'graph/distance_matrix.npy');cp(ctx.path('M4','relative_position_matrix.npy'),'graph/relative_position_matrix.npy');cp(ctx.path('M4','matrix_object_ids.json'),'graph/matrix_object_ids.json');cp(ctx.path('M3.1','model.json'),'semantics/clip_model.json');cp(ctx.path('M3.3','text_inputs.json'),'semantics/text_inputs.json');cp(ctx.config_path,'metadata/build_config.json');cp(ctx.out/'manifest.json','metadata/build_manifest.json')
 image_names=set();instances=[]
 for node in nodes:
  oid=node['object_id'];node['gaussian_indices']=cp(ctx.out/node['gaussian_indices'],f'objects/{oid}/gaussian_ids.npy');node['ply']=cp(ctx.out/node['ply'],f'objects/{oid}/instance.ply')
  for field,key in [('visual_feature','visual'),('text_feature','text')]:node[field]={'path':'semantics/features.npz','key':key,'row':node['feature_row']}
  node['views']=[]
  for r in observations[oid]:
   if not r['accepted']:continue
   im=ctx.image_map[r['image_id']];mask=cp(ctx.out/r['mask_path'],f'evidence/{oid}/{r["image_id"]}_mask.png');image='evidence/images/'+im['filename'];image_names.add(im['filename']);node['views'].append(dict(image_id=im['image_id'],image=image,mask=mask,view_quality=r['view_quality'],sam_predicted_iou=r['sam_predicted_iou']))
  node['multiview_features']=cp(ctx.path('M3.1',oid,'features.npy'),f'semantics/{oid}/view_features.npy');cp(ctx.path('M3.2',oid,'aggregation.json'),f'semantics/{oid}/aggregation.json');node['aggregation_metadata']=f'semantics/{oid}/aggregation.json';instances.append(node)
 for name in image_names:cp(ctx.source('images')/name,'evidence/images/'+name)
 for label in labels['objects']:label['gaussian_ids']=f'objects/{label["object_id"]}/gaussian_ids.npy'
 write(root/'geometry/label_lookup.json',labels);write(root/'graph/nodes.json',instances)
 graph=read(ctx.path('M4','scene_graph.json'));graph['nodes']=instances;write(root/'graph/scene_graph.json',graph)
 # Bundle the reader and the small existing native adapter, without M0 state or web files.
 shutil.copytree(Path(__file__).parent,root/'industrial_world_model',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 for file in ['__init__.py','settings.py','native_3dgs.py','spatial.py']:cp(ctx.project/'m0'/file,'m0/'+file)
 vendor=ctx.project/'m0/vendor/gaussian_splatting'
 for dirname in ['gaussian_renderer','scene','utils']:
  shutil.copytree(vendor/dirname,root/'m0/vendor/gaussian_splatting'/dirname,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
 for path in vendor.glob('*LICENSE*'):cp(path,'m0/vendor/gaussian_splatting/'+path.name)
 cp(vendor/'UPSTREAM.json','m0/vendor/gaussian_splatting/UPSTREAM.json')
 manifest=dict(format_version=1,method='M0-guided native 3DGS industrial world model, first version',m0_revision=ctx.state['revision'],units='sfm_relative',gaussian_id='Original source PLY vertex row',object_count=len(nodes),available_objects=sum(n['available'] for n in nodes),scene_ply='geometry/full_native_3dgs.ply',semantic_ply='geometry/semantic_native_3dgs.ply',gaussian_labels='geometry/gaussian_to_object.npy',nodes='graph/nodes.json',relations='graph/relations.json',features='semantics/features.npz',clip_checkpoint='models/open_clip_pytorch_model.bin',clip_arch=ctx.c['input']['clip_arch'],query_config=ctx.c['query'],prior_snapshot='metadata/m0_snapshot.json',cameras='metadata/cameras.json',requires_sam_for_loading_or_query=False,requires_original_m0_database=False,requires_original_experiment_paths=False,dependencies='Python 3.10, numpy, torch, open_clip_torch for queries; existing native 3DGS CUDA rasterizer, plyfile, scipy, Pillow for optional renders',files=copied)
 write(root/'manifest.json',manifest)
 (root/'README.md').write_text('''# Portable industrial world model

Run inside this folder with the existing compatible Python environment:

```bash
python -m industrial_world_model.model .
python -m industrial_world_model.model . --query '找到料架' --device cpu --output query.json
```

```python
from industrial_world_model.model import WorldModel
world = WorldModel('.')
result = world.query({'subject': '物料车', 'relation': 'left_of', 'object': '料架'})
node = world.get_object(result['matched_ids'][0])  # Check for an empty result first.
indices = world.gaussian_ids(node['object_id'])
# Optional CUDA render; only the packaged full native scene is loaded:
world.render(result['matched_ids'], image_id='frame_000221', output='query.png')
```

All object, mask, image, model and feature paths in the graph/manifest are relative to this folder. No SAM or object reconstruction is run during loading/query. Native render extensions remain environment dependencies. Unavailable objects retain their identity and failure reason; they do not generate artificial query results. Distances use SfM relative units. Similarities and internal reprojection IoU are not real probabilities or ground-truth accuracy.
''',encoding='utf-8')
 from .model import WorldModel
 world=WorldModel(root);assert len(world.nodes)==len(nodes)
 for node in world.nodes:assert len(world.gaussian_ids(node['object_id']))==node['gaussian_count']
 # Recheck immutable input hashes recorded at M1. This stage never writes sources.
 records=read(ctx.out/'manifest.json')['inputs'];checks=[]
 for row in records:
  path=ctx.project/row['path'];actual=sha(path);checks.append(dict(path=row['path'],expected=row['sha256'],actual=actual,unchanged=actual==row['sha256']))
 assert all(c['unchanged'] for c in checks),'Immutable build input changed during execution'
 write(root/'metadata/input_integrity.json',checks)
 return dict(objects=len(nodes),available=sum(n['available'] for n in nodes),copied_files=len(copied),copied_bytes=sum(r['bytes'] for r in copied.values()),standalone_reader_validated=True,immutable_inputs_unchanged=True,sam_not_needed_for_queries=True)
