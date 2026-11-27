from common import *
if (ROOT/'evaluation/metrics/pseudo_summary.json').exists():
    raise SystemExit('Pseudo-GT extension exists. Use publish_pseudo_evaluation.py to preserve the quantitative gallery.')
import collections,textwrap,cv2,html
check_frozen();queries=read(ROOT/'configs/benchmark_queries.json');views=read(ROOT/'configs/evaluation_views.json')['cameras'];methods=['langsplat','thgs','relags','ours'];labels=['Original held-out RGB','LangSplat','THGS','ReLaGS','Ours'];font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',19);small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',16);rows={};records={}
for method in methods:
    records[method]={q['query_id']:read(ROOT/'outputs'/method/q['query_id']/'result.json') for q in queries if (ROOT/'outputs'/method/q['query_id']/'result.json').exists()}
def row(q,iid,width=600):
    h=round(width*528/938);canvas=Image.new('RGB',(width*5,h+115),'#14212b');draw=ImageDraw.Draw(canvas)
    title=q['query_id']+' | '+q['query_en']+' | '+iid
    for j,line in enumerate(textwrap.wrap(title,width=170)):draw.text((10,5+j*23),line,font=font,fill='white')
    c=views[iid];images=[Image.open(PROJECT/'data/images'/c['filename']).convert('RGB')]
    statuses=['Original RGB; Pending GT']
    for method in methods:
        result=records[method].get(q['query_id'],{});path=ROOT/'outputs'/method/q['query_id']/iid/'overlay.jpg';images.append(Image.open(path).convert('RGB') if path.exists() else Image.new('RGB',(938,528),'#45242b'))
        if result.get('status')=='completed':
            pixels=next(v['mask_pixels'] for v in result['views'] if v['camera_id']==iid);status=f'{pixels:,} mask pixels'
            if pixels==0:status+=' (empty projection)'
            if method=='relags' and result.get('official_threshold_fallback_used'):status+=' | official fallback'
            if method=='ours' and result.get('unavailable_object_ids'):status+=' | fine instances unavailable'
        else:status=result.get('status','not executed')
        statuses.append(status)
    for i,(im,label,status) in enumerate(zip(images,labels,statuses)):
        x=i*width;draw.text((x+10,55),label,font=font,fill='white');canvas.paste(im.resize((width,h),Image.Resampling.LANCZOS),(x,83));draw.text((x+8,h+88),status,font=small,fill='#ffd166')
    return canvas
gallery=['# Industrial relational retrieval: complete qualitative results','','All masks use the same held-out RGB, camera, 938×528 pixel grid, red color and 55% opacity. These are predictions, not ground truth. No accuracy ranking can be established before independent manual GT.','','[Protocol](../EXPERIMENT_PROTOCOL.md) · [Report](../EXPERIMENT_REPORT.md)','','## All five relations','']
for relation in ['left_of','right_of','in_front_of','behind','near']:
    subset=[q for q in queries if q['predicate_ours']==relation];pieces=[row(q,q['evaluation_camera_ids'][0],469) for q in subset];board=Image.new('RGB',(pieces[0].width,sum(p.height for p in pieces)));y=0
    for piece in pieces:board.paste(piece,(0,y));y+=piece.height
    save(ROOT/'docs/figures'/f'{relation}.jpg',board);gallery+=['### '+relation,'',f'![{relation}](figures/{relation}.jpg)','']
for q in queries:
    pieces=[row(q,iid) for iid in q['evaluation_camera_ids']];canvas=Image.new('RGB',(pieces[0].width,sum(p.height for p in pieces)));y=0
    for piece in pieces:canvas.paste(piece,(0,y));y+=piece.height
    save(ROOT/'outputs/comparisons'/q['query_id']/'all_views.jpg',canvas);save(ROOT/'docs/figures/queries'/(q['query_id']+'.jpg'),canvas)
    # Full-resolution scalar heatmap and binary masks remain with raw method data.
    for method in methods:
        for iid in q['evaluation_camera_ids']:
            folder=ROOT/'outputs'/method/q['query_id']/iid
            if (folder/'response.npz').exists() and not (folder/'heatmap.jpg').exists():
                soft=np.load(folder/'response.npz')['response'];save(folder/'heatmap.jpg',cv2.cvtColor(cv2.applyColorMap((soft.clip(0,1)*255).astype(np.uint8),cv2.COLORMAP_TURBO),cv2.COLOR_BGR2RGB))
    rows[q['query_id']]=canvas
