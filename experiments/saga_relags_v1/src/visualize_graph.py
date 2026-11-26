"""Actual colored native Gaussian instances with projected 3D relationship edges."""
import cv2
from plyfile import PlyData,PlyElement
from common import *
from industrial_world_model.render import Renderer
from industrial_world_model.hybrid_views.geometry import box_projection,project
from m0.spatial import transform
wm=ROOT/'world_model';graph=read(wm/'scene_graph.json');nodes=[n for n in graph['nodes'] if n.get('segmentation_available')];byid={n['object_id']:n for n in nodes};T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform']);renderer=Renderer(NativeContext());out=ROOT/'outputs/C/visualizations';out.mkdir(parents=True,exist_ok=True)
palette=np.array([[.95,.25,.18],[.15,.7,1],[.95,.7,.12],[.4,.9,.25],[.75,.3,.95],[1,.4,.7],[.1,.85,.75],[.7,.7,1],[.8,.55,.25],[.65,1,.8]])
colors={n['object_id']:palette[i%len(palette)] for i,n in enumerate(nodes)};groups=[(np.load(wm/n['gaussian_indices']),colors[n['object_id']]) for n in nodes];raw=PlyData.read(wm/'scene/scene.ply')['vertex'].data;parts=[]
for n,(ids,color) in zip(nodes,groups):
    part=raw[ids].copy()
    for i in range(3):part['f_dc_'+str(i)]=(color[i]-.5)/.28209479177387814
    for name in part.dtype.names:
        if name.startswith('f_rest_'):part[name]=0
    parts.append(part)
PlyData([PlyElement.describe(np.concatenate(parts),'vertex')]).write(out/'colored_gaussian_instance_map.ply');write(out/'instance_colors.json',{oid:(color*255).astype(int).tolist() for oid,color in colors.items()})
cameras=read(ROOT/'inputs/training_cameras.json');real=[c for c in cameras if c['source_type']=='real']
def visible(c):
    rows=[]
    for n in nodes:
        p=box_projection(n['bbox'],T,c)
        if p and p['image_coverage']>.75 and p['area_fraction']>.0007:rows.append((n,p))
    return rows
def score(c):return sum(min(p['area_fraction'],.025) for _,p in visible(c))
ranked=sorted(real,key=score,reverse=True);chosen=[ranked[0]]
for c in ranked[1:]:
    if np.linalg.norm(np.array(c['center'])-chosen[0]['center'])>1.0:chosen.append(c);break
if len(chosen)<2:chosen.append(ranked[-1])
views=[];selected_edges=[]
for index,camera in enumerate(chosen,1):
    c=scaled_camera(camera,width=1800);image=np.ascontiguousarray(renderer.highlight(c,groups));shown=[];label_positions={}
    for n,p in sorted(visible(c),key=lambda pair:pair[1]['area_fraction'],reverse=True):
        mask=renderer.contribution(c,np.load(wm/n['gaussian_indices']))>.5
        if mask.sum()<250 or mask.sum()/max(p['area_fraction']*c['width']*c['height'],1)<.08:continue
        distance=cv2.distanceTransform(mask.astype(np.uint8),cv2.DIST_L2,5);yy,xx=np.unravel_index(distance.argmax(),distance.shape);label_positions[n['object_id']]=(int(xx),int(yy));shown.append(n)
        if len(shown)>=6:break
    shown_ids={n['object_id'] for n in shown};positions={}
    for n in shown:
        uv,z=project(transform([n['bbox']['center']],np.linalg.inv(T)),c)
        if z[0]>0:positions[n['object_id']]=tuple(np.rint(uv[0]).astype(int))
    edges=[e for e in graph['edges'] if e['subject'] in shown_ids and e['object'] in shown_ids and e['relation']=='nearest_to'];edges=sorted(edges,key=lambda e:e['evidence']['center_distance']);used=set();display=[]
    for e in edges:
        pair=tuple(sorted([e['subject'],e['object']]))
        if pair in used or len(display)>=3:continue
        used.add(pair);display.append(e)
    for e in display:
        a=positions[e['subject']];b=positions[e['object']];cv2.arrowedLine(image,a,b,(255,235,80),3,tipLength=.04);label='nearest '+byid[e['subject']]['display_id']+' -> '+byid[e['object']]['display_id'];mid=((a[0]+b[0])//2,(a[1]+b[1])//2);cv2.putText(image,label,mid,cv2.FONT_HERSHEY_SIMPLEX,.5,(0,0,0),4);cv2.putText(image,label,mid,cv2.FONT_HERSHEY_SIMPLEX,.5,(255,255,255),1)
    for n in shown:
        x,y=label_positions[n['object_id']];color=tuple((colors[n['object_id']]*255).astype(int).tolist());cv2.circle(image,(x,y),9,color,-1);cv2.rectangle(image,(x-27,y-42),(x+27,y-13),(15,20,30),-1);cv2.putText(image,n['display_id'],(x-22,y-21),cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
    canvas=Image.new('RGB',(c['width'],c['height']+230),'#14212b');canvas.paste(Image.fromarray(image),(0,0));d=ImageDraw.Draw(canvas);font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
    d.text((18,c['height']+10),'Native 3DGS + SAGA instances | arrows: nearest target of its category to anchor | relative SfM units',font=font,fill='white')
    for i,n in enumerate(shown):d.text((18+(i%2)*880,c['height']+47+(i//2)*42),n['display_id']+' '+n['name_en']+' / '+n['object_id'],font=font,fill=tuple((colors[n['object_id']]*255).astype(int)))
    path=out/f'scene_graph_{index:02d}.jpg';save(path,canvas);write(out/f'scene_graph_{index:02d}.json',dict(camera=c,shown_object_ids=list(shown_ids),edges=display,label_positions=label_positions,render='Full native Gaussian scene with actual selected Gaussian colors; arrows connect projected 3D M0 centers. Labels are anchored inside the visible instance projection; heavily occluded labels omitted.'));views.append(path);selected_edges.extend(display)
# PLY line geometry shares the original scene frame and can be opened with the
# colored Gaussian map. JSON retains directed relation names and evidence.
vertices=[];edges=[]
for e in selected_edges:
    pts=transform([byid[e['subject']]['bbox']['center'],byid[e['object']]['bbox']['center']],np.linalg.inv(T));base=len(vertices);vertices.extend([tuple(p)+(255,235,80) for p in pts]);edges.append((base,base+1))
vertex=np.array(vertices,dtype=[('x','f4'),('y','f4'),('z','f4'),('red','u1'),('green','u1'),('blue','u1')]);edge=np.array(edges,dtype=[('vertex1','i4'),('vertex2','i4')]);PlyData([PlyElement.describe(vertex,'vertex'),PlyElement.describe(edge,'edge')]).write(out/'relation_lines.ply');write(out/'displayed_relations.json',selected_edges);grid(views,out/'scene_graph_gallery.jpg',columns=1,tile=(1440,1000));print('GRAPH FIGURES',len(views),'INSTANCES',len(nodes))
