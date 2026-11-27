import os,shutil,subprocess,collections
from common import *
from plyfile import PlyData
import torch

for name in ['inputs','configs','outputs','logs','cache','docs/figures','evaluation/ground_truth','evaluation/metrics','evaluation/predictions']:(ROOT/name).mkdir(parents=True,exist_ok=True)
assert not (ROOT/'inputs/assets.json').exists()
protected={}
for base in [V2,ROOT.parent/'saga_relags_v1',PROJECT/'ReLaGS',PROJECT/'m0',PROJECT/'industrial_world_model',PROJECT/'outputs',ELI/'repos/LangSplat',ELI/'records',ELI/'outputs/gsle',ELI/'data/gsle_langsplat']:
    for p in base.rglob('*'):
        if not p.is_file() or any(s in p.parts for s in ['.git','__pycache__']):continue
        st=p.stat();protected[str(p)]=[st.st_size,st.st_mtime_ns]
write(ROOT/'inputs/protected_before.json',protected)
paths=dict(langsplat_source=str(ELI/'repos/LangSplat'),langsplat_python=str(ELI/'envs/gsle_langsplat/bin/python'),langsplat_models=[str(ELI/f'outputs/gsle/langsplat_{i}/chkpnt30000.pth') for i in [1,2,3]],autoencoder=str(ELI/'repos/LangSplat/autoencoder/ckpt/industrial_gsle/best_ckpt.pth'),language_features=str(ELI/'data/gsle_langsplat/language_features'),relags_source=str(PROJECT/'ReLaGS'),relags_python=str(PROJECT/'envs/relags/bin/python'),relags_graph=str(PROJECT/'outputs/relags_obb_repair_r1/08_scene_graph/data/model'),relags_scene=str(PROJECT/'outputs/relags_baseline/05_hierarchical_grouping/data/model'),thgs_source=str(ROOT/'third_party/THGS'),thgs_base_scene=str(PROJECT/'outputs/relags_baseline/01_gaussian_scene/data/model'),ours=str(V2/'world_model'),ours_python=str(ROOT.parent/'saga_relags_v1/envs/saga/bin/python'),native_ply=str(PROJECT/'data/gaussian_scene/original_3dgs/point_cloud/iteration_30000/point_cloud.ply'),clip_b16=str(PROJECT/'models/openclip_vit_b16/open_clip_pytorch_model.bin'))
for key,value in paths.items():
    for p in value if isinstance(value,list) else [value]:assert Path(p).exists(),(key,p)
versions={k:subprocess.check_output(['git','-C',paths[k],'rev-parse','HEAD'],text=True).strip() for k in ['langsplat_source','relags_source','thgs_source']}
critical=paths['langsplat_models']+[paths['autoencoder'],paths['native_ply'],str(Path(paths['relags_graph'])/'sai_nag_openseg.pt'),str(Path(paths['relags_graph'])/'jina_edges_predicted.pt'),str(V2/'world_model/scene_graph.json'),str(V2/'outputs/A/frozen_manifest.json')]
hashes={p:sha(p) for p in critical};write(ROOT/'inputs/assets.json',dict(paths=paths,versions=versions,hashes=hashes,selection='LangSplat final complete iteration30000 at all three levels + documented best AE epoch98; chosen before benchmark query outcomes',no_new_training=True))
for name in ['objects.json','categories.json','cameras.json','camera_split.json','m0_state.json']:shutil.copy2(V2/'inputs'/name,ROOT/'inputs'/name)
original=read(ELI/'records/camera_split.json');current=read(ROOT/'inputs/camera_split.json');assert set(original['train'])==set(current['train']) and set(original['test'])==set(current['test'])
raw=PlyData.read(paths['native_ply'])['vertex'].data;xyz=np.column_stack([raw[k] for k in ['x','y','z']]);language=[]
for p in paths['langsplat_models']:
    model,iteration=torch.load(p,map_location='cpu');assert iteration==30000;assert np.array_equal(model[1].numpy(),xyz);language.append(dict(path=p,iteration=iteration,gaussians=len(model[1]),latent_shape=list(model[7].shape),finite=bool(torch.isfinite(model[7]).all())))
T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform']);R=T[:3,:3];write(ROOT/'inputs/compatibility.json',dict(shared_training_images=len(original['train']),shared_heldout_images=len(original['test']),langsplat=language,industrial_transform=T.tolist(),linear_determinant=float(np.linalg.det(R)),orthogonality_error=float(np.abs(R@R.T-np.eye(3)).max()),raw_z_in_industrial=R[:,2].tolist(),protected_files=len(protected),gt='No independently confirmed fine query masks identified; historical automatic masks are excluded as truth'))
# Train-only THGS scene view, with original LangSplat semantics and unpruned 2DGS.
data=ROOT/'inputs/thgs_data';data.mkdir(exist_ok=True)
for name,target in [('images',ELI/'data/gsle_langsplat/images'),('sparse',ELI/'data/gsle_langsplat/sparse'),('language_features',Path(paths['language_features']))]:
    (data/name).symlink_to(target,target_is_directory=True)
model=ROOT/'outputs/thgs/model';(model/'point_cloud/iteration_30000').mkdir(parents=True,exist_ok=True)
(model/'point_cloud/iteration_30000/point_cloud.ply').symlink_to(Path(paths['thgs_base_scene'])/'point_cloud/iteration_30000/point_cloud.ply')
from argparse import Namespace
(model/'cfg_args').write_text(str(Namespace(source_path=str(data),model_path=str(model),images='images',eval=False,resolution=2,white_background=False,data_device='cpu',sh_degree=3)))
shutil.copy2(ROOT/'third_party/THGS/configs/lerf.yml',ROOT/'configs/thgs_official_lerf.yml')
for key,path in [('langsplat',ELI/'records/gsle/dataset.json'),('autoencoder',ELI/'records/gsle/autoencoder.json'),('language_validation',ELI/'records/gsle/language_parameter_identity_30000.json')]:shutil.copy2(path,ROOT/'inputs'/(key+'_source_record.json'))
print('ASSET AUDIT',versions,read(ROOT/'inputs/compatibility.json'),flush=True)
