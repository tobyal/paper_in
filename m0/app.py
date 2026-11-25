"""M0 v2: 3D scene extent, coarse object boxes, basic text, optional single training reference."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import threading
import traceback
import uuid
import zipfile
from urllib.parse import urlparse
import numpy as np
from PIL import Image
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .settings import ROOT,ASSETS,IMAGES,STATIC,PROJECT,GAUSSIANS
from .storage import Store,atomic_json,now
from .validation import require,box_check,transform_check,review_check,text_check,prompts_check,quality
from .spatial import transform,corners,inside,recommend,overview
from .sam_service import SamClient
from .prepare import sha

store=Store(ROOT)
images={i['image_id']:i for i in json.loads((ASSETS/'images.json').read_text())}
xyz=np.fromfile(ASSETS/'positions.bin',dtype='<f4').reshape(-1,3)
rgb=np.fromfile(ASSETS/'colors.bin',dtype='uint8').reshape(-1,3)
original_ids=np.load(ASSETS/'display_indices.npy')
sam=SamClient();pool=ThreadPoolExecutor(max_workers=1);jobs={};freeze_lock=threading.Lock()
app=FastAPI(title='M0 v2 · 三维工业先验工作台',version='2.0.0')

@app.exception_handler(ValueError)
async def invalid(request,exc):
    return JSONResponse({'detail':str(exc)},status_code=409 if str(exc).startswith('REVISION_CONFLICT') else 422)

@app.middleware('http')
async def local_requests(request:Request,call_next):
    if request.method in ('POST','PUT','PATCH','DELETE'):
        origin=request.headers.get('origin')
        if request.headers.get('x-m0-client')!='1' or (origin and urlparse(origin).netloc!=request.headers.get('host')):
            return JSONResponse({'detail':'Only same-origin local annotation requests are accepted.'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='no-referrer';response.headers['Cache-Control']='no-cache'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'"
    return response

def actor(b):return str(b.get('reviewer') or 'local draft')[:100]
def update(b,action,fn):return store.mutate(b.get('revision'),action,actor(b),fn)
def obj(s,oid):
    require(oid in s['objects'] and not s['objects'][oid].get('deleted'),'对象不存在。');return s['objects'][oid]
def image_info(i):
    require(i in images,'未知图像。');return images[i]
def train_image(i):
    im=image_info(i);require(im['split']=='train','可选参考只允许训练图像，不使用留出视角。');return im
def safe_file(relative):
    p=(ROOT/relative).resolve();require(p.is_relative_to(ROOT) and p.is_file(),'文件不存在或越界。');return p
def status_check(b):
    require(b.get('status') in ('draft','confirmed'),'无效确认状态。');review_check(b)
def submit_job(kind,fn):
    jid='job_'+uuid.uuid4().hex;jobs[jid]=dict(job_id=jid,kind=kind,status='queued',created_at=now())
    def run():
        jobs[jid]['status']='running'
        try:jobs[jid].update(status='complete',result=fn())
        except Exception as e:jobs[jid].update(status='failed',error=str(e),traceback=traceback.format_exc())
        jobs[jid]['finished_at']=now();atomic_json(ROOT/'.jobs'/(jid+'.json'),jobs[jid])
    pool.submit(run);return jobs[jid]

@app.get('/api/health')
def health():return dict(status='ok',version='2.0.0',revision=store.read()['revision'],images=len(images),display_points=len(xyz))
@app.get('/api/state')
def state():return store.read()
@app.get('/api/images')
def image_index():return [i for i in images.values() if i['split']=='train']
@app.get('/api/images/{image_id}')
def image_file(image_id:str,thumb:bool=False):
    im=train_image(image_id);return FileResponse((ASSETS/'thumbs' if thumb else IMAGES)/im['filename'])
@app.get('/api/scene/initial')
def initial():return json.loads((ASSETS/'initial_scene.json').read_text())
@app.get('/api/scene/cloud/{kind}')
def cloud(kind:str):
    require(kind in ('positions','colors'),'未知点云属性。');return FileResponse(ASSETS/(kind+'.bin'),media_type='application/octet-stream')
@app.get('/api/provenance')
def provenance():return json.loads((ASSETS/'source_manifest.json').read_text())
@app.get('/api/files/{relative:path}')
def artifact(relative:str):
    require(relative.startswith(('.artifacts/','.inference/','.assets/renders/','scene/','objects/')),'此路径不允许访问。')
    require(Path(relative).suffix in ('.jpg','.png','.json','.npy'), '文件类型不允许。')
    return FileResponse(safe_file(relative))

@app.post('/api/scene')
def save_scene(b:dict):
    box=box_check(b.get('bbox'));t=transform_check(b.get('transform'));status_check(b)
    floor=bool(b.get('floor_confirmed'));directions=bool(b.get('directions_confirmed'))
    if b['status']=='confirmed':require(floor and directions,'请确认框底面确实是地面，以及上下和前进方向。')
    def change(s):
        old=s['scene'];geometry_changed=not np.allclose(t,old['transform'],atol=1e-8) or box!=old['bbox']
        version='coord_'+uuid.uuid4().hex[:12] if geometry_changed else old['coordinate_version']
        transformed=transform(xyz,t);selection=inside(transformed,box)
        require(selection.sum()>=100,'场景框内有效高斯不足，请检查范围与方向。')
        folder=Path('.artifacts/scene')/(version+'_'+uuid.uuid4().hex[:8]);(ROOT/folder).mkdir(parents=True)
        np.save(ROOT/folder/'scene_gaussian_indices.npy',original_ids[selection])
        overview(ROOT/folder/'scene_overview.jpg',xyz,rgb,t,box)
        s['scene']=dict(bbox=box,transform=t.tolist(),coordinate_version=version,status=b['status'],floor_confirmed=floor,directions_confirmed=directions,
                        reviewer=actor(b),updated_at=now(),estimation=old.get('estimation'),gaussian_count=int(selection.sum()),
                        artifacts={n:str(folder/n) for n in ('scene_gaussian_indices.npy','scene_overview.jpg')})
        if geometry_changed:
            # Preserve world coverage; re-express old AABBs in the new frame and require review.
            for o in s['objects'].values():
                if o.get('deleted'):continue
                raw=transform(corners(o['bbox']),np.linalg.inv(old['transform']));p=transform(raw,t);lo=p.min(0);hi=p.max(0)
                o.update(bbox=dict(center=((lo+hi)/2).tolist(),size=(hi-lo).tolist()),coordinate_version=version,status='draft',needs_review='scene geometry changed')
                if o.get('reference'):o['reference']['status']='draft'
                folder=Path('.artifacts/objects')/o['object_id']/uuid.uuid4().hex
                overview(ROOT/folder/'bbox_preview.jpg',xyz,rgb,t,box,o['bbox']);o['preview_path']=str(folder/'bbox_preview.jpg')
    return update(b,'scene.save',change)

@app.post('/api/objects')
def save_object(b:dict):
    oid=b.get('object_id') or 'obj_'+uuid.uuid4().hex[:12];box=box_check(b.get('bbox'));status_check(b);text_check(b,b['status']=='confirmed')
    require(b.get('granularity','equipment') in ('equipment','container_group'),'只支持完整设备或物料箱组。')
    def change(s):
        old=obj(s,oid) if b.get('object_id') else {}
        require(b.get('coordinate_version')==s['scene']['coordinate_version'],'坐标版本已更新，请刷新后重新调整设备框。')
        if b['status']=='confirmed':
            require(s['scene']['status']=='confirmed','请先确认场景范围。')
            require(inside(corners(box),s['scene']['bbox']).all(),'粗框超出场景范围。')
        o={k:str(b.get(k,'')).strip() for k in ('name_zh','name_en','description_zh','description_en')}
        o.update(object_id=oid,bbox=box,status=b['status'],coordinate_version=s['scene']['coordinate_version'],granularity=b.get('granularity','equipment'),
                 source=b.get('source','human'),reviewer=actor(b),updated_at=now(),reference=old.get('reference'),visible=bool(b.get('visible',True)))
        if old.get('bbox')!=box and o['reference']:o['reference']={**o['reference'],'status':'draft','needs_review':'coarse box changed'}
        folder=Path('.artifacts/objects')/oid/uuid.uuid4().hex
        overview(ROOT/folder/'bbox_preview.jpg',xyz,rgb,s['scene']['transform'],s['scene']['bbox'],box);o['preview_path']=str(folder/'bbox_preview.jpg')
        s['objects'][oid]=o
    result=update(b,'object.save:'+oid,change);return dict(state=result,object_id=oid)

@app.post('/api/objects/{oid}/delete')
def delete_object(oid:str,b:dict):
    def change(s):obj(s,oid).update(deleted=True,deleted_at=now(),deleted_by=actor(b))
    return update(b,'object.delete:'+oid,change)

@app.post('/api/objects/{oid}/visibility')
def visibility(oid:str,b:dict):
    require(isinstance(b.get('visible'),bool),'可见性必须为布尔值。')
    return update(b,'object.visibility:'+oid,lambda s:obj(s,oid).__setitem__('visible',b['visible']))

@app.post('/api/objects/{oid}/recommend')
def recommend_views(oid:str):
    s=store.read();o=obj(s,oid)
    return dict(recommendations=recommend(o['bbox'],s['scene']['transform'],list(images.values())),purpose='one optional reference only')

@app.post('/api/render/{image_id}')
def render_image(image_id:str):
    train_image(image_id)
    def execute():
        path=ASSETS/'renders'/(image_id+'.jpg')
        if not path.exists():
            process=subprocess.run([sys.executable,'-m','m0.render_geometry',image_id],cwd=PROJECT,capture_output=True,text=True,timeout=180)
            (ROOT/'.jobs').mkdir(exist_ok=True);(ROOT/'.jobs'/(image_id+'_render.log')).write_text(process.stdout+process.stderr)
            require(process.returncode==0,'2DGS 渲染失败：'+process.stderr[-800:])
        return dict(path=str(path.relative_to(ROOT)),image_id=image_id)
    return submit_job('render',execute)

@app.get('/api/jobs/{job_id}')
def job_status(job_id:str):
    require(re.fullmatch(r'job_[a-f0-9]{32}',job_id) is not None,'任务 ID 无效。')
    if job_id in jobs:return jobs[job_id]
    p=ROOT/'.jobs'/(job_id+'.json');require(p.exists(),'任务不存在。');return json.loads(p.read_text())

@app.post('/api/sam')
def infer(b:dict):
    oid=b.get('object_id');obj(store.read(),oid);im=train_image(b.get('image_id'));prompts_check(b.get('prompts',{}),im)
    def execute():
        result=sam.predict(im,b['prompts']);result['object_id']=oid;result['purpose']='optional single-view reference'
        atomic_json(ROOT/'.inference'/result['job_id']/'inference.json',result);return result
    return submit_job('sam',execute)

@app.post('/api/objects/{oid}/reference')
def reference(oid:str,b:dict):
    obj(store.read(),oid);im=train_image(b.get('image_id'));status_check(b)
    jid=b.get('sam_job_id','');require(re.fullmatch(r'sam_[a-f0-9]{32}',jid) is not None,'请先运行本次 M0 SAM。')
    record=json.loads(safe_file('.inference/'+jid+'/inference.json').read_text())
    require(record['image_id']==im['image_id'] and record['image_sha256']==im['sha256'] and record.get('object_id')==oid,'SAM 结果与当前对象或图像不一致。')
    selected=b.get('candidate',0);require(isinstance(selected,int) and 0<=selected<3,'候选编号无效。')
    encoded=b.get('mask_png','');require(encoded.startswith('data:image/png;base64,') and len(encoded)<22000000,'需要原分辨率 PNG 掩膜。')
    try:
        mask=Image.open(io.BytesIO(base64.b64decode(encoded.split(',',1)[1],validate=True)))
        require(mask.format=='PNG' and mask.size==(im['width'],im['height']),'掩膜尺寸必须与原图相同。')
        arr=np.asarray(mask.convert('L'));require(np.isin(arr,[0,255]).all() and arr.any(),'掩膜必须非空，使用 0/255 二值像素。')
    except (OSError,TypeError) as e:raise ValueError('掩膜格式无效。') from e
    original=np.asarray(Image.open(safe_file(f'.inference/{jid}/candidate_{selected}.png')))
    require(np.array_equal(arr,original) or bool(b.get('edit_history')),'修正掩膜必须保留编辑过程。')
    folder=Path('.artifacts/references')/oid/uuid.uuid4().hex;(ROOT/folder).mkdir(parents=True)
    Image.fromarray(arr).save(ROOT/folder/'mask.png')
    source=np.asarray(Image.open(IMAGES/im['filename']).convert('RGB'));out=source.copy();out[arr>0]=(source[arr>0]*.5+np.array([10,210,170])*.5).astype('uint8')
    Image.fromarray(out).save(ROOT/folder/'overlay.jpg',quality=94)
    atomic_json(ROOT/folder/'edits.json',dict(operations=b.get('edit_history',[]),action_history=b.get('action_history',[]),selected_candidate=selected,reviewer=actor(b),saved_at=now()))
    originals=[]
    for i in range(3):
        dest=folder/f'candidate_{i}.png';shutil.copy2(safe_file(f'.inference/{jid}/candidate_{i}.png'),ROOT/dest);originals.append(str(dest))
    ref=dict(image_id=im['image_id'],image_sha256=im['sha256'],split='train',width=im['width'],height=im['height'],status=b['status'],reviewer=actor(b),
             prompts=record['prompts'],sam_job_id=jid,candidate=selected,mask_path=str(folder/'mask.png'),overlay_path=str(folder/'overlay.jpg'),
             edit_history_path=str(folder/'edits.json'),original_mask_paths=originals,mask_sha256=sha(ROOT/folder/'mask.png'),purpose='optional identity reference; no multi-view fusion',updated_at=now())
    return update(b,'reference.save:'+oid,lambda s:obj(s,oid).__setitem__('reference',ref))

@app.post('/api/objects/{oid}/reference/remove')
def remove_reference(oid:str,b:dict):
    return update(b,'reference.remove:'+oid,lambda s:obj(s,oid).__setitem__('reference',None))

@app.get('/api/draft/{key}')
def get_draft(key:str):
    require(len(key)<180,'草稿键无效。');return store.draft(key)
@app.put('/api/draft/{key}')
def put_draft(key:str,b:dict):
    require(len(key)<180 and len(json.dumps(b))<23000000,'草稿过大。');store.draft(key,b);return dict(saved=True)
@app.get('/api/history')
def history():return store.history()
@app.get('/api/quality')
def get_quality():return quality(store.read())
@app.get('/api/versions')
def versions():
    return [json.loads(p.read_text()) for p in sorted((ROOT/'versions').glob('*/FROZEN.json'),reverse=True)]

@app.post('/api/freeze')
def freeze(b:dict):
    require(b.get('review_ack') is True and bool(str(b.get('reviewer','')).strip()),'冻结前请人工核对并填写审核人。')
    with freeze_lock,store.lock:
        s=store.read();require(b.get('revision')==s['revision'],'REVISION_CONFLICT: 冻结前数据已更新。')
        q=quality(s);require(q['can_freeze'],'尚不能冻结：'+'；'.join(i['message'] for i in q['issues'] if i['severity']=='error'))
        provenance=json.loads((ASSETS/'source_manifest.json').read_text())
        for source in provenance['source_files']:require(sha(PROJECT/source['path'])==source['sha256'],'基础来源文件哈希已变化：'+source['path'])
        for im in images.values():require(sha(IMAGES/im['filename'])==im['sha256'],'原图发生变化：'+im['image_id'])
        for o in s['objects'].values():
            ref=o.get('reference')
            if not o.get('deleted') and ref and ref['status']=='confirmed':
                require(ref['image_id'] in images and images[ref['image_id']]['split']=='train','参考不是训练图像。')
                require(sha(safe_file(ref['mask_path']))==ref['mask_sha256'],'参考掩膜哈希不一致。')
        version='m0v2_'+now().replace(':','').replace('-','').replace('.','_')+'_'+str(s['revision'])
        folder=ROOT/'versions'/version;folder.mkdir(parents=True,exist_ok=False)
        store.write_dataset(folder,s)
        atomic_json(folder/'annotation_history.json',store.history())
        hashes={str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()}
        record=dict(version=version,frozen_at=now(),revision=s['revision'],reviewer=actor(b),files=hashes,objects=q['objects'])
        atomic_json(folder/'FROZEN.json',record)
        update(b,'freeze:'+version,lambda state:state.__setitem__('last_frozen_version',version))
        return record

@app.get('/api/exports/{version}')
def export(version:str):
    require(re.fullmatch(r'm0v2_[A-Za-z0-9_+]+',version) is not None,'版本号无效。')
    folder=ROOT/'versions'/version;require((folder/'FROZEN.json').exists(),'冻结版本不存在。')
    record=json.loads((folder/'FROZEN.json').read_text())
    for name,digest in record['files'].items():require(sha(folder/name)==digest,'冻结文件校验失败：'+name)
    target=ROOT/'.exports'/(version+'.zip');target.parent.mkdir(exist_ok=True)
    if not target.exists():
        tmp=target.with_suffix('.tmp')
        with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED) as z:
            for name in [*record['files'],'FROZEN.json']:z.write(folder/name,name)
        os.replace(tmp,target)
    return FileResponse(target,filename=version+'.zip',media_type='application/zip')

app.mount('/static',StaticFiles(directory=str(STATIC)),name='static')
@app.get('/')
def home():return FileResponse(STATIC/'index.html')
