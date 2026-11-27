"""Read-only R1 reuse; rotate geometry into the shared industrial reference frame."""
from common import *
import os,torch
check_frozen();sys.path.insert(0,str(PROJECT/'ReLaGS'));sys.path.insert(0,str(PROJECT/'scripts'))
local_clip_weights()
import predict_3d_scene_graph as predictor
import relags_audit
from obb_boundary_r1 import wrap_official_obb
model=ROOT/'outputs/relags/model';model.mkdir(parents=True,exist_ok=True)
assets=read(ROOT/'inputs/assets.json')['paths']
for name,source in [('point_cloud',Path(assets['relags_scene'])/'point_cloud'),('sai_nag_openseg.pt',Path(assets['relags_graph'])/'sai_nag_openseg.pt')]:
    target=model/name
    if not target.exists():target.symlink_to(source)
R=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform'])[:3,:3]
assert np.allclose(R.T@R,np.eye(3),atol=1e-6)
audit=ROOT/'outputs/relags/coordinate_adaptation';audit.mkdir(parents=True,exist_ok=True)
records=[];original=predictor.get_oriented_bounding_boxes;guarded=wrap_official_obb(original,records);calls=0
def aligned(points,labels,obj_ids,**kwargs):
    global calls
    start=len(records);result=guarded(points@R.T,labels,obj_ids,**kwargs)
    for row in records[start:]:row['level']=predictor.LEVELS[calls]
    calls+=1;return result
predictor.get_oriented_bounding_boxes=aligned
def save(stage,name,value):torch.save(relags_audit.cpu(value),audit/(name+'.pt'))
relags_audit.save=save
assert (PROJECT/'models/relags/relationship_jina_features.pt').exists()
sys.argv=['align_relags.py','--root_pred',str(model),'--checkpoint',str(PROJECT/'models/relags/graph_transformer_512_80.pth'),'--vlm_type','openseg','--iteration','0','--neighbor_thresh','5','--edge_batch_size','400000']
predictor.main()
write(audit/'adaptation.json',dict(status='completed',rotation=R.tolist(),translation='discarded by official global centering',source_graph=assets['relags_graph'],source_graph_unchanged=True,geometry_only=True,device_boxes_and_classes_used=False,fallbacks=records,gaussian_render_frame='original COLMAP; membership IDs unchanged'))

