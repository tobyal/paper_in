"""All 33 frozen results, native Gaussian scene graphs, and genuine 3D query projections."""
import colorsys,cv2,shutil,collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from plyfile import PlyData,PlyElement
from common import *
from query_engine import WorldModel
from industrial_world_model.render import Renderer
from industrial_world_model.hybrid_views.geometry import box_projection,project
from m0.native_3dgs import subset_model
from m0.spatial import corners,transform

wm=WorldModel(ROOT/'world_model');nodes=wm.objects;byid=wm.byid;summary=read(ROOT/'outputs/A/final_summary.json');quality={o['object_id']:o for o in summary['objects']};fontpath='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf';font=ImageFont.truetype(fontpath,23);smallfont=ImageFont.truetype(fontpath,19)
fig=ROOT/'docs/figures';fig.mkdir(parents=True,exist_ok=True);aout=ROOT/'outputs/A/final_gallery';aout.mkdir(exist_ok=True);renderer=Renderer(NativeContext());T=np.array(renderer.ctx.state['scene']['transform']);palette={n['object_id']:np.array(colorsys.hsv_to_rgb((i*.61803398875)%1,.65,.95)) for i,n in enumerate(nodes)}
category=collections.defaultdict(list);gallery=[];labels=[];comparison=[]
for node in nodes:
    oid=node['object_id'];q=quality[oid];source=ROOT/'outputs/A/extractions/refined/objects'/oid/'visualizations';im=Image.open(source/'comparison.jpg');canvas=Image.new('RGB',(im.width,im.height+88),'#15212d');canvas.paste(im,(0,88));draw=ImageDraw.Draw(canvas)
    draw.text((12,8),node['display_id']+' | '+node['name_en']+' | '+oid,font=font,fill='white');draw.text((12,43),'Reconstruction: '+q['reconstruction_status']+' | Extraction: '+q['extraction_status']+' | Fine query: '+str(q['fine_instance_available'])+' | Codex visual review (no independent truth)',font=font,fill='#ffcc66' if not q['fine_instance_available'] else '#a5dded')
    dest=aout/(oid+'.jpg');save(dest,canvas);category[node['category_id']].append(dest);gallery.append(source/'oblique.jpg');labels.append(node['display_id']+' '+node['name_en']+'\n'+q['extraction_status'])
    if oid in {o['object_id'] for o in read(V1/'outputs/A/extractions/iteration_10000/summary.json')['objects']}:
        oldids=np.load(V1/'outputs/A/extractions/iteration_10000/objects'/oid/'gaussian_indices.npy');cam=read(source/'oblique_camera.json');oldpath=aout/(oid+'_v1.jpg');save(oldpath,renderer.rgb(cam,oldids));target=aout/(oid+'_v1_v2.jpg');grid([oldpath,source/'oblique.jpg'],target,labels=['v1 / '+node['name_en'],'v2 / '+('exact reuse' if q['reused_v1'] else 'prompt refinement')],columns=2,tile=(500,540));comparison.append(target)
for cid,paths in category.items():
    ims=[Image.open(p) for p in paths];canvas=Image.new('RGB',(ims[0].width,sum(im.height for im in ims)),'#15212d');y=0
    for im in ims:canvas.paste(im,(0,y));y+=im.height
    save(aout/(cid+'.jpg'),canvas);shutil.copy2(aout/(cid+'.jpg'),fig/(cid+'.jpg'))
grid(gallery,fig/'all_33_instances.jpg',labels=labels,columns=5,tile=(400,400));grid(comparison,fig/'v1_v2_comparison.jpg',columns=2,tile=(1000,570))
write(aout/'index.json',[dict(object_id=n['object_id'],display_id=n['display_id'],image=str((aout/(n['object_id']+'.jpg')).relative_to(ROOT)),**{k:quality[n['object_id']][k] for k in ['reconstruction_status','extraction_status','fine_instance_available']}) for n in nodes])

cout=ROOT/'outputs/C/visualizations';cout.mkdir(parents=True,exist_ok=True);available=[n for n in nodes if n['segmentation_available']];arrays={n['object_id']:np.load(wm.path/n['gaussian_indices']) for n in available};union=np.unique(np.concatenate(list(arrays.values())));subset=Renderer(NativeContext(),model=subset_model(renderer.model,union));groups=[(ids,palette[oid]) for oid,ids in arrays.items()];subsetgroups=[(np.searchsorted(union,ids),palette[oid]) for oid,ids in arrays.items()]
write(cout/'instance_colors.json',{oid:(color*255).astype(int).tolist() for oid,color in palette.items()})
raw=PlyData.read(original_ply())['vertex'].data;parts=[]
for oid,ids in arrays.items():
    part=raw[ids].copy()
    for i in range(3):part['f_dc_'+str(i)]=(palette[oid][i]-.5)/.28209479177387814
    for key in part.dtype.names:
        if key.startswith('f_rest_'):part[key]=0
    parts.append(part)
