"""Frozen official SAGA affinity inference; all 33 M0 identities retained."""
import argparse,shutil,math
from common import *
import torch,cv2
from plyfile import PlyData,PlyElement
from sklearn.preprocessing import QuantileTransformer
from argparse import Namespace
SAGA=V1/'third_party/SegAnyGAussians';sys.path.insert(0,str(SAGA))
from scene.gaussian_model_ff import FeatureGaussianModel
from scene.cameras import MiniCam
from utils.graphics_utils import getWorld2View2,getProjectionMatrix
from gaussian_renderer import render_contrastive_feature

def camera(c):
    w,h=c['width'],c['height'];K=np.array(c['K']);fovx=2*math.atan(w/(2*K[0,0]));fovy=2*math.atan(h/(2*K[1,1]))
    view=torch.tensor(getWorld2View2(np.array(c['world_to_camera_R']).T,np.array(c['world_to_camera_t'])),device='cuda').T
    proj=getProjectionMatrix(.01,100.,fovx,fovy);proj[0,2]=2*(K[0,2]+.5)/w-1;proj[1,2]=2*(K[1,2]+.5)/h-1;proj=proj.T.cuda()
    cam=MiniCam(w,h,fovy,fovx,.01,100,view,view@proj);cam.feature_width=w;cam.feature_height=h;return cam

