"""Batch the official SAGA GUI's scale-gated click-affinity selection."""
import sys,argparse,math,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SAGA=ROOT/'third_party/SegAnyGAussians';sys.path.insert(0,str(SAGA))
import numpy as np,torch,cv2
from PIL import Image
from plyfile import PlyData,PlyElement
from sklearn.preprocessing import QuantileTransformer
from argparse import Namespace
from scene.gaussian_model_ff import FeatureGaussianModel
from scene.cameras import MiniCam
from utils.graphics_utils import getWorld2View2,getProjectionMatrix
from gaussian_renderer import render_contrastive_feature
p=argparse.ArgumentParser();p.add_argument('--iteration',type=int,default=10000);p.add_argument('--threshold',type=float,default=.85);p.add_argument('--tag',default='');args=p.parse_args()
def read(path):return json.loads(Path(path).read_text())
def write(path,v):path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
folder=ROOT/(f'outputs/A/extractions/iteration_{args.iteration}'+('_'+args.tag if args.tag else ''));folder.mkdir(parents=True,exist_ok=True)
modelpath=ROOT/f'outputs/A/saga_model/point_cloud/iteration_{args.iteration}';model=FeatureGaussianModel(32);model.load_ply(str(modelpath/'contrastive_feature_point_cloud.ply'));model.requires_grad_(False) if hasattr(model,'requires_grad_') else None
gate=torch.nn.Sequential(torch.nn.Linear(1,32,bias=True),torch.nn.Sigmoid()).cuda().eval();gate.load_state_dict(torch.load(modelpath/'scale_gate.pt'))
xyz=np.load(ROOT/'inputs/geometry/xyz_raw.npy',mmap_mode='r');assert np.array_equal(model.get_xyz.detach().cpu().numpy(),xyz)
raw=PlyData.read(ROOT/'outputs/A/saga_model/point_cloud/iteration_30000/scene_point_cloud.ply')['vertex'].data
assert len(raw)==len(model.get_xyz)
quantile=QuantileTransformer(output_distribution='uniform',random_state=0).fit(np.load(ROOT/'outputs/A/saga_model/all_mask_scales.npy').reshape(-1,1))
pipe=Namespace(compute_cov3D_python=False,debug=False);background=torch.zeros(32,device='cuda');refs=read(ROOT/'outputs/A/reference_prompts/records.json');objects=read(ROOT/'inputs/focus_objects.json');featuremaps={};summaries=[];selections={};scores_by_object={}
extra=read(ROOT/'configs/extra_prompt_points.json');original_cameras={c['image_id']:c for c in read(ROOT/'inputs/training_cameras.json')}
def camera(c):
    w,h=c['width'],c['height'];K=np.array(c['K']);fx,fy=K[0,0],K[1,1];fovx=2*math.atan(w/(2*fx));fovy=2*math.atan(h/(2*fy));view=torch.tensor(getWorld2View2(np.array(c['world_to_camera_R']).T,np.array(c['world_to_camera_t'])),device='cuda').T
    proj=getProjectionMatrix(.01,100.,fovx,fovy);proj[0,2]=2*(K[0,2]+.5)/w-1;proj[1,2]=2*(K[1,2]+.5)/h-1;proj=proj.T.cuda();cam=MiniCam(w,h,fovy,fovx,.01,100,view,view@proj);cam.feature_width=w;cam.feature_height=h;return cam