representative=[];seen=set()
for relation in ['left_of','right_of','in_front_of','behind','near']:
    q=next(q for q in queries if q['predicate_ours']==relation and q['subject_category_id'] not in seen);representative.append(q);seen.add(q['subject_category_id'])
for q in queries:
    if q['subject_category_id'] not in seen:representative.append(q);seen.add(q['subject_category_id'])
for q in queries:
    if len(representative)>=9:break
    if q not in representative and records['ours'].get(q['query_id'],{}).get('unavailable_object_ids'):representative.append(q)
for q in queries:
    if len(representative)>=10:break
    record=records['ours'].get(q['query_id'],{})
    if q not in representative and record.get('unavailable_object_ids') and record.get('selected_gaussians')==0:representative.append(q)
gallery+=['## Representative cases','','Chosen to span all eight target categories and all five relations, plus an unavailable-instance case when present; the complete query atlas follows.','']
for q in representative:gallery += [f'### {q["query_id"]}: {q["query_en"]}','',f'![{q["query_id"]}](figures/queries/{q["query_id"]}.jpg)','']
gallery+=['## Complete query index','','| Query | Relation | English description | All fixed views |','|---|---|---|---|']
for q in queries:gallery.append(f'| {q["query_id"]} | {q["predicate"]} | {q["query_en"]} | [Images](figures/queries/{q["query_id"]}.jpg) |')
gallery+=['','## Isolated 3D regions','','THGS, ReLaGS and Ours are rendered on black backgrounds with identical virtual poses and FOV. Within each row all three methods receive the same square pixel crop and resize, preserving their common display scale. Crop parameters are saved in outputs/comparisons/Qxxx/display_crops.json; original full-frame renders remain on the server. These remove scene context for visualization only; all evaluation masks retain full-scene occlusion. LangSplat retains its official per-view output.','']
for q in queries:
    available=all((ROOT/'outputs'/m/q['query_id']/'isolated_oblique.jpg').exists() for m in ['thgs','relags','ours'])
    if not available:continue
    canvas=Image.new('RGB',(768*3,810*2),'#14212b');d=ImageDraw.Draw(canvas);crop_record={}
    for j,axis in enumerate(['oblique','top']):
        ims=[Image.open(ROOT/'outputs'/method/q['query_id']/f'isolated_{axis}.jpg').convert('RGB') for method in ['thgs','relags','ours']]
        union=np.logical_or.reduce([np.array(im).max(axis=2)>12 for im in ims]);yy,xx=np.where(union);crop=(0,0,768,768)
        if len(xx):
            side=min(768,max(int(xx.max()-xx.min()),int(yy.max()-yy.min()))+64);cx=(xx.max()+xx.min())//2;cy=(yy.max()+yy.min())//2;x=max(0,min(768-side,cx-side//2));y=max(0,min(768-side,cy-side//2));crop=(int(x),int(y),int(x+side),int(y+side))
        crop_record[axis]=crop
        for i,method in enumerate(['thgs','relags','ours']):
            canvas.paste(ims[i].crop(crop).resize((768,768),Image.Resampling.LANCZOS),(i*768,j*810+40));d.text((i*768+10,j*810+8),f'{q["query_id"]} | {method} | {axis} | shared crop',font=font,fill='white')
    write(ROOT/'outputs/comparisons'/q['query_id']/'display_crops.json',dict(crops=crop_record,same_crop_and_scale_for_all_three_methods=True,purpose='Remove blank margins in supplementary figure only; full original virtual renders retained'))
    save(ROOT/'docs/figures/3d'/(q['query_id']+'.jpg'),canvas);gallery.append(f'- [{q["query_id"]} isolated 3D comparison](figures/3d/{q["query_id"]}.jpg)')
write(ROOT/'outputs/comparisons/representative_cases.json',[q['query_id'] for q in representative]);(ROOT/'docs/GALLERY.md').write_text('\n'.join(gallery)+'\n')
print('Gallery generated',len(queries),'queries',len(representative),'representative cases')
