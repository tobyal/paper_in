"""One documented prompt refinement round; immutable initial artifacts retained."""
from pathlib import Path
import sys,copy,cv2
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
cfg=read(ROOT/'configs/refinement.json');records=copy.deepcopy(read(ROOT/'outputs/A/reference_prompts/records.json'));changes=[]
for row in records:
    oid,iid=row['object_id'],row['image_id'];old=ROOT/'outputs/A/reference_prompts'/oid/iid;new=ROOT/'outputs/A/refinement_prompts'/oid/iid
    if oid not in [cfg['rack02']['object_id'],cfg['rack04']['object_id']]:continue
    new.mkdir(parents=True,exist_ok=True);contrib=np.load(old/'coarse_candidate_contribution.npz')['contribution'].astype(float)
    if oid==cfg['rack02']['object_id']:
        if iid not in cfg['rack02']['views']:continue
        valid=[q for q in row['sam_candidates'] if q['coarse_precision']>=.40 and q['coarse_recall']>=.7 and q['outside']<.05 and q['predicted_iou']>=.9]
        if not valid:continue
        q=max(valid,key=lambda x:x['score']);mask=np.load(old/'sam_candidates.npz')['masks'][q['index']]
        distance=cv2.distanceTransform((mask&(contrib>.75)).astype(np.uint8),cv2.DIST_L2,5);points=[]
        distance[:4]=0;distance[-4:]=0;distance[:,:4]=0;distance[:,-4:]=0
        for _ in range(7):
            y,x=np.unravel_index(distance.argmax(),distance.shape)
            if distance[y,x]<1.5:break
            points.append([int(x),int(y)]);cv2.circle(distance,(x,y),30,0,-1)
        row.update(accepted=bool(points),selected_index=q['index'],points_xy=points,mask_path=str((new/'mask.png').relative_to(ROOT)),prompt_source='One object-specific reference precision check relaxed after Codex thin-structure inspection')
        save(new/'mask.png',mask.astype(np.uint8)*255)
    else:
        points=cfg['rack04']['visual_points'].get(iid,[]);accepted=[];rejected=[]
        for x,y in points:
            (accepted if contrib[y,x]>.65 else rejected).append([x,y])
        row.update(accepted=bool(accepted),points_xy=accepted,prompt_source='Explicit Codex visual clicks on central rack; not automatic or human ground truth',rejected_visual_points=rejected)
        mask=np.array(Image.open(old/'mask.png'))>0 if (old/'mask.png').exists() else np.zeros_like(contrib,bool)
        row['mask_note']='Initial SAM mask retained as evidence of neighbor contamination; only reviewed clicks are used'
    rgb=np.array(Image.open(old/'rgb.jpg'));overlay=rgb.copy()
    for x,y in row.get('points_xy',[]):cv2.circle(overlay,(x,y),5,(20,255,20),2);cv2.putText(overlay,f'{x},{y}',(x+5,y-6),cv2.FONT_HERSHEY_SIMPLEX,.35,(20,255,20),1)
    save(new/'points.jpg',overlay);write(new/'record.json',row);changes.append(dict(object_id=oid,image_id=iid,accepted=row['accepted'],points=row.get('points_xy',[])))
write(ROOT/'outputs/A/refinement_prompts/records.json',records);write(ROOT/'outputs/A/refinement_prompts/changes.json',changes)
print(json.dumps(changes,ensure_ascii=False,indent=2))