with torch.inference_mode():
    for obj in objects:
        oid=obj['object_id'];dest=folder/'objects'/oid;dest.mkdir(parents=True,exist_ok=True);prompts=[];vectors=[]
        physical_scale=float(np.linalg.norm(obj['bbox']['size'])/np.sqrt(3));scale=float(quantile.transform([[physical_scale]])[0,0]);gates=gate(torch.tensor([scale],device='cuda',dtype=torch.float32))
        for ref in [r for r in refs if r['object_id']==oid and r['accepted']]:
            iid=ref['image_id'];c=ref['camera'];refdir=ROOT/Path(ref['mask_path']).parent;mask=np.array(Image.open(ROOT/ref['mask_path']))>0;contrib=np.load(refdir/'coarse_candidate_contribution.npz')['contribution'];safe=mask&(contrib>.75)
            distance=cv2.distanceTransform(safe.astype(np.uint8),cv2.DIST_L2,5);points=[]
            for _ in range(3):
                y,x=np.unravel_index(distance.argmax(),distance.shape)
                if distance[y,x]<1.5:break
                points.append((int(x),int(y)));cv2.circle(distance,(x,y),max(12,int(min(c['width'],c['height'])*.04)),0,-1)
            additional=[]
            for px,py in extra['objects'].get(oid,{}).get(iid,[]):
                x=round(px*c['width']/original_cameras[iid]['width']);y=round(py*c['height']/original_cameras[iid]['height'])
                if contrib[y,x]>.5:points.append((x,y));additional.append([x,y])
                else:print('REJECT EXTRA CLICK',oid,iid,x,y,float(contrib[y,x]),flush=True)
            if not points:continue
            if iid not in featuremaps:
                fmap=render_contrastive_feature(camera(c),model,pipe,background)['render'].permute(1,2,0)
                featuremaps[iid]=fmap.cpu().half();target=folder/'rendered_affinity';target.mkdir(exist_ok=True);np.savez_compressed(target/(iid+'.npz'),feature=featuremaps[iid].numpy(),camera_json=json.dumps(c))
            fmap=featuremaps[iid].float().cuda();fmap=torch.nn.functional.normalize(fmap*gates,dim=-1)
            for x,y in points:vectors.append(fmap[y,x])
            prompts.append(dict(image_id=iid,pixels_xy=points,extra_visual_clicks=additional,mask_source=ref['mask_path'],camera=c))
        if not vectors:
            summaries.append(dict(object_id=oid,category_id=obj['category_id'],status='failed_no_reliable_prompt'));continue
        prompt_features=torch.stack(vectors,dim=1);features=torch.nn.functional.normalize(model.get_point_features*gates,dim=-1);score=((features@prompt_features+1)/2).max(1).values.cpu().numpy();np.save(dest/'affinity_scores.npy',score.astype(np.float16));np.save(dest/'prompt_features.npy',prompt_features.cpu().numpy());candidates=np.load(ROOT/'inputs/geometry/object_candidates'/oid/'gaussian_ids.npy');ids=candidates[score[candidates]>args.threshold];selections[oid]=ids;scores_by_object[oid]=score
        write(dest/'prompt.json',dict(physical_scale=physical_scale,normalized_scale=scale,physical_scale_rule='M0 OBB diagonal / sqrt(3), mapped using training-mask scale quantiles',threshold=args.threshold,score='(cosine+1)/2, maximum over positive clicks; official SAGA GUI',prompts=prompts,spatial_filter='Read-only M0 box and scene bounds',geometry_unchanged=True))
        summaries.append(dict(object_id=oid,category_id=obj['category_id'],name_zh=obj['name_zh'],name_en=obj['name_en'],status='extracted_pending_visual_review',candidate_gaussians=len(candidates),selected_before_conflicts=len(ids),fraction_retained=len(ids)/max(len(candidates),1),prompt_clicks=len(vectors),scale=scale))
        print('SAGA INSTANCE',oid,len(ids),'/',len(candidates),'scale',scale,flush=True)
    # Spatially overlapping priors use the largest learned affinity, not center votes.
    ownership=np.full(len(raw),-1,np.int16);best=np.full(len(raw),-np.inf,np.float32);oids=list(selections)
    for i,oid in enumerate(oids):
        ids=selections[oid];replace=scores_by_object[oid][ids]>best[ids];ids=ids[replace];ownership[ids]=i;best[ids]=scores_by_object[oid][ids]
    for row in summaries:
        oid=row['object_id']
        if oid not in selections:continue
        ids=np.flatnonzero(ownership==oids.index(oid));dest=folder/'objects'/oid;np.save(dest/'gaussian_indices.npy',ids);PlyData([PlyElement.describe(raw[ids].copy(),'vertex')]).write(dest/'object.ply');row.update(gaussian_count=len(ids),conflicts_removed=int(len(selections[oid])-len(ids)),gaussian_indices=str((dest/'gaussian_indices.npy').relative_to(ROOT)),ply=str((dest/'object.ply').relative_to(ROOT)))
    np.save(folder/'instance_labels.npy',ownership)
write(folder/'summary.json',dict(iteration=args.iteration,threshold=args.threshold,objects=summaries,method='Official SAGA trained features, scale gate, rendered positive clicks, cosine selection; M0 spatial constraint.',heldout_used=False))
