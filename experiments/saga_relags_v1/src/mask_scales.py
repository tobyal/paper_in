"""Official SAGA depth-based 2*std scale, with calibrated XY backprojection."""
import sys,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SAGA=ROOT/'third_party/SegAnyGAussians';sys.path.insert(0,str(SAGA))
import numpy as np,torch
from argparse import Namespace
from scene import Scene,GaussianModel
from gaussian_renderer import render_with_depth
cfg=json.loads((ROOT/'configs/experiment.json').read_text());model_path=ROOT/'outputs/A/saga_model';args=eval((model_path/'cfg_args').read_text());args.need_masks=False;args.need_features=False
model=GaussianModel(args.sh_degree);scene=Scene(args,model,None,load_iteration=30000,shuffle=False,mode='eval',target='scene')
pipe=Namespace(convert_SHs_python=False,compute_cov3D_python=False,debug=False);records={im['image_id']:im for im in json.loads((ROOT/'inputs/training_cameras.json').read_text())};out=ROOT/'inputs/saga_dataset/mask_scales';out.mkdir(exist_ok=True);evidence=ROOT/'outputs/A/scale_evidence';evidence.mkdir(exist_ok=True);stats=[]
with torch.inference_mode():
    for i,cam in enumerate(scene.getTrainCameras()):
        im=records[cam.image_name];K=np.array(im['K'],float);K[0]*=cam.image_width/im['width'];K[1]*=cam.image_height/im['height']
        # Verify CUDA pixel convention and exact image-bound camera calibration.
        xyz=model.get_xyz[::10000];hom=torch.cat([xyz,torch.ones_like(xyz[:,:1])],1);clip=hom@cam.full_proj_transform;uv=(clip[:,:2]/clip[:,3:]+1)*torch.tensor([cam.image_width,cam.image_height],device='cuda')/2-.5
        cv=xyz.cpu().numpy()@np.array(im['world_to_camera_R']).T+im['world_to_camera_t'];expected=(cv@K.T)[:,:2]/cv[:,2,None];valid=(cv[:,2]>.1)&(abs(expected).max(1)<5000)
        error=float(np.max(abs(uv.cpu().numpy()[valid]-expected[valid])));assert error<.03,error
        pkg=render_with_depth(cam,model,pipe,torch.zeros(3,device='cuda'));depth=pkg['depth'].detach().cpu().squeeze();masks=torch.load(ROOT/'inputs/saga_dataset/sam_masks'/(cam.image_name+'.pt'),map_location='cpu').float();assert tuple(depth.shape)==tuple(masks.shape[-2:])
        y,x=torch.meshgrid(torch.arange(depth.shape[0]),torch.arange(depth.shape[1]),indexing='ij');points=torch.stack([(x-K[0,2])*depth/K[0,0],(y-K[1,2])*depth/K[1,1],depth],-1)
        eroded=torch.nn.functional.conv2d(masks[:,None],torch.ones(1,1,3,3),padding=1)[:,0]>=5
        scales=torch.stack([(points[mask].std(0)*2).norm() for mask in eroded]);assert torch.isfinite(scales).all() and (scales>0).all()
        torch.save(scales,out/(cam.image_name+'.pt'));np.savez_compressed(evidence/(cam.image_name+'.npz'),depth=depth.numpy(),mask_scales=scales.numpy(),K=K)
        stats.append(dict(image_id=cam.image_name,masks=len(scales),minimum=float(scales.min()),maximum=float(scales.max()),projection_max_error_pixels=error));print('SCALE',i+1,len(records),cam.image_name,len(scales),flush=True)
(evidence/'summary.json').write_text(json.dumps(dict(views=stats,formula='norm(2*std(masked backprojected XYZ))',depth_source='Official SAGA full-scene depth rasterizer, unnormalized expected Z',adaptations=['Correct row/column ordering','Exact per-camera scaled K','CPU storage'],camera_alignment_passed=True),indent=2))
