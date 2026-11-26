"""Compact review figures derived only from saved real experiment renderings."""
from common import *
out=ROOT/'outputs/gallery';out.mkdir(parents=True,exist_ok=True);quality=read(ROOT/'world_model/quality_review.json');nodes={n['object_id']:n for n in read(ROOT/'world_model/scene_graph.json')['nodes']};iteration=read(ROOT/'world_model/manifest.json')['iteration'];paths=[];labels=[];cropping=[]
for row in quality['objects']:
    if not row['usable_for_queries']:continue
    oid=row['object_id'];source=ROOT/f'outputs/A/extractions/iteration_{iteration}/objects'/oid/'visualizations/oblique.jpg';im=np.array(Image.open(source).convert('RGB'));y,x=np.where(im.max(2)>15)
    if len(x):
        x0=max(0,int(x.min())-20);y0=max(0,int(y.min())-20);x1=min(im.shape[1],int(x.max())+21);y1=min(im.shape[0],int(y.max())+21)
    else:x0,y0,x1,y1=0,0,im.shape[1],im.shape[0]
    path=out/'object_crops'/(oid+'.jpg');save(path,im[y0:y1,x0:x1]);paths.append(path);labels.append(nodes[oid]['name_en']);cropping.append(dict(object_id=oid,source=str(source.relative_to(ROOT)),display_crop=[x0,y0,x1,y1],original_camera_and_full_image_preserved=True))
grid(paths,out/'instances.jpg',labels=labels,columns=3,tile=(440,350));write(out/'display_crops.json',cropping)
queries=read(ROOT/'outputs/D/summary.json')['queries'];classes=[r for r in queries if not r['relation']];relations=[r for r in queries if r['relation']];chosen=classes[:1]+classes[2:3]+relations[:2];images=[];labels=[]
for r in chosen:
    if not r['evaluation_views']:continue
    iid=r['evaluation_views'][0]['image_id'];images.append(ROOT/'outputs/D'/r['query_id']/(iid+'_overlay.jpg'));labels.append(r['query_id']+' / '+(r['relation'] or 'category')+' / '+str(r['candidates_before'])+' -> '+str(r['matches_after']))
grid(images,out/'query_examples.jpg',labels=labels,columns=2,tile=(900,560));write(out/'query_examples.json',chosen)
print('COMPACT GALLERY',len(paths),'instances',len(images),'queries')