def main():
    p=argparse.ArgumentParser();p.add_argument('--tag',default='initial');p.add_argument('--threshold',type=float,default=.85)
    p.add_argument('--objects',nargs='*');p.add_argument('--scale-offset',type=float,default=0);p.add_argument('--review',default='configs/prompt_review.json')
    p.add_argument('--references',default='outputs/A/reference_prompts/records.json');args=p.parse_args()
    out=ROOT/'outputs/A/extractions'/args.tag;out.mkdir(parents=True,exist_ok=True)
    objects=read(ROOT/'inputs/objects.json');objects=[o for o in objects if not args.objects or o['object_id'] in args.objects]
    reviews=read(ROOT/args.review) if (ROOT/args.review).exists() else dict(rejected_views=[],rejected_points=[])
    refs=read(ROOT/args.references);checkpoint=V1/'outputs/A/saga_model/point_cloud/iteration_10000'
    model=FeatureGaussianModel(32);model.load_ply(str(checkpoint/'contrastive_feature_point_cloud.ply'))
    gate=torch.nn.Sequential(torch.nn.Linear(1,32),torch.nn.Sigmoid()).cuda().eval();gate.load_state_dict(torch.load(checkpoint/'scale_gate.pt'))
    xyz=np.load(V1/'inputs/geometry/xyz_raw.npy',mmap_mode='r');assert np.array_equal(model.get_xyz.detach().cpu().numpy(),xyz)
    raw=PlyData.read(original_ply())['vertex'].data
    quantile=QuantileTransformer(output_distribution='uniform',random_state=0).fit(np.load(V1/'outputs/A/saga_model/all_mask_scales.npy').reshape(-1,1))
    pipe=Namespace(compute_cov3D_python=False,debug=False);bg=torch.zeros(32,device='cuda')
    reuse={r['object_id'] for r in read(V1/'configs/final_quality_review.json')['objects'] if r['usable_for_queries']}
    previous={r['object_id']:r for r in read(existing_instances()/'summary.json')['objects']}
    summaries=[];selections={};scores_by={}
    with torch.inference_mode():
        for obj in objects:
            oid=obj['object_id'];dest=out/'objects'/oid;dest.mkdir(parents=True,exist_ok=True);candidates=candidate_ids(oid)
            if oid in reuse and not args.objects:
                old=existing_instances()/'objects'/oid;ids=np.load(old/'gaussian_indices.npy');scores=np.load(old/'affinity_scores.npy').astype(np.float32)
                row=dict(previous[oid]);row.update(reused_v1=True,initialization='Exact v1 accepted Gaussian IDs, prompts and threshold; before all-object conflict resolution')
                copy=read(old/'prompt.json');copy['source_readonly']=str(old/'prompt.json');write(dest/'prompt.json',copy)
                shutil.copy2(old/'prompt_features.npy',dest/'prompt_features.npy')
            else:
                physical=float(np.linalg.norm(obj['bbox']['size'])/np.sqrt(3));scale=float(np.clip(quantile.transform([[physical]])[0,0]+args.scale_offset,0,1))
                gates=gate(torch.tensor([scale],device='cuda',dtype=torch.float32));vectors=[];prompts=[]
                for ref in [r for r in refs if r['object_id']==oid and r['accepted']]:
                    iid=ref['image_id']
                    if any(r['object_id']==oid and r['image_id']==iid for r in reviews['rejected_views']):continue
                    points=[pt for pt in ref['points_xy'] if not any(r['object_id']==oid and r['image_id']==iid and list(pt)==r['point_xy'] for r in reviews['rejected_points'])]
                    if not points:continue
                    c=ref['camera'];assert c['split']=='train'
                    cache=ROOT/'outputs/A/rendered_affinity'/f'{iid}_{c["width"]}x{c["height"]}.npy';cache.parent.mkdir(exist_ok=True)
                    if not cache.exists():
                        feature=render_contrastive_feature(camera(c),model,pipe,bg)['render'].permute(1,2,0).cpu().half().numpy();np.save(cache,feature);write(cache.with_suffix('.json'),c)
                    fmap=np.load(cache,mmap_mode='r');click=torch.tensor(np.array([fmap[y,x] for x,y in points]),device='cuda',dtype=torch.float32)
                    vectors.extend(torch.nn.functional.normalize(click*gates,dim=-1));prompts.append(dict(image_id=iid,pixels_xy=points,source_type=ref['source_type'],in_affinity_training=ref['in_affinity_training'],camera=c,mask_source=ref['mask_path']))
                scores=np.full(len(raw),-1.,np.float32)
                if vectors:
                    pf=torch.stack(vectors,dim=1);features=torch.nn.functional.normalize(model.get_point_features[candidates]*gates,dim=-1)
                    scores[candidates]=((features@pf+1)/2).max(1).values.cpu().numpy();ids=candidates[scores[candidates]>args.threshold];np.save(dest/'prompt_features.npy',pf.cpu().numpy())
                else:ids=np.empty(0,np.int64)
                write(dest/'prompt.json',dict(physical_scale=physical,normalized_scale=scale,scale_offset=args.scale_offset,threshold=args.threshold,prompts=prompts,heldout_used=False,score='(cosine+1)/2 maximum over safe positive clicks; original SAGA inference'))
                row=dict(object_id=oid,category_id=obj['category_id'],name_zh=obj['name_zh'],name_en=obj['name_en'],reused_v1=False,
                         status='extracted_pending_visual_review' if len(ids) else 'failed_no_reliable_instance',prompt_clicks=len(vectors),scale=scale,
                         effective_real_views=sum(p['source_type']=='real' for p in prompts),effective_virtual_views=sum(p['source_type']!='real' for p in prompts))
            np.save(dest/'selected_before_conflicts.npy',ids);np.save(dest/'affinity_scores.npy',scores.astype(np.float16))
            selections[oid]=ids;scores_by[oid]=scores.astype(np.float16).astype(np.float32)
            row.update(candidate_gaussians=len(candidates),selected_before_conflicts=len(ids));summaries.append(row)
            print('INSTANCE',obj['name_en'],len(ids),'/',len(candidates),'reuse',row['reused_v1'],flush=True)
    membership=np.zeros(len(raw),np.uint16)
    for ids in selections.values():membership[ids]+=1
    owner=np.full(len(raw),-1,np.int16);best=np.full(len(raw),-np.inf,np.float32);oids=list(selections)
    for i,oid in enumerate(oids):
        ids=selections[oid];take=ids[scores_by[oid][ids]>best[ids]];owner[take]=i;best[take]=scores_by[oid][take]
    conflicts=[]
    for row in summaries:
        oid=row['object_id'];ids=np.flatnonzero(owner==oids.index(oid));dest=out/'objects'/oid
        np.save(dest/'gaussian_indices.npy',ids);PlyData([PlyElement.describe(raw[ids].copy(),'vertex')]).write(dest/'object.ply')
        lost=np.setdiff1d(selections[oid],ids);np.save(dest/'lost_conflict_ids.npy',lost)
        row.update(gaussian_count=len(ids),conflicts_removed=len(lost),gaussian_indices=str((dest/'gaussian_indices.npy').relative_to(ROOT)),ply=str((dest/'object.ply').relative_to(ROOT)))
        conflicts.append(dict(object_id=oid,removed=len(lost),reused_v1=row['reused_v1'],changed_fraction=len(lost)/max(len(selections[oid]),1)))
    np.save(out/'instance_labels.npy',owner);np.save(out/'conflict_gaussian_ids.npy',np.flatnonzero(membership>1))
    write(out/'conflicts.json',dict(conflicting_gaussians=int((membership>1).sum()),objects=conflicts,rule='Maximum stored float16 affinity within M0; stable M0 order breaks exact ties',caveat='Different scale gates and prompt sets need not give calibrated comparable affinities',object_label_order=oids))
    write(out/'summary.json',dict(tag=args.tag,iteration=10000,threshold=args.threshold,objects=summaries,heldout_used=False,training_frozen=True,geometry_modified=False))
    print('EXTRACTION COMPLETE',len(summaries),'conflicts',int((membership>1).sum()),flush=True)

if __name__=='__main__':main()
