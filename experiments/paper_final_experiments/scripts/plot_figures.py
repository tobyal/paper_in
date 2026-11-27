"""Paper figures from frozen masks, native renders and actual intermediate values."""
from common import *
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
import itertools,textwrap,shutil
from m0.spatial import corners,transform
from industrial_world_model.hybrid_views.geometry import project,box_projection
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':7,'axes.titlesize':7,'axes.labelsize':6,'xtick.labelsize':5.5,'ytick.labelsize':5.5,'axes.linewidth':.6,'lines.linewidth':.7,'svg.fonttype':'none','savefig.facecolor':'white','figure.facecolor':'white','pdf.fonttype':42})
verify_locks();objects=read(V2/'inputs/objects.json');byid={o['object_id']:o for o in objects};number={o['object_id']:f'O{i+1:02d}' for i,o in enumerate(objects)};colors=read(ROOT/'configs/object_colors.json');T=np.array(Context.state['scene']['transform']);wm=world_model();queries={q['query_id']:q for q in read(BENCH/'configs/benchmark_queries.json')};views=read(BENCH/'configs/evaluation_views.json')['cameras'];samples={(s['query_id'],s['camera_id']):s for s in read(BENCH/'evaluation/pseudo_ground_truth/sample_manifest.json')};sources={};manifest=[]
def imread(p):
    p=Path(p);sources[str(p)]=dict(bytes=p.stat().st_size,sha256=sha(p));return np.array(Image.open(p).convert('RGB'))
def show(ax,im,title=None):
    ax.imshow(imread(im) if isinstance(im,(str,Path)) else im);ax.axis('off')
    if title:ax.set_title(title,pad=3)
    return ax
def foreground_crop(path,reference=None,pad=.12):
    image=imread(path);ref=imread(reference or path);mask=(ref.min(2)<232);yy,xx=np.where(mask)
    if not len(xx):return image
    x0,x1=xx.min(),xx.max()+1;y0,y1=yy.min(),yy.max()+1;margin=max(x1-x0,y1-y0)*pad
    box=[max(0,int(x0-margin)),max(0,int(y0-margin)),min(ref.shape[1],int(x1+margin)),min(ref.shape[0],int(y1+margin))]
    sources[str(path)]['display_crop_xyxy']=box
    return image[box[1]:box[3],box[0]:box[2]]
def figsave(fig,stem,experiment,description,subplots=True):
    from matplotlib.text import Text
    overrides=read(ROOT/'configs/figure_text_overrides.json') if (ROOT/'configs/figure_text_overrides.json').exists() else {}
    texts=fig.findobj(match=Text)
    for artist in texts:
        if artist.get_text() in overrides:artist.set_text(overrides[artist.get_text()])
    d=ROOT/'figures'/stem;d.mkdir(parents=True,exist_ok=True);fig.savefig(d/(stem+'.png'),dpi=450);fig.savefig(d/(stem+'.svg'),dpi=450)
    write(d/'editable_text.json',dict.fromkeys(sorted(set(t.get_text() for t in texts if t.get_text())),''))
    if subplots:
        fig.canvas.draw();renderer=fig.canvas.get_renderer()
        for i,ax in enumerate(fig.axes):
            if not ax.get_visible():continue
            bbox=ax.get_tightbbox(renderer).transformed(fig.dpi_scale_trans.inverted());fig.savefig(d/'subplots'/f'panel_{i+1:02d}.png',dpi=450,bbox_inches=bbox) if (d/'subplots').exists() else None
    write(d/'layout.json',dict(size_inches=fig.get_size_inches().tolist(),width_mm=float(fig.get_size_inches()[0]*25.4),dpi=450,editable_text='SVG text elements; DejaVu Sans',description=description,axes=[dict(title=ax.get_title(),position=ax.get_position().bounds) for ax in fig.axes]))
    write(d/'sources.json',sources);manifest.append(dict(figure=stem,experiment=experiment,png=str((d/(stem+'.png')).relative_to(ROOT)),svg=str((d/(stem+'.svg')).relative_to(ROOT)),description=description));plt.close(fig);sources.clear();print('FIGURE',stem,flush=True)
def start(stem):
    (ROOT/'figures'/stem/'subplots').mkdir(parents=True,exist_ok=True)
