from common import *
import argparse
p=argparse.ArgumentParser();p.add_argument('--revision',default='review1');p.add_argument('tasks',nargs='+');a=p.parse_args();base=ROOT/'evaluation/pseudo_ground_truth';tasks={t['task_id']:t for t in read(base/'tasks.json')};font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',17)
for page in range(0,len(a.tasks),4):
    canvas=Image.new('RGB',(1600,4*330),'#14212b');d=ImageDraw.Draw(canvas)
    for row,tid in enumerate(a.tasks[page:page+4]):
        t=tasks[tid];dest=base/'objects'/tid/a.revision;data=np.load(dest/'sam_candidates.npz');rgb=np.array(Image.open(base/'rgb'/(t['camera_id']+'.png')));box=t['projection']['bbox'];x0,y0,x1,y1=box;pad=15;crop=[max(0,int(x0-pad)),max(0,int(y0-pad)),min(938,int(x1+pad)),min(528,int(y1+pad))]
        for col in range(4):
            im=rgb.copy()
            if col:
                mask=data['masks'][col-1];im[mask]=(im[mask]*.5+np.array([20,235,90])*.5).astype('uint8')
            im=Image.fromarray(im).crop(crop);s=min(390/im.width,290/im.height);im=im.resize((int(im.width*s),int(im.height*s)));canvas.paste(im,(col*400,row*330+30));d.text((col*400+4,row*330+3),tid+(' RGB' if not col else f" c{col-1} score={data['scores'][col-1]:.3f}"),font=font,fill='white')
    save(base/'candidate_sheets'/a.revision/f'page_{page//4+1:02d}.jpg',canvas)
