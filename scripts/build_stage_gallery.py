"""Read-only scientific figure layouts of saved intermediate results, no inference."""
import hashlib,json,pathlib,shutil
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable
ROOT=pathlib.Path(__file__).resolve().parents[1]
B=ROOT/'outputs/relags_baseline';R=ROOT/'outputs/relags_obb_repair_r1'
OUT=ROOT/'outputs/stage_gallery';OUT.mkdir(exist_ok=True)
FRAME='frame_000049';sources={};manifest=[]
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':12,'axes.titlesize':14,'figure.facecolor':'white'})
def image(p):
    p=pathlib.Path(p);sources[str(p.relative_to(ROOT))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return plt.imread(p)
def panel(ax,p,title):
    ax.imshow(image(p) if isinstance(p,(str,pathlib.Path)) else p);ax.axis('off');ax.set_title(title,pad=8)
def grid(rows=1,cols=2,height=None):
    return plt.subplots(rows,cols,figsize=(13,height or 4.4*rows),squeeze=False)
def finish(fig,name,title,foot,stage,raw):
    fig.suptitle(title,fontsize=20,y=.98)
    fig.text(.02,.018,foot,fontsize=11,color='#4b5563',va='bottom')
    fig.tight_layout(rect=(0,.06,1,.94),pad=1.2)
    if any(a.get_subplotspec().get_gridspec().nrows>1 for a in fig.axes if hasattr(a,'get_subplotspec') and a.get_subplotspec() is not None):
        fig.subplots_adjust(hspace=.35)
    p=OUT/(name+'.jpg');fig.savefig(p,dpi=120,pil_kwargs={'quality':94});plt.close(fig)
    manifest.append({'stage':stage,'display':str(p.relative_to(ROOT)),'title':title,'raw_artifacts':raw,'display_only':True})
base1=B/'01_gaussian_scene/visualizations/reconstruction'
fig,ax=grid()
panel(ax[0,0],base1/'gt'/f'{FRAME}.png','Undistorted industrial RGB | frame 49')
panel(ax[0,1],B/'00_data_check/visualizations/camera_trajectory.png','COLMAP cameras and scene coordinates')
finish(fig,'stage_00','00 | Data and camera reconstruction','350 registered images | 306 train / 44 test | original COLMAP units',0,['data/images/','data/colmap/sparse/0/','outputs/relags_baseline/00_data_check/data/camera_trajectory.json'])
fig,ax=grid(2,2,8.3)
for a,(folder,title) in zip(ax.flat,[('gt','Original image'),('rgb','Official 2DGS | 30,000 steps'),('depth','Rendered depth | display color scale'),('normal','Rendered surface normals')]):panel(a,base1/folder/f'{FRAME}.png',title)
finish(fig,'stage_01','01 | Gaussian geometry reconstruction','865,920 Gaussians | held-out PSNR 26.9838 dB / SSIM 0.89311 | frame 49',1,['outputs/relags_baseline/01_gaussian_scene/data/model/','outputs/relags_baseline/01_gaussian_scene/visualizations/reconstruction/'])
enc=B/'02_image_encoding/visualizations';strip=image(enc/f'{FRAME}_sam_levels.jpg');w=strip.shape[1]//5
fig,ax=grid(3,2,11.2)
for i,title in enumerate(['RGB','SAM default','SAM small','SAM medium','SAM large']):panel(ax.flat[i],strip[:180,i*w:(i+1)*w],title)
panel(ax.flat[5],enc/f'{FRAME}_openseg_pca.png','OpenSeg dense feature PCA | display only')
finish(fig,'stage_02','02 | New masks and visual-language features','All 350 frames encoded anew | colors identify masks / PCA coordinates, not verified object categories',2,['outputs/relags_baseline/02_image_encoding/data/language_features/','outputs/relags_baseline/02_image_encoding/data/language_features_openseg/'])
fig,ax=grid(2,2,8.3);pr=B/'03_gaussian_pruning'
before=image(base1/'rgb'/f'{FRAME}.png');after=image(pr/'visualizations/pruned/rgb'/f'{FRAME}.png')
panel(ax[0,0],before,'Before MWP | 865,920 Gaussians');panel(ax[0,1],after,'After MWP | 816,661 Gaussians')
delta=np.load(pr/'visualizations/comparison'/f'{FRAME}_delta.npz')['absolute_rgb_delta'].astype(float)
panel(ax[1,0],np.clip(delta*5,0,1),'Saved RGB difference x5')
panel(ax[1,1],pr/'visualizations/comparison/contribution_histogram.png','Saved maximum-contribution distribution')
finish(fig,'stage_03','03 | Maximum-weight Gaussian pruning','Removed 49,259 (5.6886%) | near-zero RGB change does not prove all thin parts are preserved',3,['outputs/relags_baseline/03_gaussian_pruning/data/','outputs/relags_baseline/03_gaussian_pruning/metrics/pruning_comparison.json'])
fig,ax=grid();stage=B/'04_superpoint_partition/visualizations'
panel(ax[0,0],base1/'gt'/f'{FRAME}.png','Reference RGB | frame 49')
panel(ax[0,1],stage/'id_projections'/f'{FRAME}_level_0_overlay.png','Raw-neighbor Cut Pursuit diagnostic | 21,712 groups')
finish(fig,'stage_04','04 | Initial Superpoint partition','This saved diagnostic is not the canonical reweighted Stage 05 input | colors are group IDs',4,['outputs/relags_baseline/04_superpoint_partition/data/model/neighbor.pt','outputs/relags_baseline/04_superpoint_partition/data/hierarchy_labels.npz'])
fig,ax=grid(2,2,8.3);stage=B/'05_hierarchical_grouping/visualizations/id_projections'
for level,(a,count) in enumerate(zip(ax.flat,[21784,9281,2491,1189])):panel(a,stage/f'{FRAME}_level_{level}_overlay.png',f'Level {level} | {count:,} groups')
finish(fig,'stage_05','05 | Hierarchical Gaussian grouping','Same camera, frame 49 | grouping colors are arbitrary IDs; coarse merging can join separate devices',5,['outputs/relags_baseline/05_hierarchical_grouping/data/model/sai_nag_3.0.pt','outputs/relags_baseline/05_hierarchical_grouping/data/'])
fig,ax=grid(2,2,8.5);stage=B/'06_semantic_aggregation'
for col,vlm in enumerate(['clip','openseg']):
    panel(ax[0,col],stage/'visualizations'/f'{vlm}_level_2'/f'{FRAME}.png',f'{vlm.upper()} | L2 retained-observation colors')
    vals=np.load(stage/'data'/f'{vlm}_level_2_retention.npz')
    ax[1,col].hist(vals['retained_fraction'],bins=30,range=(0,1),color='#327f83')
    ax[1,col].set(xlabel='ROFA retained fraction',ylabel='Group count',title=f'{vlm.upper()} | L2 retention distribution',xlim=(0,1));ax[1,col].spines[['top','right']].set_visible(False)
    fig.colorbar(ScalarMappable(norm=Normalize(0,1),cmap='viridis'),ax=ax[0,col],fraction=.035,pad=.02,label='Retained fraction')
finish(fig,'stage_06','06 | ROFA multi-view feature aggregation','Both branches replay exactly (max error 0) | high retention is not semantic accuracy | rendered colors include alpha blending',6,['outputs/relags_baseline/06_semantic_aggregation/data/','outputs/relags_baseline/06_semantic_aggregation/data/replay/'])
fig,ax=grid(2,2,8.4);stage=B/'07_object_part_modeling/clip'
panel(ax[0,0],base1/'gt'/f'{FRAME}.png','Reference probes A / B on two box-like regions')
for x,y,label in [(150,422,'A'),(515,422,'B')]:ax[0,0].plot(x,y,'o',mfc='none',mec='yellow',ms=9,mew=2);ax[0,0].text(x+10,y,label,color='yellow',weight='bold')
panel(ax[0,1],stage/'visualizations/id_projections'/f'{FRAME}_level_2_overlay.png','L2 | A = 156, B = 182')
panel(ax[1,0],stage/'visualizations/id_projections'/f'{FRAME}_level_3_overlay.png','L3 | both probes have parent 18')
cat=json.loads((stage/'data/cluster_catalog.json').read_text())['clusters'];lookup={(x['level'],x['id']):x for x in cat}
assert lookup[(2,156)]['parent_ids']==[18] and lookup[(2,182)]['parent_ids']==[18]
a=ax[1,1];a.axis('off');a.set_xlim(0,1);a.set_ylim(0,1)
a.text(.5,.85,f"L3 parent 18\n{lookup[(3,18)]['gaussians']:,} Gaussians",ha='center',va='center',fontsize=17)
for x,cid,label in [(.24,156,'A'),(.76,182,'B')]:
    a.annotate('',xy=(x,.45),xytext=(.5,.73),arrowprops={'arrowstyle':'->','color':'#167c80','lw':2})
    a.text(x,.33,f"L2 group {cid} ({label})\n{lookup[(2,cid)]['gaussians']:,} Gaussians",ha='center',va='center',fontsize=15)
a.text(.5,.08,'Two selected children shown; no semantic names assigned',ha='center',fontsize=11,color='#5b6470')
finish(fig,'stage_07','07 | Object / part hierarchy export','Saved parent-child membership | A has boundary ambiguity | a coarse-merge candidate, not confirmed instance ground truth',7,['outputs/relags_baseline/07_object_part_modeling/clip/data/hierarchy_labels.npz','outputs/relags_baseline/07_object_part_modeling/clip/data/cluster_catalog.json','outputs/relags_baseline/07_object_part_modeling/openseg/'])
fig,ax=grid()
for a,level,count,edges in [(ax[0,0],2,2491,1645360),(ax[0,1],3,1189,359928)]:panel(a,R/'08_scene_graph/visualizations/camera_projections'/f'level_{level}_{FRAME}.png',f'L{level} | {count:,} nodes / {edges:,} directed edges')
finish(fig,'stage_08','08 | Full scene graph after OBB boundary repair (R1)','Frame 49 | only 20 high-score in-frustum edges shown per level; no occlusion test | all raw edges saved',8,['outputs/relags_baseline/08_scene_graph/diagnostics/obb/','outputs/relags_obb_repair_r1/08_scene_graph/data/','outputs/relags_obb_repair_r1/08_scene_graph/metrics/obb_repair.json'])
fig,ax=grid(2,2,8.3);q=B/'09_relational_query';summary=json.loads((q/'metrics/query_open_summary.json').read_text())['queries'];vis=json.loads((q/'metrics/query_visibility.json').read_text())['queries'];best={x['id']:x['display_view'] for x in vis}
for a,i in zip(ax.flat,[4,5,10,11]):
    r=summary[i];frame=best[r['id']];panel(a,q/'visualizations'/r['id']/f'{frame}.png',f"{r['query']} | {r['selected_gaussians']:,} Gaussians\n{frame}")
finish(fig,'stage_09_open','09 | Open-vocabulary queries (4 of 12 shown)','Red = selected Gaussians | each uses its best-visible fixed reference view | floor / marking are not separated',9,['outputs/relags_baseline/09_relational_query/data/','outputs/relags_baseline/09_relational_query/metrics/query_open_summary.json'])
src=R/'09_relational_query/visualizations/relational_query_crops.jpg';shutil.copy2(src,OUT/'stage_09_relations.jpg');image(src)
manifest.append({'stage':9,'display':str((OUT/'stage_09_relations.jpg').relative_to(ROOT)),'title':'Six relational queries after OBB repair (R1)','raw_artifacts':['outputs/relags_obb_repair_r1/09_relational_query/data/','outputs/relags_obb_repair_r1/09_relational_query/metrics/relational_review.json'],'display_only':True})
(OUT/'gallery_manifest.json').write_text(json.dumps({'reference_camera':'frame_000049 for stages 00-08; query views explicitly labeled','baseline0_and_r1_unchanged':True,'figures':manifest,'source_image_sha256':sources},indent=2))
print(json.dumps({'figures':len(manifest),'directory':str(OUT)}))