def wireboxes(ax,c,oids=None,linewidth=.6,labels=False):
    for oid in oids or list(byid):
        uv,z=project(transform(corners(byid[oid]['bbox']),np.linalg.inv(T)),c)
        for i,j in itertools.combinations(range(8),2):
            if bin(i^j).count('1')==1 and min(z[i],z[j])>.01:ax.plot(uv[[i,j],0],uv[[i,j],1],color=colors[oid],lw=linewidth)
        if labels and np.all(z>.01):
            p=uv.mean(0)
            if 0<=p[0]<c['width'] and 0<=p[1]<c['height']:ax.text(*p,number[oid],fontsize=5,color='white',ha='center',bbox=dict(facecolor=colors[oid],alpha=.85,edgecolor='none',pad=.6))
    ax.set_xlim(0,c['width']);ax.set_ylim(c['height'],0)
def plan(ax,candidates_ids=None,matched=None,anchors=None,edges=None,all_labels=True):
    matched=set(matched or []);anchors=set(anchors or []);candidates_ids=None if candidates_ids is None else set(candidates_ids)
    for o in objects:
        oid=o['object_id'];x,y,z=o['bbox']['center'];sx,sy,sz=o['bbox']['size'];color=colors[oid];alpha=.45
        if candidates_ids is not None:
            color=('#ed623f' if oid in matched else '#20a2c5' if oid in anchors else '#e1b94a' if oid in candidates_ids else '#dddddd');alpha=.7 if oid in matched or oid in anchors or oid in candidates_ids else .25
        available=wm.byid[oid]['segmentation_available'];ax.add_patch(Rectangle((x-sx/2,y-sy/2),sx,sy,facecolor=color,alpha=alpha,edgecolor='#555555',linewidth=.5,linestyle='-' if available else '--'))
        if all_labels or oid in matched or oid in anchors or (candidates_ids and oid in candidates_ids):ax.text(x,y,number[oid],ha='center',va='center',fontsize=5,color='#222222')
    for e in (edges or [])[:8]:
        a=np.array(byid[e['object']]['bbox']['center'])[:2];b=np.array(byid[e['subject']]['bbox']['center'])[:2];ax.annotate('',xy=b,xytext=a,arrowprops=dict(arrowstyle='->',lw=.8,color='#544e96',connectionstyle='arc3,rad=.10'))
    centers=np.array([o['bbox']['center'] for o in objects]);sizes=np.array([o['bbox']['size'] for o in objects]);lo=(centers-sizes/2).min(0);hi=(centers+sizes/2).max(0);ax.set_xlim(lo[0]-.4,hi[0]+.4);ax.set_ylim(lo[1]-.3,hi[1]+.3);ax.set_aspect('equal');ax.set_xlabel('+X: right (SfM relative units)');ax.set_ylabel('+Y: front');ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15,lw=.4)
