"""Known-category CLIP library; no unknown-object recognition or instance discovery."""
import collections,torch,open_clip
from common import *
from industrial_world_model.hybrid_views.geometry import box_projection
catalog=[
 ('material cart',['物料车','料车','运输小车','material cart','wheeled material trolley'], 'A wheeled industrial material cart with a box-shaped metal body, trays and handles.'),
 ('assembly fixture table',['装配夹具台','装配台','assembly fixture table','assembly jig'], 'A long white wheeled base with open metal fixture supports and clamps for industrial assembly.'),
 ('fixture table carrying a black workpiece',['带黑色工件的夹具台','带工件的夹具台','黑色工件夹具台','loaded fixture','fixture table carrying a black workpiece'], 'An industrial fixture on a long white base carrying a prominent dark elongated workpiece.'),
 ('multi-tier material rack',['多层料架','工业料架','多层货架','multi-tier rack','multi-level storage rack','industrial shelf'], 'A tall open metal rack with several horizontal tiers or trays for storing industrial parts.'),
 ('group of blue storage bins',['蓝色箱组','蓝色料箱','周转箱','blue storage bins','blue plastic containers'], 'Several blue rectangular plastic storage bins grouped or stacked together.'),
 ('upright portable air cooler',['立式移动冷风机','冷风机','立式冷风机','移动冷风机','air cooler','portable cooling unit'], 'A tall narrow light gray portable air cooler with a dark ventilation grille and wheels.'),
 ('workbench',['工作台','操作台','workbench','industrial work table'], 'An industrial work table with a flat working surface and a metal support frame.'),
 ('compartmented material rack',['分隔式料架','分格料架','隔层料架','compartmented rack','partitioned storage rack'], 'A tall metal material rack divided into many narrow vertical compartments for separate parts.'),
]
out=ROOT/'outputs/B';out.mkdir(parents=True,exist_ok=True)
cats=read(ROOT/'inputs/categories.json');objects=read(ROOT/'inputs/objects.json');cameras={im['image_id']:im for im in read(ROOT/'inputs/cameras.json') if im['split']=='train'}
manifest=read(ROOT/'inputs/manifest.json');hybrid=PROJECT/manifest['hybrid_observations'];views=read(hybrid/'selected_views.json');T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform'])
model,_,preprocess=open_clip.create_model_and_transforms('ViT-B-16',pretrained=str(PROJECT/'models/openclip_vit_b16/open_clip_pytorch_model.bin'),device='cuda');model.eval();tokenizer=open_clip.get_tokenizer('ViT-B-16')
alltext=[];allvisual=[];crop_records=[];text_rows=[]
with torch.inference_mode():
    for cat,(name,aliases,desc) in zip(cats,catalog):
        cat.update(name_en=name,aliases=aliases,description_en=desc,category_known_from_m0=True)
        texts=['a photo of '+x for x in aliases if x.isascii()]+[desc]
        feat=model.encode_text(tokenizer(texts).cuda()).float();feat=torch.nn.functional.normalize(feat,dim=-1);alltext.append(norm(feat.mean(0).cpu().numpy()));text_rows.extend(dict(category_id=cat['category_id'],text=t) for t in texts)
        candidates=[]
        for obj in objects:
            if obj['category_id']!=cat['category_id']:continue
            real=[v for v in views[obj['object_id']] if v['source_type']=='real' and v['image_id'] in cameras]
            for v in sorted(real,key=lambda v:v['visible_fraction']*v['image_coverage'],reverse=True)[:2]:candidates.append((obj,v))
        # Up to six representative crops per class, at most two per instance.
        candidates=sorted(candidates,key=lambda p:p[1]['visible_fraction']*p[1]['image_coverage'],reverse=True)[:6];visual=[]
        for obj,v in candidates:
            im=cameras[v['image_id']];p=box_projection(obj['bbox'],T,im)
            if not p:continue
            rgb=Image.open(PROJECT/manifest['images']/im['filename']).convert('RGB');box=np.array(p['bbox']);pad=(box[2:]-box[:2])*.04;box[:2]-=pad;box[2:]+=pad;box=np.round(box).astype(int);box[[0,2]]=np.clip(box[[0,2]],0,im['width']);box[[1,3]]=np.clip(box[[1,3]],0,im['height'])
            if min(box[2:]-box[:2])<15:continue
            crop=rgb.crop(tuple(box));path=out/'crops'/cat['category_id']/(obj['object_id']+'_'+im['image_id']+'.jpg');save(path,crop)
            feature=model.encode_image(preprocess(crop).unsqueeze(0).cuda()).float();visual.append(norm(feature.cpu().numpy()[0]));crop_records.append(dict(category_id=cat['category_id'],object_id=obj['object_id'],image_id=im['image_id'],split='train',bbox_xyxy=box.tolist(),path=str(path.relative_to(ROOT)),precise_mask_used=False))
        assert visual,cat
        allvisual.append(norm(np.mean(visual,axis=0)));cat['visual_observations']=len(visual)
    np.savez(out/'category_features.npz',text=np.stack(alltext),visual=np.stack(allvisual),category_ids=np.array([c['category_id'] for c in cats]))
    tests=[('factory material transport trolley',0),('装配台',1),('fixture holding a dark workpiece',2),('a metal rack with multiple shelves',3),('stacked blue plastic boxes',4),('a wheeled cooling appliance with a grille',5),('industrial work table',6),('rack with separate vertical slots',7)]
    validation=[]
    for query,expected in tests:
        matches=[i for i,c in enumerate(cats) if query.casefold() in [a.casefold() for a in c['aliases']]]
        q=norm(model.encode_text(tokenizer([query]).cuda()).float().cpu().numpy()[0]);scores=.8*(np.stack(alltext)@q)+.2*(np.stack(allvisual)@q);best=matches[0] if matches else int(scores.argmax())
        validation.append(dict(query=query,expected_category=cats[expected]['category_id'],matched_category=cats[best]['category_id'],matched_by='known_alias' if matches else 'CLIP_text_visual',scores=scores.tolist(),correct=best==expected))
write(out/'categories.json',cats);write(out/'crop_observations.json',crop_records);write(out/'text_prompts.json',text_rows);write(out/'validation.json',dict(cases=validation,correct=sum(v['correct'] for v in validation),total=len(validation),interpretation='Small hand-authored category retrieval sanity check; not open-vocabulary recognition accuracy. Chinese alias mapping is explicit; CLIP is primarily English.'))
grid([ROOT/r['path'] for r in crop_records],out/'visual_representatives.jpg',labels=[r['category_id']+' '+r['object_id'][-6:] for r in crop_records])
write(out/'summary.json',dict(categories=len(cats),objects_bound=len(objects),feature_dimension=512,visual_crops=len(crop_records),checkpoint=manifest.get('clip_checkpoint','models/openclip_vit_b16/open_clip_pytorch_model.bin'),heldout_images_used=0,independent_of_A=True))
print('CATEGORY LIBRARY',len(cats),'SANITY CHECK',sum(v['correct'] for v in validation),'/',len(validation))