PlyData([PlyElement.describe(np.concatenate(parts),'vertex')]).write(cout/'colored_instance_map.ply');np.save(cout/'colored_map_original_gaussian_ids.npy',np.concatenate(list(arrays.values())))
# Sparse representative edges; all 2020 remain in the JSON graph.
selected=[];pairs=set()
for relation in ['nearest_to','left_of','right_of','in_front_of','behind','near']:
    candidates=sorted([e for e in wm.graph['edges'] if e['relation']==relation],key=lambda e:np.linalg.norm(np.array(byid[e['subject']]['bbox']['center'])-byid[e['object']]['bbox']['center']))
    for e in candidates:
        pair=tuple(sorted([e['subject'],e['object']]))
        if pair not in pairs:selected.append(e);pairs.add(pair);break
write(cout/'representative_edges.json',selected)
pts=np.concatenate([corners(n['bbox']) for n in nodes]);center=(pts.min(0)+pts.max(0))/2;size=pts.max(0)-pts.min(0)
def annotate(im,c,shown,edges):
    im=np.ascontiguousarray(im);positions={}
    for n in shown:
        uv,z=project(transform([n['bbox']['center']],np.linalg.inv(T)),c)
        if z[0]>0:positions[n['object_id']]=tuple(np.rint(uv[0]).astype(int).tolist())
    for e in edges:
        if e['subject'] not in positions or e['object'] not in positions:continue
        a,b=positions[e['subject']],positions[e['object']];cv2.arrowedLine(im,a,b,(255,255,255),2,tipLength=.035);mid=((a[0]+b[0])//2,(a[1]+b[1])//2);cv2.putText(im,e['relation'],mid,cv2.FONT_HERSHEY_SIMPLEX,.48,(0,0,0),4);cv2.putText(im,e['relation'],mid,cv2.FONT_HERSHEY_SIMPLEX,.48,(255,255,255),1)
    for n in shown:
        if n['object_id'] not in positions:continue
        x,y=positions[n['object_id']];label=n['display_id']+(' [M0]' if not n['segmentation_available'] else '');cv2.rectangle(im,(x-25,y-22),(x+len(label)*13,y+8),(10,15,25),-1);cv2.putText(im,label,(x-20,y),cv2.FONT_HERSHEY_SIMPLEX,.65,tuple((palette[n['object_id']]*255).astype(int).tolist()),2)
    return im
for axis in ['oblique','top']:
    c=subset.virtual(center,size*.68,axis,width=1800);im=annotate(subset.highlight(c,subsetgroups),c,nodes,selected);canvas=Image.new('RGB',(1800,2500),'#14212b');canvas.paste(Image.fromarray(im),(0,0));draw=ImageDraw.Draw(canvas);draw.text((18,1815),'30 actual SAGA instances | 3 unavailable: labelled M0 location only | '+axis,font=font,fill='white')
    for i,n in enumerate(nodes):draw.text((18+(i%3)*595,1860+(i//3)*54),n['display_id']+' '+n['name_en']+'\n'+n['extraction_status'],font=smallfont,fill=tuple((palette[n['object_id']]*255).astype(int)))
    save(cout/('instance_graph_'+axis+'.jpg'),canvas);shutil.copy2(cout/('instance_graph_'+axis+'.jpg'),fig/('instance_graph_'+axis+'.jpg'));write(cout/('instance_graph_'+axis+'.json'),dict(camera=c,edges=selected,rendered_object_ids=list(arrays),unavailable_M0_only=[n['object_id'] for n in nodes if not n['segmentation_available']]))
# Explicit industrial coordinate plan; rectangles are M0 priors, never claimed as fine instances.
f,ax=plt.subplots(figsize=(12,15));ax.set_facecolor('#f4f6fa')
for n in nodes:
    p=corners(n['bbox']);lo,hi=p.min(0),p.max(0);color=palette[n['object_id']];ax.add_patch(Rectangle(lo[:2],*(hi-lo)[:2],facecolor=(*color,.25),edgecolor=color,linestyle='-' if n['segmentation_available'] else '--',linewidth=2));ax.text(*np.array(n['bbox']['center'])[:2],n['display_id']+('*' if not n['segmentation_available'] else ''),ha='center',fontsize=10)
for e in selected:
    a=np.array(byid[e['subject']]['bbox']['center'])[:2];b=np.array(byid[e['object']]['bbox']['center'])[:2];ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',color='#30353c',lw=1));ax.text(*((a+b)/2),e['relation'],fontsize=8,bbox=dict(facecolor='white',alpha=.7,edgecolor='none'))
ax.set_xlim(pts[:,0].min()-.5,pts[:,0].max()+.5);ax.set_ylim(pts[:,1].min()-.5,pts[:,1].max()+.5);ax.set_aspect('equal');ax.set_xlabel('+X right (SfM relative units)');ax.set_ylabel('+Y front (SfM relative units)');ax.set_title('33 frozen M0 equipment nodes | * fine instance unavailable\nRectangles: M0 prior; six representative geometric edges');f.tight_layout();f.savefig(cout/'industrial_top_plan.png',dpi=180);plt.close(f);shutil.copy2(cout/'industrial_top_plan.png',fig/'industrial_top_plan.png')
# Full native scene context, using previously chosen training cameras.
for i in [1,2]:
    old=read(V1/f'outputs/C/visualizations/scene_graph_{i:02d}.json');c=old['camera'];shown=[]
    for n in nodes:
        p=box_projection(n['bbox'],T,c)
        if not p or p['image_coverage']<.7:continue
        ids=arrays.get(n['object_id']);pixels=int((renderer.contribution(c,ids)>.5).sum()) if ids is not None else 0
        if pixels>300:shown.append((pixels,n))
    shown=[n for _,n in sorted(shown,key=lambda x:-x[0])[:8]];shownids={n['object_id'] for n in shown};edges=[e for e in wm.graph['edges'] if e['relation']=='nearest_to' and e['subject'] in shownids and e['object'] in shownids][:3];im=annotate(renderer.highlight(c,groups),c,shown,edges);save(cout/f'full_scene_graph_{i:02d}.jpg',im);write(cout/f'full_scene_graph_{i:02d}.json',dict(camera=c,shown=[n['object_id'] for n in shown],edges=edges,content='Complete original scene with SAGA membership colors; no source geometry changed'));shutil.copy2(cout/f'full_scene_graph_{i:02d}.jpg',fig/f'full_scene_graph_{i:02d}.jpg')
print('A/C FINAL GALLERY COMPLETE',flush=True)

# Held-out RGB is accessed only now, after the hash-bearing A freeze manifest.
frozen=read(ROOT/'outputs/A/frozen_manifest.json');assert frozen['objects'];dout=ROOT/'outputs/D';cameras=[c for c in read(ROOT/'inputs/cameras.json') if c['split']!='train'];manifest=read(ROOT/'inputs/manifest.json');assert len(cameras)==44
fixed=[cameras[i] for i in [0,14,28,43]];write(dout/'future_evaluation_protocol.json',dict(fixed_camera_ids=[c['image_id'] for c in fixed],selection='Fixed sorted-list positions 0,14,28,43 before looking at heldout RGB, for future independent labels',objects=[n['object_id'] for n in nodes],ground_truth_masks=None,predictions_are_not_ground_truth=True))
visibility={}
for original in cameras:
    c=scaled_camera(original,600);row={}
    for n in nodes:
        p=box_projection(n['bbox'],T,c)
        if p:
            ids=arrays.get(n['object_id'],candidate_ids(n['object_id']));pixels=int((renderer.contribution(c,ids)>.5).sum());row[n['object_id']]=dict(pixels=pixels,coverage=p['image_coverage'],geometry='fine_instance' if n['segmentation_available'] else 'M0_coarse_display_camera_only')
        else:row[n['object_id']]=dict(pixels=0,coverage=0)
    visibility[c['image_id']]=row
write(dout/'heldout_display_visibility.json',dict(frozen_utc=frozen['frozen_utc'],width=600,views=visibility,purpose='Select readable final figures only; no A tuning or independent accuracy claim'))
records=[];pictures=[];captions=[]
for index,text in enumerate(read(dout/'demonstration_queries.json'),1):
    result=wm.query(text);ids=wm.gaussian_ids(result);folder=dout/f'query_{index:02d}';folder.mkdir(exist_ok=True);write(folder/'result.json',result);np.save(folder/'gaussian_indices.npy',ids);matched=result['matched_object_ids'];anchors=result.get('anchor_object_ids',[])
    def score(c):
        rows=[visibility[c['image_id']][oid] for oid in matched or anchors];return (sum(r['pixels']>=80 for r in rows),sum(np.log1p(r['pixels'])*min(r['coverage'],1) for r in rows))
    chosen=sorted(cameras,key=score,reverse=True)[:2];views=[]
    for j,original in enumerate(chosen):
        c=scaled_camera(original,1500);rgb=np.array(Image.open(PROJECT/manifest['images']/c['filename']).convert('RGB').resize((c['width'],c['height'])));contrib=renderer.contribution(c,ids) if len(ids) else np.zeros((c['height'],c['width']),np.float32);mask=contrib>.5;overlay=rgb.copy();overlay[mask]=(overlay[mask]*.45+[140,10,0]).clip(0,255).astype(np.uint8)
        for oid in result['unavailable_object_ids']:
            p=box_projection(byid[oid]['bbox'],T,c)
            if p:
                x0,y0,x1,y1=np.rint(p['bbox']).astype(int);cv2.rectangle(overlay,(x0,y0),(x1,y1),(255,200,0),3);cv2.putText(overlay,byid[oid]['display_id']+' M0 ONLY',(x0,max(y0-8,25)),cv2.FONT_HERSHEY_SIMPLEX,.65,(255,200,0),2)
        iid=c['image_id'];save(folder/(iid+'_original.jpg'),rgb);save(folder/(iid+'_overlay.jpg'),overlay);save(folder/(iid+'_mask.png'),mask.astype(np.uint8)*255);np.savez_compressed(folder/(iid+'_contribution.npz'),contribution=contrib);write(folder/(iid+'_camera.json'),c)
        if len(ids):save(folder/(iid+'_isolated.jpg'),renderer.rgb(c,ids));save(folder/(iid+'_native_highlight.jpg'),renderer.highlight(c,[(ids,[1,.1,.03])]))
        caption=f'Q{index:02d} | {result["relation"] or "category / identity"} | '+str(result.get('same_category_candidates_before',0))+' -> '+str(len(matched))+' | fine '+str(len(result['renderable_object_ids']))+' / M0 only '+str(len(result['unavailable_object_ids']))
        canvas=Image.new('RGB',(1500,c['height']+110),'#14212b');canvas.paste(Image.fromarray(overlay),(0,0));draw=ImageDraw.Draw(canvas);draw.text((15,c['height']+8),caption,font=font,fill='white');draw.text((15,c['height']+43),', '.join(byid[oid]['display_id']+' '+byid[oid]['name_en'] for oid in matched)[:145] or result['status'],font=smallfont,fill='#ffcc66');draw.text((15,c['height']+75),'Red: actual frozen 3D instance projection | Yellow box: M0 location only | '+iid+' heldout',font=smallfont,fill='white');save(folder/(iid+'_panel.jpg'),canvas)
        if j==0:pictures.append(folder/(iid+'_panel.jpg'));captions.append(caption)
        views.append(dict(image_id=iid,split=original['split'],mask_pixels=int(mask.sum()),camera=str((folder/(iid+'_camera.json')).relative_to(ROOT)),panel=str((folder/(iid+'_panel.jpg')).relative_to(ROOT))))
    records.append(dict(query_id=f'query_{index:02d}',query=text,status=result['status'],relation=result['relation'],candidate_count=result.get('same_category_candidates_before'),matched_object_ids=matched,renderable=result['renderable_object_ids'],unavailable=result['unavailable_object_ids'],views=views));print('QUERY DISPLAY',index,text,len(matched),flush=True)
grid(pictures,fig/'query_gallery.jpg',labels=captions,columns=2,tile=(1000,690));write(dout/'summary.json',dict(queries=records,heldout_views_only_after_A_freeze=True,segmentation_at_query_time=False,projection='Complete native scene alpha compositing of frozen membership, threshold 0.5',no_independent_ground_truth=True))
# Small focused gallery that remains readable in a chat preview.
indices=[8,14,15,16] if len(pictures)>16 else list(range(min(4,len(pictures))))
grid([pictures[i] for i in indices],fig/'query_examples.jpg',labels=[captions[i] for i in indices],columns=2,tile=(1000,690));print('FINAL FIGURES COMPLETE',len(records),flush=True)