def row_query(ax,text):ax.axis('off');ax.text(0,.70,text,fontsize=6.4,fontweight='bold',va='center')
metric={exp:{(x['method'],x['query_id'],x['camera_id']):x for x in read(ROOT/exp/'metrics/per_view.json')} for exp in ['E01_external_comparison','E02_ablation']}
def comparison(row_cases,methods,exp,stem,formal=True):
    n=len(row_cases);fig=plt.figure(figsize=(7.08,(1.20 if len(methods)==3 else 1.05)*n+.60));grid=fig.add_gridspec(n*2,len(methods)+2,height_ratios=sum(([.29,1] for _ in row_cases),[]),left=.015,right=.995,top=.94,bottom=.035,wspace=.035,hspace=.17)
    heads=['Original RGB','SAM reference']+[{'box_gated':'Box-based','no_relation':'w/o Relation','ours':'Ours','langsplat':'LangSplat','thgs':'THGS','relags':'ReLaGS','box_all33':'Box (33)','sam_common':'SAM (shared)','ours_common':'Ours (shared)','sam_original':'Multi-view SAM'}.get(m,m) for m in methods]
    for ri,(qid,iid) in enumerate(row_cases):
        q=queries[qid];c=views[iid];s=samples[(qid,iid)];image=imread(BENCH/s['original_rgb']);gt=np.array(Image.open(BENCH/s['mask_path']))>0;raw=wm.query(q['query_zh']);title=f'{qid} | {q["query_en"]}'
        if not formal:title+=' | '+iid
        row_query(fig.add_subplot(grid[ri*2,:]),title)
        for col in range(len(heads)):
            ax=fig.add_subplot(grid[ri*2+1,col])
            if col==0:
                show(ax,image)
                for oid in raw['anchor_object_ids']:
                    proj=box_projection(byid[oid]['bbox'],T,c)
                    if proj:
                        x0,y0,x1,y1=proj['bbox'];ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0,fill=False,edgecolor='#26c8e9',lw=.45))
                label='Cyan: reference-category boxes'
            elif col==1:show(ax,overlay(image,gt,(40,185,85)));label='Pseudo-GT' if s['status']=='accepted_pseudo' else 'Excluded: uncertain reference'
            else:
                m=methods[col-2];base=BENCH/'outputs'/m if exp.startswith('E01') else ROOT/exp/'predictions'/m;path=base/qid/iid/'mask.png';sources[str(path)]=dict(bytes=path.stat().st_size,sha256=sha(path));mask=np.array(Image.open(path))>0;show(ax,overlay(image,mask));v=metric[exp][m,qid,iid];label=f'IoU {v["iou"]*100:.1f}%' if v['evaluated'] else 'IoU N/A (excluded)'
            if ri==0:ax.set_title(heads[col],fontsize=6.5,pad=3)
            ax.text(.5,-.055,label,ha='center',va='top',transform=ax.transAxes,fontsize=4.8 if col==0 else 5.7)
    if formal:start(stem);figsave(fig,stem,exp,dict(cases=row_cases,methods=methods,common_camera_crop=True,overlay_alpha=.55,reference='SAM-assisted Pseudo-GT',not_human_gt=True))
    else:
        d=ROOT/exp/'gallery';d.mkdir(exist_ok=True);fig.savefig(d/(stem+'.png'),dpi=240);plt.close(fig)

# F04: actual RGB, reconstructed scene, camera distribution, 33 priors, 8 classes.
start('F04_dataset');fig=plt.figure(figsize=(7.08,7.8));outer=fig.add_gridspec(4,1,height_ratios=[1,1.55,1.6,2.05],left=.035,right=.99,bottom=.04,top=.94,hspace=.36)
a=outer[0].subgridspec(1,3,wspace=.06)
for j,iid in enumerate(['frame_000329','frame_000113','frame_000217']):
    ax=fig.add_subplot(a[j]);s=next(s for (q,i),s in samples.items() if i==iid);show(ax,BENCH/s['original_rgb'],('(a) Real RGB observations' if j==0 else '')+'\n'+iid)
b=outer[1].subgridspec(1,2,wspace=.17);scene=ROOT/'E04_relation_retrieval/scene';show(fig.add_subplot(b[0]),scene/'frame_000329_native.png','(b) Native 3DGS: 1,828,777 Gaussians')
ax=fig.add_subplot(b[1],projection='3d');pts=np.load(scene/'native_scene_display_points.npz');ax.scatter(*pts['xyz'][::2].T,c=pts['rgb'][::2],s=.12,depthshade=False,rasterized=True)
cams=read(scene/'original_cameras.json');counts={}
for split,col in [('train','#1877b7'),('heldout','#e7642a')]:
    cc=np.array([c['center'] for c in cams if c['split']==split]);cc=cc@T[:3,:3].T+T[:3,3];counts[split]=len(cc);ax.scatter(*cc.T,s=2 if split=='train' else 7,c=col,label=f'{split}: {len(cc)}',depthshade=False)
