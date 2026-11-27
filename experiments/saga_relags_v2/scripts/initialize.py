"""Freeze provenance and read-only dependencies before v2 processing."""
from pathlib import Path
import sys,shutil,datetime
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
from plyfile import PlyData

for name in ['inputs','outputs/A','outputs/B','outputs/C','outputs/D','outputs/validation','logs','docs/figures','world_model']:
    (ROOT/name).mkdir(parents=True,exist_ok=True)
assert not (ROOT/'inputs/provenance.json').exists(), 'Initialization is intentionally not destructive/reentrant'
protected={}
for base in [V1,PROJECT/'outputs',PROJECT/'m0',PROJECT/'industrial_world_model',PROJECT/'ReLaGS']:
    for p in base.rglob('*'):
        if p.is_file() and '.git' not in p.parts and '__pycache__' not in p.parts:
            s=p.stat();protected[str(p.relative_to(PROJECT))]=[s.st_size,s.st_mtime_ns]
write(ROOT/'inputs/protected_before.json',protected)
for name in ['m0_state.json','objects.json','categories.json','cameras.json','training_cameras.json','manifest.json','camera_split.json']:
    shutil.copy2(V1/'inputs'/name,ROOT/'inputs'/name)
objects=read(ROOT/'inputs/objects.json');assert len(objects)==33
state=read(ROOT/'inputs/m0_state.json');assert state['revision']==29
checkpoint=V1/'outputs/A/saga_model/point_cloud/iteration_10000'
critical=[original_ply(),checkpoint/'contrastive_feature_point_cloud.ply',checkpoint/'scale_gate.pt',
          checkpoint/'training_state.pt',V1/'outputs/A/saga_model/all_mask_scales.npy',
          V1/'inputs/m0_state.json',V1/'inputs/geometry/original_gaussian_ids.npy']
hashes={str(p.relative_to(PROJECT)):sha(p) for p in critical}
raw=PlyData.read(original_ply())['vertex'].data
features=PlyData.read(checkpoint/'contrastive_feature_point_cloud.ply')['vertex'].data
xyz=np.column_stack([raw[k] for k in ['x','y','z']])
assert np.array_equal(np.column_stack([features[k] for k in ['x','y','z']]),xyz)
assert np.array_equal(np.load(V1/'inputs/geometry/original_gaussian_ids.npy'),np.arange(len(raw)))
assert np.array_equal(np.load(V1/'inputs/geometry/xyz_raw.npy'),xyz)
provenance=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    v1=str(V1),checkpoint=str(checkpoint),checkpoint_hashes=hashes,m0_revision=29,
    m0_status=state['scene']['status'],human_confirmation_not_inferred=True,native_gaussians=len(raw),
    gaussian_xyz_and_ids_exactly_equal=True,objects=len(objects),training_frozen=True,
    readonly_references=['v1 environment','v1 SAGA source and checkpoint','v1 candidate Gaussian IDs and geometry','v1 successful instances','original RGB and hybrid full-scene observations'],
    protected_files=len(protected))
write(ROOT/'inputs/provenance.json',provenance)
hybrid=PROJECT/read(ROOT/'inputs/manifest.json')['hybrid_observations']
views=read(hybrid/'selected_views.json')
npz=next((hybrid/'objects'/objects[0]['object_id']/'visibility').glob('*.npz'))
a=np.load(npz);print('VISIBILITY_SCHEMA',[(k,a[k].shape,str(a[k].dtype)) for k in a.files],flush=True)
print('OBJECTS',[(o['object_id'],o['name_zh'],len(views.get(o['object_id'],[]))) for o in objects],flush=True)
print('PROVENANCE',json.dumps(provenance,ensure_ascii=False),flush=True)
