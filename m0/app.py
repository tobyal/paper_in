"""Server-local M0 annotation API. Run one process: caches and revision writes are serialized."""
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
from PIL import Image, ImageDraw
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from .settings import ROOT, ASSETS, IMAGES, STATIC, PROJECT, GAUSSIANS
from .storage import Store, atomic_json, now
from .validation import require, bbox_check, prompts_check, review_check, quality, VISIBLE, VISIBILITY, QUERY_TYPES, relation_signature
from .geometry import fit_reference, project
from .sam_service import SamClient

store = Store(ROOT)
images = {x['image_id']: x for x in json.loads((ASSETS / 'images.json').read_text())}
sam = SamClient(); pool = ThreadPoolExecutor(max_workers=1); jobs = {}; freeze_lock = threading.Lock()
app = FastAPI(title='M0 · 工业场景先验标注', version='1.0.0')


@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({'detail': str(exc)}, status_code=409 if str(exc).startswith('REVISION_CONFLICT') else 422)


@app.middleware('http')
async def local_requests(request: Request, call_next):
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
        origin = request.headers.get('origin')
        if request.headers.get('x-m0-client') != '1' or (origin and urlparse(origin).netloc != request.headers.get('host')):
            return JSONResponse({'detail': 'M0 only accepts same-origin local annotation requests.'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'"
    return response


def image_info(image_id):
    require(image_id in images, '未知图像 ID。'); return images[image_id]


def safe_file(relative):
    p = (ROOT / relative).resolve()
    require(p.is_relative_to(ROOT) and p.is_file(), '文件不存在或越界。')
    return p


def actor(b): return str(b.get('reviewer') or 'local annotator')[:100]
def update(b, action, step, func): return store.mutate(b.get('revision'), action, step, actor(b), func)
def obj(s, oid): require(oid in s['objects'], '对象不存在。'); return s['objects'][oid]


def split_check(scope, image_id):
    require(scope in ('priors', 'ground_truth'), '无效数据用途。')
    im = image_info(image_id)
    require(im['split'] == ('train' if scope == 'priors' else 'heldout'), '训练掩膜与留出评价掩膜严格隔离，当前图像用途不匹配。')
    return im


def submit_job(kind, execute):
    jid = 'job_' + uuid.uuid4().hex
    jobs[jid] = dict(job_id=jid, kind=kind, status='queued', created_at=now())
    def run():
        jobs[jid].update(status='running')
        try: jobs[jid].update(status='complete', result=execute())
        except Exception as e: jobs[jid].update(status='failed', error=str(e), traceback=traceback.format_exc())
        jobs[jid]['finished_at'] = now(); atomic_json(ROOT / '.jobs' / (jid + '.json'), jobs[jid])
    pool.submit(run); return jobs[jid]


@app.get('/api/health')
def health(): return dict(status='ok', revision=store.read()['revision'], images=len(images), model_loaded=sam.predictor is not None)


@app.get('/api/state')
def state(): return store.read()


@app.get('/api/images')
def image_index(): return list(images.values())


@app.get('/api/provenance')
def provenance(): return json.loads((ASSETS / 'source_manifest.json').read_text())


@app.get('/api/images/{image_id}')
def image_file(image_id: str, thumb: bool = False):
    im = image_info(image_id); return FileResponse((ASSETS / 'thumbs' if thumb else IMAGES) / im['filename'])


@app.get('/api/scene/points')
def point_file(): return FileResponse(ASSETS / 'scene_points.json')


@app.get('/api/files/{relative:path}')
def artifact(relative: str):
    # No arbitrary project files or SQLite state are exposed.
    require(relative.startswith(('priors/', 'ground_truth/', '.inference/', '.assets/renders/', 'versions/')), '此路径不允许访问。')
    require(Path(relative).suffix in ('.png', '.jpg', '.json', '.npy', '.npz', '.zip', '.md'), '文件类型不允许。')
    return FileResponse(safe_file(relative))


@app.post('/api/render/{image_id}')
def render_image(image_id: str):
    image_info(image_id)
    def execute():
        path = ASSETS / 'renders' / (image_id + '.jpg')
        if not path.exists():
            process = subprocess.run([sys.executable, '-m', 'm0.render_geometry', image_id], cwd=PROJECT, capture_output=True, text=True, timeout=180)
            (ROOT / '.jobs').mkdir(exist_ok=True)
            (ROOT / '.jobs' / (image_id + '_render.log')).write_text(process.stdout + process.stderr)
            require(process.returncode == 0, '渲染失败：' + process.stderr[-1000:])
        return {'path': str(path.relative_to(ROOT)), 'image_id': image_id}
    return submit_job('render', execute)


@app.get('/api/jobs/{job_id}')
def job_status(job_id: str):
    require(re.fullmatch(r'job_[a-f0-9]{32}', job_id) is not None, '无效任务 ID。')
    if job_id in jobs: return jobs[job_id]
    p = ROOT / '.jobs' / (job_id + '.json'); require(p.exists(), '任务不存在或服务已重启，请重新运行。')
    return json.loads(p.read_text())


@app.post('/api/objects')
def save_object(b: dict):
    oid = b.get('object_id') or 'obj_' + uuid.uuid4().hex[:12]
    im = image_info(b.get('anchor_image_id')); require(im['split'] == 'train', '对象主参考图必须来自训练视角。')
    bbox_check(b.get('anchor_bbox'), im)
    for field in ('category_zh', 'category_en'): require(bool(str(b.get(field, '')).strip()), field + ' 必填。')
    require(b.get('granularity') in ('equipment', 'container_group', 'part'), '请选择建模粒度。')
    require(b.get('status') in ('candidate', 'confirmed', 'excluded'), '无效对象状态。')
    if b['status'] == 'excluded': require(bool(b.get('exclusion_reason')), '排除对象需说明原因。')
    if b['status'] == 'confirmed': review_check({**b, 'review_status': 'confirmed'})
    fields = ('category_zh', 'category_en', 'granularity', 'candidate_region_id', 'anchor_image_id', 'anchor_bbox', 'parent_object_id', 'status', 'exclusion_reason')
    def change(s):
        if b.get('object_id'): obj(s, oid)
        parent = b.get('parent_object_id')
        if parent:
            obj(s, parent); require(parent != oid and b['granularity'] == 'part', '父对象只适用于明确的部件关系。')
            seen = {oid}; current = parent
            while current:
                require(current not in seen, '对象父子关系不能成环。'); seen.add(current); current = s['objects'][current].get('parent_object_id')
        if b.get('candidate_region_id'): require(b['candidate_region_id'] in {r['region_id'] for r in s['regions']}, '候选区域不存在。')
        s['objects'][oid] = {**{f: b.get(f) for f in fields}, 'object_id': oid, 'updated_at': now(), 'reviewer': actor(b), 'source': b.get('source', 'human')}
    result = update(b, 'object.save:' + oid, 2, change); return dict(state=result, object_id=oid)


@app.post('/api/sam')
def infer(b: dict):
    obj(store.read(), b.get('object_id')); im = split_check(b.get('scope'), b.get('image_id')); prompts_check(b.get('prompts', {}), im)
    return submit_job('sam', lambda: sam.predict(im, b['prompts']))


@app.get('/api/drafts/{scope}/{object_id}/{image_id}')
def get_draft(scope: str, object_id: str, image_id: str):
    split_check(scope, image_id); obj(store.read(), object_id); return store.draft(f'{scope}:{object_id}:{image_id}')


@app.put('/api/drafts/{scope}/{object_id}/{image_id}')
def save_draft(scope: str, object_id: str, image_id: str, b: dict):
    split_check(scope, image_id); obj(store.read(), object_id)
    require(len(json.dumps(b)) < 22000000, '草稿过大。')
    store.draft(f'{scope}:{object_id}:{image_id}', b); return dict(saved=True, at=now())


@app.post('/api/annotations')
def save_annotation(b: dict):
    oid, image_id, scope = b.get('object_id'), b.get('image_id'), b.get('scope')
    obj(store.read(), oid); im = split_check(scope, image_id); review_check(b)
    visibility = b.get('visibility'); require(visibility in VISIBILITY, '无效可见性。')
    uid = uuid.uuid4().hex; base = Path('priors/masks' if scope == 'priors' else 'ground_truth/heldout_masks') / oid
    annotation = dict(object_id=oid, image_id=image_id, scope=scope, width=im['width'], height=im['height'], image_sha256=im['sha256'],
                      pixel_coordinates='original_undistorted_xy', visibility=visibility, review_status=b.get('review_status', 'draft'),
                      reviewer=actor(b), reviewed_at=now() if b.get('review_status') == 'confirmed' else None,
                      notes=str(b.get('notes', '')), mask_path=None, original_mask_paths=[], final_confirmed_mask_path=None, updated_at=now())
    if visibility in VISIBLE:
        job_id = b.get('sam_job_id', ''); require(re.fullmatch(r'sam_[a-f0-9]{32}', job_id) is not None, '请先重新运行 SAM。')
        job = json.loads(safe_file(f'.inference/{job_id}/inference.json').read_text())
        require(job['image_id'] == image_id and job['image_sha256'] == im['sha256'], 'SAM 结果与当前图像不一致。')
        selected = b.get('candidate', 0); require(isinstance(selected, int) and 0 <= selected < len(job['scores']), '无效候选掩膜。')
        encoded = b.get('mask_png', ''); require(encoded.startswith('data:image/png;base64,') and len(encoded) < 22000000, '需要原分辨率 PNG 掩膜。')
        try:
            raw = base64.b64decode(encoded.split(',', 1)[1], validate=True); mask_image = Image.open(io.BytesIO(raw))
            require(mask_image.format == 'PNG' and mask_image.size == (im['width'], im['height']), '掩膜尺寸必须与原图完全一致。')
            arr = np.asarray(mask_image.convert('L')); require(np.isin(arr, [0, 255]).all(), '掩膜必须使用 0/255 二值像素。')
            require(arr.any(), '可见对象不能保存空掩膜；请使用不同的不可见状态。')
        except (OSError, TypeError) as e: raise ValueError('无法读取掩膜 PNG。') from e
        original = np.asarray(Image.open(safe_file(f'.inference/{job_id}/candidate_{selected}.png')))
        manual = not np.array_equal(arr, original)
        require(not manual or bool(b.get('edit_history')), '人工修改掩膜必须附带编辑过程。')
        folder = ROOT / base; folder.mkdir(parents=True, exist_ok=True)
        originals = []
        for i in range(len(job['scores'])):
            dest = base / 'original' / f'{job_id}_{i}.png'; (ROOT / dest).parent.mkdir(exist_ok=True)
            if not (ROOT / dest).exists(): shutil.copy2(safe_file(f'.inference/{job_id}/candidate_{i}.png'), ROOT / dest)
            originals.append(str(dest))
        atomic_json(folder / 'original' / f'{job_id}.json', job)
        final = base / 'confirmed' / f'{image_id}_{uid}.png'; (ROOT / final).parent.mkdir(exist_ok=True); Image.fromarray(arr).save(ROOT / final)
        process_path = base / 'edits' / f'{image_id}_{uid}.json'
        atomic_json(ROOT / process_path, dict(selected_candidate=selected, sam_job_id=job_id, operations=b.get('edit_history', []), action_history=b.get('action_history', []), actor=actor(b), saved_at=now()))
        ys, xs = np.where(arr > 0); box = [int(xs.min()), int(ys.min()), int(xs.max()+1), int(ys.max()+1)]
        rgb = np.asarray(Image.open(IMAGES / im['filename']).convert('RGB')); overlay = rgb.copy(); overlay[arr>0] = (rgb[arr>0]*.5+np.array([14, 190, 152])*.5).astype('uint8')
        over = base / 'overlays' / f'{image_id}_{uid}.jpg'; (ROOT / over).parent.mkdir(exist_ok=True); Image.fromarray(overlay).save(ROOT / over, quality=91)
        crop = Image.fromarray(rgb).convert('RGBA'); crop.putalpha(Image.fromarray(arr)); crop_path = base / 'overlays' / f'{image_id}_{uid}_crop.png'; crop.crop(tuple(box)).save(ROOT / crop_path)
        annotation.update(mask_path=str(final), final_confirmed_mask_path=str(final) if b.get('review_status')=='confirmed' else None,
                          original_mask_paths=originals, original_sam_mask_path=originals[selected], sam_job_id=job_id, candidate=selected,
                          prompts=job['prompts'], bbox=box, area=int((arr>0).sum()), manually_corrected=manual, edit_history_path=str(process_path),
                          overlay_path=str(over), crop_path=str(crop_path), mask_sha256=hashlib.sha256((ROOT/final).read_bytes()).hexdigest())
    else: require(not b.get('mask_png'), '未出现、完全遮挡、尚未标注应保存独立状态，不保存空掩膜。')
    key = f'{scope}:{oid}:{image_id}'
    result = update(b, 'mask.save:' + key, 3 if scope == 'priors' else 6, lambda s: s['annotations'].__setitem__(key, annotation))
    store.draft(key, {'saved_annotation_revision': result['revision']})
    return dict(state=result, annotation=annotation)


@app.post('/api/descriptions/{object_id}')
def description(object_id: str, b: dict):
    obj(store.read(), object_id); review_check(b)
    required = ['name_zh', 'name_en', 'synonyms_en', 'visual_description_en', 'visual_description_zh']
    for key in required: require(bool(b.get(key)), key + ' 必填。')
    require(isinstance(b['synonyms_en'], list) and all(isinstance(x, str) for x in b['synonyms_en']), '英文同义词应为字符串数组。')
    text = b['visual_description_en'] + ' ' + b['visual_description_zh']
    require(not re.search(r'\b(left of|right of|next to|in front of|behind)\b|位于.+[左右]侧|在.+[左右]边', text, re.I), '对象视觉描述不要写入待评价的空间关系。')
    fields = required + ['color', 'shape', 'structural_features', 'visible_parts', 'distinguishing_features', 'optional_facts']
    d = {f: b.get(f, 'unknown') for f in fields}; d.update(object_id=object_id, review_status=b.get('review_status', 'draft'), reviewer=actor(b), updated_at=now())
    d['field_sources'] = {f: dict(source=b.get('field_sources', {}).get(f, {}).get('source', b.get('source', 'human_visual_observation')),
                                review_status=d['review_status'], reviewer=actor(b), updated_at=now()) for f in fields}
    return update(b, 'description.save:' + object_id, 4, lambda s: s['descriptions'].__setitem__(object_id, d))


@app.post('/api/scene/fit')
def fit(b: dict): return fit_reference(b.get('floor_points'), b.get('origin'), b.get('heading_points'), b.get('up_hint'), b.get('units', 'sfm_relative'))


@app.post('/api/scene/pick')
def pick_reference(b: dict):
    im=image_info(b.get('image_id'));x,y=b.get('x'),b.get('y')
    require(isinstance(x,(int,float)) and isinstance(y,(int,float)) and 0<=x<im['width'] and 0<=y<im['height'],'参考像素超出图像范围。')
    path=ASSETS/'renders'/(im['image_id']+'_geometry.npz');require(path.exists(),'请先生成当前图像对应的高斯渲染，再从 RGB 或渲染图选点。')
    with np.load(path) as geometry:
        depth=geometry['depth'][0];alpha=geometry['alpha'][0];h,w=depth.shape
        px,py=int(x*w/im['width']),int(y*h/im['height']);z=float(depth[py,px])
        require(float(alpha[py,px])>.5 and np.isfinite(z) and z>0,'该像素没有足够可靠的可见表面深度，请选择清晰的地面位置。')
        # Use the center of the rendered depth pixel to avoid subpixel mismatch between resolutions.
        uv=np.array([(px+.5)*im['width']/w,(py+.5)*im['height']/h,1.0])
        point=np.asarray(im['world_to_camera_R']).T@(np.linalg.inv(np.asarray(im['K']))@uv*z-np.asarray(im['world_to_camera_t']))
    return dict(point=point.tolist(),image_id=im['image_id'],original_pixel=[x,y],depth_pixel=[px,py],depth=z,
                alpha=float(alpha[py,px]),coordinate_frame='colmap_raw',source='fresh MWP geometry render',units='sfm_relative')


@app.post('/api/scene/reference')
def save_reference(b: dict):
    review_check(b); c = b['coordinate_system']; c = fit_reference(c['floor_points'], c['origin'], c['heading_points'], c['up_hint'])
    c.update(review_status=b.get('review_status', 'draft'), reviewer=actor(b), coordinate_revision='coord_' + uuid.uuid4().hex[:12],reference_points_evidence=b.get('reference_points_evidence',[]))
    views = b.get('scene_reference_views', [])
    for v in views: image_info(v)
    if b.get('geometry_verified'): require(bool(views), '对应关系确认必须保留参考图像。')
    def change(s): s.update(coordinate_system=c, scene_reference_views=views, geometry_verified=b.get('geometry_verified', False))
    return update(b, 'scene.reference.save', 1, change)


@app.post('/api/regions')
def region(b: dict):
    review_check(b); rid = b.get('region_id') or 'region_' + uuid.uuid4().hex[:10]
    boundary = np.asarray(b.get('boundary'), float)
    require(boundary.ndim == 2 and boundary.shape[1] == 2 and len(boundary) >= 3 and np.isfinite(boundary).all(), '区域需要至少三个工业平面坐标点。')
    area = abs(np.dot(boundary[:,0], np.roll(boundary[:,1],1))-np.dot(boundary[:,1], np.roll(boundary[:,0],1)))/2
    require(area > 1e-7 and bool(b.get('name')), '区域名称必填，边界面积不能为零。')
    for v in b.get('reference_image_ids', []): image_info(v)
    def change(s):
        require(s['coordinate_system'] is not None, '先保存工业坐标系。')
        if b.get('region_id'): require(rid in {r['region_id'] for r in s['regions']}, '区域不存在。')
        record = dict(region_id=rid, name=b['name'], boundary=boundary.tolist(), coordinate_frame='industrial',
                      coordinate_revision=s['coordinate_system']['coordinate_revision'], include=bool(b.get('include', True)),
                      reference_image_ids=b.get('reference_image_ids', []), review_status=b.get('review_status', 'draft'), reviewer=actor(b))
        s['regions'] = [r for r in s['regions'] if r['region_id'] != rid] + [record]
    return update(b, 'region.save:' + rid, 1, change)


@app.post('/api/relations/schema')
def schema(b: dict):
    rows = b.get('relations', []); names = [r.get('name') for r in rows]
    require(len(names)==len(set(names)) and {'near','left_of','right_of','inside_region'} <= set(names), '关系名必须唯一并包含四个核心关系。')
    for r in rows:
        require(r.get('subject_type') == 'object' and r.get('object_type') in ('object','region'), '关系实体类型无效。')
        require(r.get('coordinate_frame') == 'industrial', '空间关系必须使用统一工业坐标系。')
        require(r.get('units') in ('sfm_relative', 'normalized'), '未标定场景不能使用米。')
        require(isinstance(r.get('directional'),bool) and bool(r.get('label_zh')) and bool(r.get('label_en')), '请填写方向性和中英文表达。')
        if r.get('inverse'): require(r['inverse'] in names, '互逆关系必须已定义。')
        if r.get('threshold') is not None: require(isinstance(r['threshold'],(int,float)) and np.isfinite(r['threshold']) and r['threshold']>0, '距离阈值必须为正数。')
    return update(b, 'relation.schema.save', 5, lambda s: s.__setitem__('relation_schema', rows))


@app.post('/api/relations/records')
def relation_record(b: dict):
    review_check(b); collection = b.get('collection'); require(collection in ('known_relations','reference_relations'), '请选择先验或独立评价。')
    rid = b.get('relation_id') or 'rel_' + uuid.uuid4().hex[:12]
    def change(s):
        obj(s,b.get('subject_id')); definition = next((r for r in s['relation_schema'] if r['name']==b.get('relation_type')), None)
        require(definition is not None,'关系类型未定义。')
        if definition['object_type']=='object': obj(s,b.get('object_id')); require(b['object_id']!=b['subject_id'],'不能标注自身关系。')
        else: require(b.get('region_id') in {r['region_id'] for r in s['regions']},'区域不存在。')
        require(bool(b.get('evidence')), '请记录关系证据。')
        if collection=='reference_relations': require(b.get('expected_label') in ('true','false','unknown'),'评价标签应为 true/false/unknown。')
        else: require(bool(b.get('knowledge_reason')), '先验关系需要说明为何不能可靠地由几何计算获得。')
        rec={k:b.get(k) for k in ['subject_id','relation_type','object_id','region_id','expected_label','evidence','knowledge_reason']}
        rec.update(relation_id=rid, review_status=b.get('review_status','draft'),reviewer=actor(b),coordinate_frame='industrial')
        other = 'known_relations' if collection=='reference_relations' else 'reference_relations'
        require(relation_signature(rec,s['relation_schema']) not in {relation_signature(r,s['relation_schema']) for r in s[other]},'该关系（含互逆/对称形式）已在另一数据用途出现，禁止评价泄漏。')
        s[collection]=[r for r in s[collection] if r['relation_id']!=rid]+[rec]
    return update(b,'relation.record.save:'+rid,5 if collection=='known_relations' else 6,change)


@app.post('/api/evaluation/queries')
def query(b: dict):
    review_check(b); collection=b.get('collection'); require(collection in ('semantic_queries','relational_queries'),'无效评价集合。')
    require(b.get('query_type') in QUERY_TYPES and bool(b.get('query_text')) and bool(b.get('evidence')),'查询类型、文本和证据必填。')
    expected=b.get('expected_object_ids'); require(isinstance(expected,list) and len(expected)==len(set(expected)),'答案必须是唯一对象 ID 数组。')
    require(b.get('allow_multiple') or len(expected)<=1,'多个答案需要显式允许。')
    require(bool(expected) or b['query_type']=='no_match','空答案只用于明确的无匹配查询。')
    require(b['query_type']!='no_match' or not expected,'无匹配查询答案应为空。')
    qid=b.get('query_id') or 'query_'+uuid.uuid4().hex[:12]
    def change(s):
        for oid in expected:
            require(obj(s,oid)['status']!='excluded','排除对象不能作为评价答案。')
            if collection=='semantic_queries':
                d=s['descriptions'].get(oid,{})
                require(b['query_text'].strip().lower() not in [str(d.get(k,'')).strip().lower() for k in ('name_en','name_zh','visual_description_en','visual_description_zh')],'语义评价查询不能直接复制输入名称或描述。')
        q={k:b.get(k) for k in ['query_text','query_type','expected_object_ids','allow_multiple','evidence','review_status']}
        q.update(query_id=qid,reviewer=actor(b));s[collection]=[q0 for q0 in s[collection] if q0['query_id']!=qid]+[q]
    return update(b,'evaluation.query.save:'+qid,6,change)


@app.post('/api/coarse-roi/{object_id}')
def coarse_roi(object_id: str, b: dict):
    s=store.read();obj(s,object_id)
    anns=[a for a in s['annotations'].values() if a['object_id']==object_id and a['scope']=='priors' and a['visibility'] in VISIBLE and a['review_status']=='confirmed']
    require(len(anns)>=2,'粗略 ROI 需要至少两个确认的训练掩膜，不能使用评价掩膜。')
    from plyfile import PlyData
    v=PlyData.read(str(GAUSSIANS))['vertex'];xyz=np.column_stack([v[k] for k in ('x','y','z')]);keep=np.ones(len(xyz),bool)
    for a in anns:
        uv,valid=project(xyz,images[a['image_id']]); idx=np.where(valid)[0];uv=uv[idx].astype(int);mask=np.asarray(Image.open(safe_file(a['mask_path'])))>0
        inside=np.zeros(len(xyz),bool);inside[idx]=mask[uv[:,1],uv[:,0]];keep &= inside
    require(keep.sum()>=5,'共同可见几何点不足，无法生成可靠候选范围。')
    c=s['coordinate_system'];require(c is not None,'先建立工业坐标系。')
    pts=xyz[keep]@np.asarray(c['transform'])[:3,:3].T+np.asarray(c['transform'])[:3,3]
    rec=dict(object_id=object_id,coordinate_frame='industrial',coordinate_revision=c['coordinate_revision'],purpose='M2 search restriction only; not final instance membership or final bounding box',
             min=pts.min(0).tolist(),max=pts.max(0).tolist(),candidate_count=int(keep.sum()),source_masks=[a['mask_sha256'] for a in anns],review_status='draft')
    return update(b,'coarse_roi.estimate:'+object_id,3,lambda s:s['coarse_rois'].__setitem__(object_id,rec))


@app.get('/api/quality')
def checks(): return quality(store.read(),ROOT,images)


@app.post('/api/coarse-roi/{object_id}/clear')
def clear_coarse_roi(object_id: str, b: dict):
    obj(store.read(),object_id)
    return update(b,'coarse_roi.clear:'+object_id,3,lambda s:s['coarse_rois'].pop(object_id,None))


@app.post('/api/steps/{step}/confirm')
def confirm_step(step: int,b:dict):
    require(1<=step<=6,'无效步骤。');review_check({**b,'review_status':'confirmed'})
    def change(s):
        q=quality(s,ROOT,images);fail=[i['message'] for i in q['issues'] if i['step']==step and i['severity']=='error']
        require(not fail,'当前步骤尚未满足条件：'+'；'.join(fail[:5]))
        s['approvals'][str(step)]=dict(reviewer=actor(b),at=now(),revision=s['revision']+1)
        s['stale_steps']=[n for n in s['stale_steps'] if n!=step]
    return update(b,'step.confirm:'+str(step),0,change)


@app.get('/api/history')
def history(): return store.history()


@app.get('/api/form-drafts')
def form_drafts(): return store.draft('form-drafts')


@app.put('/api/form-drafts')
def save_form_drafts(b: dict):
    require(len(json.dumps(b)) < 1000000, '表单草稿过大。')
    return store.draft('form-drafts', b)


def export_version(version,scope):
    require(scope in ('priors','ground_truth'),'导出用途必须明确。')
    folder=ROOT/'versions'/version;require(folder.is_dir(),'版本不存在。')
    frozen=json.loads((folder/'FREEZE.json').read_text())
    for name,digest in frozen['files'].items():
        p=folder/name
        require(p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==digest,'冻结版本文件校验失败：'+name)
    target=folder/(scope+'.zip')
    if not target.exists():
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
            for p in sorted((folder/scope).rglob('*')):
                if p.is_file(): archive.write(p,str(p.relative_to(folder)))
            for name in ['PRIOR_MANIFEST.json','SOURCE_MANIFEST.json','FREEZE.json']:
                archive.write(folder/name,name)
    return target


@app.post('/api/freeze')
def freeze(b:dict):
    review_check({**b,'review_status':'confirmed'})
    with freeze_lock,store.lock:
        s=store.read();require(s['revision']==b.get('revision'),'REVISION_CONFLICT: 数据已更新。')
        q=quality(s,ROOT,images);require(q['can_freeze'],'数据尚未通过全部质量检查和六个步骤的人工确认。')
        from .prepare import sha
        source=json.loads((ASSETS/'source_manifest.json').read_text())
        for f in source['source_files']:
            require(sha(PROJECT/f['path'])==f['sha256'],'几何、相机、划分或模型来源已变化，请重新检查：'+f['path'])
        for im in images.values(): require(sha(IMAGES/im['filename'])==im['sha256'],'原始图像发生变化：'+im['image_id'])
        version='m0_'+now().replace(':','').replace('-','').split('.')[0]+'_'+str(s['revision'])
        folder=ROOT/'versions'/version;require(not folder.exists(),'版本已存在。');folder.mkdir(parents=True)
        for name in ['priors','ground_truth']:shutil.copytree(ROOT/name,folder/name)
        # All masks and editing provenance stay in the appropriate isolated scope.
        for name in ['PRIOR_MANIFEST.json']:shutil.copy2(ROOT/name,folder/name)
        shutil.copy2(ASSETS/'source_manifest.json',folder/'SOURCE_MANIFEST.json')
        hashes={str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}
        atomic_json(folder/'FREEZE.json',dict(version=version,revision=s['revision'],frozen_at=now(),reviewer=actor(b),files=hashes,quality=q))
        update(b,'version.freeze:'+version,0,lambda x:x.__setitem__('last_frozen_version',version))
        return dict(version=version,priors_url=f'/api/exports/{version}/priors',ground_truth_url=f'/api/exports/{version}/ground_truth')


@app.get('/api/versions')
def versions():
    folder=ROOT/'versions'
    return [json.loads(p.read_text()) for p in sorted(folder.glob('*/FREEZE.json'),reverse=True)] if folder.exists() else []


@app.get('/api/exports/{version}/{scope}')
def export(version:str,scope:str):
    require(re.fullmatch(r'm0_[A-Za-z0-9_]+',version) is not None,'无效版本。')
    return FileResponse(export_version(version,scope),filename=f'{version}_{scope}.zip')


@app.get('/')
def index(): return FileResponse(STATIC/'index.html')


app.mount('/static',StaticFiles(directory=str(STATIC)),name='static')