assert counts==dict(train=306,heldout=44);ax.view_init(40,-65);ax.set_xlabel('X',labelpad=-5);ax.set_ylabel('Y',labelpad=-5);ax.set_zlabel('Z',labelpad=-5);ax.tick_params(pad=-2,labelsize=4);ax.set_title('Camera distribution (same industrial frame)');ax.legend(fontsize=5,loc='upper left',frameon=False)
cgrid=outer[2].subgridspec(1,2,wspace=.16);ax=fig.add_subplot(cgrid[0]);c=read(scene/'frame_000329_camera.json');show(ax,scene/'frame_000329_native.png','(c) M0 equipment OBBs (33 identities)');wireboxes(ax,c,labels=False);ax=fig.add_subplot(cgrid[1]);plan(ax);ax.set_title('Industrial spatial priors; +Z up')
dgrid=outer[3].subgridspec(2,4,wspace=.10,hspace=.40);chosen=[6,0,3,8,20,12,14,23];short=['Material cart','Assembly fixture','Loaded fixture','Multi-tier rack','Blue bin group','Portable cooler','Workbench','Compartment rack']
for j,(ix,label) in enumerate(zip(chosen,short)):
    o=objects[ix];source=V2/'outputs/A/extractions/refined/objects'/o['object_id']/'visualizations/real_crop.jpg';n=sum(x['category_id']==o['category_id'] for x in objects);ax=fig.add_subplot(dgrid[j//4,j%4]);show(ax,source,('(d) ' if j==0 else '')+f'{label} (n={n})');ax.text(.5,-.04,number[o['object_id']],transform=ax.transAxes,ha='center',va='top',fontsize=5.5)
figsave(fig,'F04_dataset','Dataset',dict(cameras=counts,objects=33,categories=8,category_example_ids=[objects[i]['object_id'] for i in chosen],native_points_display='subsampled source Gaussian centers with SH DC colors; visualization only'))

external_cases=[(qid,queries[qid]['evaluation_camera_ids'][0]) for qid in ['Q001','Q003','Q006','Q011','Q019','Q024']]
comparison(external_cases,['langsplat','thgs','relags','ours'],'E01_external_comparison','F05_external_comparison')

# F06: same camera/extent for coarse, affinity and final geometry.
start('F06_entity_construction');rows=read(ROOT/'E03_entity_construction/summary.json')[:4];fig=plt.figure(figsize=(7.08,6.6));gs=fig.add_gridspec(8,5,height_ratios=[.24,1]*4,left=.02,right=.99,top=.96,bottom=.12,wspace=.04,hspace=.14)
for i,row in enumerate(rows):
    d=ROOT/'E03_entity_construction/objects'/row['object_id'];row_query(fig.add_subplot(gs[i*2,:]),f'{row["display_id"]} | {row["name_en"]} | {row["quality"]["extraction_status"].replace("_"," ")}')
    names=['original_crop.png','coarse_oblique.png','affinity_oblique.png','refined_oblique.png','refined_side.png'];heads=['Original observation','Coarse candidate','Gated affinity','Refined entity','Another direction']
    foot=[row['quality']['reconstruction_status'].replace('_',' '),f'{row["candidate_gaussians"]:,} Gaussians',f'Actual scores; threshold {row["threshold"]:.2f}',f'{row["final_gaussians"]:,}; removed {row["removed_gaussians"]:,}',f'Conflict removals: {row["lost_conflicts"]:,}']
    for j,(name,head) in enumerate(zip(names,heads)):
        ax=fig.add_subplot(gs[i*2+1,j]);image=d/name if j==0 else foreground_crop(d/name,d/('coarse_side.png' if j==4 else 'coarse_oblique.png'));show(ax,image,head if i==0 else None);ax.text(.5,-.035,foot[j],ha='center',va='top',transform=ax.transAxes,fontsize=4.9)
cax=fig.add_axes([.35,.065,.30,.012]);cb=fig.colorbar(ScalarMappable(norm=Normalize(0,1),cmap='viridis'),cax=cax,orientation='horizontal');cb.set_label('Stored gated affinity: max (cosine + 1) / 2',fontsize=6);cb.ax.tick_params(labelsize=5)
figsave(fig,'F06_entity_construction','E03',dict(objects=[x['object_id'] for x in rows],color_scale=[0,1],affinity='stored float16; exact before/after indices separately retained',counts_not_accuracy=True))

# F07: complete identity graph and real category-to-relation query.
start('F07_relation_retrieval');fig=plt.figure(figsize=(7.08,7.8));gs=fig.add_gridspec(3,2,height_ratios=[1,1.35,.85],left=.06,right=.99,top=.97,bottom=.04,hspace=.32,wspace=.19)
ax=fig.add_subplot(gs[0,0]);show(ax,scene/'frame_000329_instances.png','(a) Scene-level equipment identities');wireboxes(ax,read(scene/'frame_000329_camera.json'),oids=[o['object_id'] for o in objects if not wm.byid[o['object_id']]['segmentation_available']],labels=True)
ax=fig.add_subplot(gs[0,1]);show(ax,foreground_crop(scene/'oblique_colored.png'),'30 fine / partial instances (consistent colors)')
raw=wm.query(queries['Q006']['query_zh']);ax=fig.add_subplot(gs[1,0]);plan(ax);ax.set_title('(b) 33 nodes / 2,020 directed relations')
ax=fig.add_subplot(gs[1,1]);plan(ax,raw['known_category_instances'],raw['matched_object_ids'],raw['anchor_object_ids'],raw['relation_evidence'],False);ax.set_title('Q006: category candidates 6 → relation target 1');ax.text(.98,.98,'Candidates: gold\nAnchors: cyan\nTarget: red',ha='right',va='top',transform=ax.transAxes,fontsize=4.6,bbox=dict(facecolor='white',edgecolor='none',alpha=.85));ax.text(.02,.015,'Dashed: fine unavailable',transform=ax.transAxes,fontsize=4.6,bbox=dict(facecolor='white',edgecolor='none',alpha=.85))
c=views[queries['Q006']['evaluation_camera_ids'][0]];s=samples['Q006',c['image_id']];im=imread(BENCH/s['original_rgb'])
for j,m in enumerate(['no_relation','ours']):
    ax=fig.add_subplot(gs[2,j]);mask=np.array(Image.open(ROOT/'E02_ablation/predictions'/m/'Q006'/c['image_id']/'mask.png'))>0;show(ax,overlay(im,mask),'(c) Category-only candidates' if j==0 else 'Relation-constrained 3D instance');ax.text(.5,-.04,'Q006: material cart to the right of the multi-tier material rack',transform=ax.transAxes,ha='center',fontsize=5.5)
figsave(fig,'F07_relation_retrieval','E04',dict(query='Q006',nodes=33,edges=2020,drawn_edges=raw['relation_evidence'],all_anchors=raw['anchor_object_ids'],no_fine_substitution=True))

ablation_cases=[(qid,queries[qid]['evaluation_camera_ids'][0]) for qid in ['Q006','Q007','Q011','Q024']]
comparison(ablation_cases,['box_gated','no_relation','ours'],'E02_ablation','F08_ablation')

# F09: fixed 3D IDs, nearest distances, and honest incomplete results.
start('F09_multiview_application');fig=plt.figure(figsize=(7.08,8.7));outer=fig.add_gridspec(4,1,height_ratios=[1.1,1.1,1,1.0],left=.03,right=.99,top=.97,bottom=.035,hspace=.30)
for i,qid in enumerate(['Q003','Q006']):
    gs=outer[i].subgridspec(2,3,hspace=.035,wspace=.035)
    for j,axis in enumerate(['oblique','side','top']):
        d=ROOT/'E05_multiview_application/multiview'/qid/axis;ax=fig.add_subplot(gs[0,j]);show(ax,foreground_crop(d/'highlight.png',d/'isolated.png',.22),f'{"(a) " if i==j==0 else ""}{qid}: {axis}');show(fig.add_subplot(gs[1,j]),foreground_crop(d/'isolated.png',pad=.22))
    fig.axes[-1].text(.99,-.04,'Same retrieved Gaussian IDs in all 3 views',transform=fig.axes[-1].transAxes,ha='right',fontsize=5.5)
gs=outer[2].subgridspec(1,3,width_ratios=[1,1,1],wspace=.15);near=read(ROOT/'E05_multiview_application/nearest/summary.json')[1];ax=fig.add_subplot(gs[0]);plan(ax,[r['object_id'] for r in near['ranking']],near['matched_ids'],[near['anchor_id']],None,False);ax.set_title('(b) Nearest portable cooler');ax.tick_params(labelsize=4);ax.set_xlabel('+X (SfM units)',fontsize=5);ax.set_ylabel('+Y',fontsize=5)
ax=fig.add_subplot(gs[1]);rank=near['ranking'];ax.barh([number[v['object_id']] for v in rank][::-1],[v['center_distance'] for v in rank][::-1],color=['#ed623f' if v['object_id'] in near['matched_ids'] else '#bdc7ce' for v in rank][::-1]);ax.set_xlabel('Center distance (SfM units)');ax.set_title('N02: all candidates ranked');ax.spines[['top','right']].set_visible(False)
show(fig.add_subplot(gs[2]),ROOT/'E05_multiview_application/nearest/N02/highlight.png','Target red; coarse anchor cyan')
gs=outer[3].subgridspec(2,3,hspace=.12,wspace=.05)
for i,oid in enumerate([objects[23]['object_id'],objects[10]['object_id']]):
    d=ROOT/'E03_entity_construction/objects'/oid;heads=['(c) Partial compartment rack','Original 3DGS subset','Frozen fine / attempted output'] if i==0 else ['Unavailable blue-bin group','Original coarse candidate','Attempt excluded from queries']
    for j,name in enumerate(['original_crop.png','coarse_oblique.png','refined_oblique.png']):show(fig.add_subplot(gs[i,j]),d/name if j==0 else foreground_crop(d/name,d/'coarse_oblique.png'),heads[j])
figsave(fig,'F09_multiview_application','E05',dict(multiview_queries=['Q003','Q006'],fixed_ids=True,nearest_example='N02',difficult_objects=[objects[23]['object_id'],objects[10]['object_id']],unavailable_attempt_labelled=True))

# Complete per-query galleries, all selected and excluded cases, never only wins.
for qid,q in ([] if '--main-only' in sys.argv else queries.items()):
    cases=[(qid,iid) for iid in q['evaluation_camera_ids']]
    comparison(cases,['langsplat','thgs','relags','ours'],'E01_external_comparison',qid,False)
    comparison(cases,['box_gated','no_relation','ours','box_all33'],'E02_ablation',qid,False)
    print('Gallery',qid,flush=True)
for exp in ['E01_external_comparison','E02_ablation']:
    (ROOT/exp/'GALLERY.md').write_text('# All 25 queries and both fixed views\n\nSAM-assisted reference; excluded samples retained and labelled N/A.\n\n'+'\n\n'.join(f'## {qid}: {q["query_en"]}\n\n![{qid}](gallery/{qid}.png)' for qid,q in queries.items())+'\n')

# F01--F03: traceable standalone actual assets, not a newly invented method diagram.
assets=[]
def asset(group,name,source):
    source=Path(source);dest=ROOT/'method_figure_assets'/group/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest);assets.append(dict(group=group,name=name,source=str(source),destination=str(dest.relative_to(ROOT)),sha256=sha(source)))
qid='Q006';iid=queries[qid]['evaluation_camera_ids'][0]
for name,p in [('original.png',BENCH/samples[qid,iid]['original_rgb']),('category_query.jpg',ROOT/'E02_ablation/predictions/no_relation'/qid/iid/'overlay.jpg'),('lang_relation.jpg',BENCH/'outputs/langsplat'/qid/iid/'overlay.jpg'),('ours_relation.jpg',BENCH/'outputs/ours'/qid/iid/'overlay.jpg'),('instance.png',ROOT/'E05_multiview_application/multiview/Q006/oblique/isolated.png')]:asset('F01',name,p)
oid=objects[6]['object_id'];d=ROOT/'E03_entity_construction/objects'/oid
for group in ['F02','F03']:
    for name in ['original_crop.png','coarse_oblique.png','affinity_oblique.png','threshold_oblique.png','refined_oblique.png','refined_side.png','prompt.json','provenance.json']:asset(group,name,d/name)
    for p in (d/'prompts').glob('*/*'):
        if p.suffix in ['.png','.json']:asset(group,'prompts/'+str(p.relative_to(d/'prompts')),p)
asset('F02','categories.json',V2/'world_model/categories.json');asset('F02','scene_graph.json',V2/'world_model/scene_graph.json');asset('F02','scene.png',scene/'frame_000329_native.png');asset('F02','category_features.npz',V2/'world_model/category_features.npz')
fig,ax=plt.subplots(figsize=(5,3));show(ax,BENCH/samples[qid,iid]['original_rgb']);wireboxes(ax,views[iid],oids=[oid],linewidth=1.1,labels=True);fig.savefig(ROOT/'method_figure_assets/F02/m0_spatial_prior.png',dpi=400,bbox_inches='tight');plt.close(fig)
for row in read(ROOT/'E03_entity_construction/summary.json')[:4]:
    src=ROOT/'E03_entity_construction/objects'/row['object_id'];asset('F03',row['display_id']+'_shared_feature_instance.png',src/'refined_oblique.png');asset('F03',row['display_id']+'_provenance.json',src/'provenance.json')
write(ROOT/'method_figure_assets/manifest.json',assets);write(ROOT/'figures/manifest.json',manifest)
write(ROOT/'configs/figure_text.json',{m['figure']:dict(description=m['description'],experiment=m['experiment']) for m in manifest})
if not (ROOT/'configs/figure_text_overrides.json').exists():write(ROOT/'configs/figure_text_overrides.json',{})
print('All six figures, 50 comparison boards and method assets exported',flush=True)
