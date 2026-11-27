"""Review RGB against SAM only, with no method masks or accuracy scores."""
from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--revision',default='initial');p.add_argument('--tasks',nargs='*');a=p.parse_args();base=ROOT/'evaluation/pseudo_ground_truth';tasks=read(base/'tasks.json');font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
if a.tasks:tasks=[t for t in tasks if t['task_id'] in a.tasks]
else:tasks=[t for t in tasks if t['projection'] and (base/'objects'/t['task_id']/a.revision/'record.json').exists()]
for page in range(0,len(tasks),6):
    subset=tasks[page:page+6];canvas=Image.new('RGB',(1800,3*420),'#14212b');d=ImageDraw.Draw(canvas)
    for i,t in enumerate(subset):
        dest=base/'objects'/t['task_id']/a.revision;r=read(dest/'record.json');box=np.array(t['projection']['bbox']);x0,y0,x1,y1=box;pad=max(15,.15*max(x1-x0,y1-y0));crop=[max(0,int(x0-pad)),max(0,int(y0-pad)),min(938,int(x1+pad)),min(528,int(y1+pad))];x=(i%2)*900;y=(i//2)*420
        for j,source in enumerate([base/'rgb'/(t['camera_id']+'.png'),dest/'overlay.jpg']):
            im=Image.open(source).convert('RGB');draw=ImageDraw.Draw(im);draw.rectangle(box.tolist(),outline='yellow',width=2)
            for pt,label in zip(r['points'],r['point_labels']):draw.ellipse([pt[0]-3,pt[1]-3,pt[0]+3,pt[1]+3],fill='lime' if label else 'red')
            im=im.crop(crop);im.thumbnail((440,340));canvas.paste(im,(x+j*450,y+50))
        d.text((x+5,y+4),t['task_id']+' '+t['label']+' '+t['name']+' / '+t['camera_id'][-6:],font=font,fill='white');d.text((x+5,y+25),f"SAM={r['scores'][r['selected_candidate']]:.3f} candidate={r['selected_candidate']} crop={crop}",font=font,fill='white')
    save(base/'review_sheets'/a.revision/f'page_{page//6+1:02d}.jpg',canvas)
print('REVIEW PAGES',int(np.ceil(len(tasks)/6)))
