"""Readable 3D instance-only graph; full-scene context figures remain separate."""
import cv2
from common import *
from industrial_world_model.render import Renderer
from m0.native_3dgs import subset_model
from m0.spatial import corners,transform
from industrial_world_model.hybrid_views.geometry import project
wm=ROOT/'world_model';graph=read(wm/'scene_graph.json');nodes=[n for n in graph['nodes'] if n.get('segmentation_available')];byid={n['object_id']:n for n in nodes};out=ROOT/'outputs/C/visualizations';colors={oid:np.array(c)/255 for oid,c in read(out/'instance_colors.json').items()};arrays={n['object_id']:np.load(wm/n['gaussian_indices']) for n in nodes};union=np.unique(np.concatenate(list(arrays.values())));full=Renderer(NativeContext());renderer=Renderer(NativeContext(),model=subset_model(full.model,union));groups=[(np.searchsorted(union,ids),colors[oid]) for oid,ids in arrays.items()];points=np.concatenate([corners(n['bbox']) for n in nodes]);center=(points.min(0)+points.max(0))/2;size=points.max(0)-points.min(0);T=np.array(read(ROOT/'inputs/m0_state.json')['scene']['transform']);selected=[];pairs=set()
for relation in ['nearest_to','left_of','near']:
    candidates=[e for e in graph['edges'] if e['relation']==relation and e['subject'] in byid and e['object'] in byid]
    candidates.sort(key=lambda e:np.linalg.norm(np.array(byid[e['subject']]['bbox']['center'])-byid[e['object']]['bbox']['center']))
    for e in candidates:
        pair=tuple(sorted([e['subject'],e['object']]))
        if pair not in pairs:selected.append(e);pairs.add(pair);break
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',23);paths=[]
for axis in ['oblique','top']:
    c=renderer.virtual(center,size*.65,axis,width=1600);im=np.ascontiguousarray(renderer.highlight(c,groups));positions={}
    for n in nodes:
        uv,z=project(transform([n['bbox']['center']],np.linalg.inv(T)),c);positions[n['object_id']]=tuple(np.rint(uv[0]).astype(int).tolist())
    for e in selected:
        a,b=positions[e['subject']],positions[e['object']];cv2.arrowedLine(im,a,b,(255,255,255),3,tipLength=.04);mid=((a[0]+b[0])//2,(a[1]+b[1])//2);cv2.putText(im,e['relation'],mid,cv2.FONT_HERSHEY_SIMPLEX,.65,(0,0,0),5);cv2.putText(im,e['relation'],mid,cv2.FONT_HERSHEY_SIMPLEX,.65,(255,255,255),2)
    for n in nodes:
        x,y=positions[n['object_id']];color=tuple((colors[n['object_id']]*255).astype(int).tolist());cv2.rectangle(im,(x-31,y-39),(x+31,y-8),(15,20,30),-1);cv2.putText(im,n['display_id'],(x-26,y-16),cv2.FONT_HERSHEY_SIMPLEX,.7,color,2)
    canvas=Image.new('RGB',(1600,1870),'#14212b');canvas.paste(Image.fromarray(im),(0,0));draw=ImageDraw.Draw(canvas);draw.text((20,1610),'Actual SAGA Gaussian instances | Industrial +X right, +Y front | '+axis,font=font,fill='white')
    for i,n in enumerate(nodes):draw.text((20+(i%2)*790,1655+(i//2)*40),n['display_id']+' '+n['name_en'],font=font,fill=tuple((colors[n['object_id']]*255).astype(int)))
    path=out/('instance_graph_'+axis+'.jpg');save(path,canvas);write(path.with_suffix('.json'),dict(camera=c,edges=selected,object_ids=list(byid),rendered_content='Only the nine approved original Gaussian subsets, color overridden for visualization; full-scene context figures saved separately.'));paths.append(path)
grid(paths,out/'instance_graph_gallery.jpg',columns=2,tile=(800,950));print('INSTANCE GRAPH VIEWS',len(paths))
