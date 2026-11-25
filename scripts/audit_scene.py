#!/usr/bin/env python3
import importlib.util,json,pathlib,sys
import numpy as np
from PIL import Image,ImageDraw
ROOT=pathlib.Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/relags_baseline/00_data_check'
def dump(p,d):p.write_text(json.dumps(d,indent=2,ensure_ascii=False)+'\n')
spec=importlib.util.spec_from_file_location('colmap_reader',ROOT/'external/2d-gaussian-splatting/scene/colmap_loader.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
cameras=m.read_intrinsics_binary(ROOT/'data/colmap/sparse/0/cameras.bin')
views=m.read_extrinsics_binary(ROOT/'data/colmap/sparse/0/images.bin')
xyz,rgb,err=m.read_points3D_binary(ROOT/'data/colmap/sparse/0/points3D.bin')
ordered=sorted(views.values(),key=lambda v:v.name)
centers=np.stack([-m.qvec2rotmat(v.qvec).T@v.tvec for v in ordered])
split=json.loads((ROOT/'data/scene_information/camera_split.json').read_text())
reference=json.loads((ROOT/'configs/reference_views.json').read_text())
frames=[];dims={}
for name in sorted(split['train']+split['test']):
    p=ROOT/'data/images'/name
    with Image.open(p) as im:
        im.verify()
    with Image.open(p) as im:dims[name]=list(im.size)
assert len(set(tuple(v) for v in dims.values()))==1
assert set(v.name for v in ordered)==set(dims)
canvas=Image.new('RGB',(4*384,2*(216+28)),(245,245,245));draw=ImageDraw.Draw(canvas)
for i,name in enumerate(reference['image_names']):
    with Image.open(ROOT/'data/images'/name) as im:tile=im.convert('RGB').resize((384,216),Image.Resampling.LANCZOS)
    x=(i%4)*384;y=(i//4)*244;canvas.paste(tile,(x,y));draw.text((x+8,y+220),name,fill=(20,20,20))
canvas.save(OUT/'visualizations/reference_rgb_contact_sheet.jpg',quality=95)
trajectory={'image_names':[v.name for v in ordered],'camera_centers':centers.tolist(),'qvec_world_to_camera':[v.qvec.tolist() for v in ordered],'tvec_world_to_camera':[v.tvec.tolist() for v in ordered]}
dump(OUT/'data/camera_trajectory.json',trajectory)
np.savez_compressed(OUT/'data/scene_coordinates.npz',sfm_xyz=xyz,sfm_rgb=rgb,camera_centers=centers,image_names=np.array(trajectory['image_names']))
with (OUT/'visualizations/camera_trajectory.ply').open('w') as f:
    f.write('ply\nformat ascii 1.0\nelement vertex '+str(len(centers))+'\nproperty float x\nproperty float y\nproperty float z\nproperty uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n')
    for v,c in zip(ordered,centers):f.write(' '.join(map(str,c))+(' 240 90 30\n' if v.name in split['test'] else ' 30 100 240\n'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig=plt.figure(figsize=(12,7));ax=fig.add_subplot(111,projection='3d')
idx=np.linspace(0,len(xyz)-1,min(35000,len(xyz))).astype(int)
ax.scatter(*xyz[idx].T,c=rgb[idx]/255,s=.5,alpha=.35)
ax.plot(*centers.T,color='#e64b35',linewidth=1)
ax.scatter(*centers[::8].T,color='blue',s=8,label='44 held-out views')
ax.set(xlabel='COLMAP X',ylabel='COLMAP Y',zlabel='COLMAP Z',title='Original SfM and camera trajectory (scale not calibrated)');ax.legend();fig.tight_layout();fig.savefig(OUT/'visualizations/camera_trajectory.png',dpi=160);plt.close(fig)
ply=ROOT/'data/gaussian_scene/original_3dgs/point_cloud/iteration_30000/point_cloud.ply'
props=[];count=0
with ply.open('rb') as f:
    while True:
        line=f.readline().decode('ascii').strip()
        if line.startswith('element vertex'):count=int(line.split()[-1])
        if line.startswith('property float'):props.append(line.split()[-1])
        if line=='end_header':offset=f.tell();break
arr=np.memmap(ply,dtype=np.dtype([(p,'<f4') for p in props]),mode='r',offset=offset,shape=(count,))
gauxyz=np.column_stack([arr[k] for k in ['x','y','z']])
summary={'registered_views':len(ordered),'sfm_points':len(xyz),'image_dimensions':next(iter(dims.values())),'split':{k:len(v) for k,v in split.items()},'sfm_bbox_min':xyz.min(0).tolist(),'sfm_bbox_max':xyz.max(0).tolist(),'sfm_quantile_01_99':np.quantile(xyz,[.01,.99],axis=0).tolist(),'camera_bbox_min':centers.min(0).tolist(),'camera_bbox_max':centers.max(0).tolist(),'coordinate_system':'Original COLMAP world coordinates; R(q), t map world to camera; no recenter, rotation or metric rescaling','physical_scale':'unverified','camera_hardware':'not found in supplied records','equipment_models':'not independently verified; industrial workstations/machinery visible','image_camera_names_match':True,'ground_reference':'Historical LangSplat-derived plane archived in previous_work only; not applied'}
dump(OUT/'metrics/scene_audit.json',summary);dump(ROOT/'data/scene_information/coordinate_system.json',summary)
compat={'status':'incompatible_representation_retrain_required','check_type':'static PLY schema + upstream CUDA representation','source_gaussians':count,'source_scale_properties':[p for p in props if p.startswith('scale_')],'required_scale_properties':['scale_0','scale_1'],'source_bbox_min':gauxyz.min(0).tolist(),'source_bbox_max':gauxyz.max(0).tolist(),'source_quantile_01_99':np.quantile(gauxyz,[.01,.99],axis=0).tolist(),'evidence':['ReLaGS/scene/gaussian_model.py:create_from_pcd repeat(1,2)','ReLaGS/submodules/diff-surfel-rasterization-trace-maxcontrib/cuda_rasterizer/rasterizer_impl.cu casts scales to glm::vec2','source 3DGS PLY contains scale_0,scale_1,scale_2'],'decision':'Retain 3DGS as reference. Train official 2DGS from same COLMAP/image data. Dropping a scale would change geometry and orientation; not a lossless interface conversion.','source_model_not_sent_to_incompatible_cuda':True}
target=ROOT/'outputs/relags_baseline/01_gaussian_scene';dump(target/'data/compatibility_audit.json',compat)
(target/'README.md').write_text('# Stage 01\n\n静态兼容性检查完成：旧模型为三轴椭球，官方 ReLaGS 使用二维面元。详见 data/compatibility_audit.json。将从相同 COLMAP、同一 306/44 划分训练官方 2DGS，禁止删除第三个尺度来伪装兼容。实际训练与渲染状态见 metrics/*.json。\n')
print(json.dumps(summary,ensure_ascii=False));print(json.dumps(compat,ensure_ascii=False))
