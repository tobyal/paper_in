"""Reject visibly contaminated auxiliary masks; never edit their pixels."""
import sys,collections
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from common import *
import torch
rejections={
 ('obj_57b0f30bdd9e','frame_000188'):'Occluded cart prompt includes foreground fixture.',
 ('obj_09a35ba03c92','frame_000179'):'Fixture mask includes rear air cooler.',
 ('obj_ad85774e5f18','frame_000170'):'Loaded fixture mask includes rear material cart.',
 ('obj_5bfd32389355','virtual_guided_obj_5bfd32389355_005'):'Rack mask includes adjacent carts and shelves.',
}
records=read(ROOT/'outputs/A/reference_prompts/records.json');group=collections.defaultdict(list)
for row in records:
    key=(row['object_id'],row['image_id'])
    if key in rejections:
        row.update(accepted=False,visual_review_rejection=rejections[key])
        write(ROOT/'outputs/A/reference_prompts'/key[0]/key[1]/'record.json',row)
    group[row['image_id']].append(row)
for iid,rows in group.items():
    original=torch.load(ROOT/'outputs/A/sam_automatic_original'/(iid+'.pt'),map_location='cpu')
    masks=[torch.from_numpy(np.array(Image.open(ROOT/r['mask_path']))>0) for r in rows if r['accepted']]
    torch.save(torch.cat([original,torch.stack(masks)]) if masks else original,ROOT/'inputs/saga_dataset/sam_masks'/(iid+'.pt'))
write(ROOT/'outputs/A/reference_prompts/records.json',records)
write(ROOT/'outputs/A/reference_prompts/visual_review.json',[dict(object_id=k[0],image_id=k[1],reason=v) for k,v in rejections.items()])
accepted=[r for r in records if r['accepted']]
grid([ROOT/Path(r['mask_path']).parent/'overlay.jpg' for r in accepted],ROOT/'outputs/A/reference_prompts/overview.jpg',labels=[r['object_id']+' '+r['image_id'][-12:] for r in accepted])
write(ROOT/'outputs/A/reference_prompts/summary.json',dict(total=len(records),accepted=len(accepted),visual_rejections=len(rejections),official_automatic_masks_preserved=True,heldout_used=False,old_semantic_masks_used=False))
print('FINAL AUXILIARY MASKS',len(accepted))
