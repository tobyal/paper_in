import json
from pathlib import Path
import re
import numpy as np
from PIL import Image

VISIBLE = ('clear', 'partial', 'uncertain')
VISIBILITY = (*VISIBLE, 'not_present', 'fully_occluded', 'unannotated')
QUERY_TYPES = ('category', 'attribute', 'region', 'relation', 'disambiguation', 'multi_condition', 'no_match')


def require(condition, message):
    if not condition: raise ValueError(message)


def bbox_check(box, image):
    require(isinstance(box, list) and len(box) == 4, '目标框需要 [x0,y0,x1,y1]。')
    a = np.asarray(box, float)
    require(np.isfinite(a).all() and 0 <= a[0] < a[2] <= image['width'] and 0 <= a[1] < a[3] <= image['height'], '目标框超出原图或宽高为零。')


def prompts_check(p, image):
    box, points, labels = p.get('bbox'), p.get('points', []), p.get('labels', [])
    if box is not None: bbox_check(box, image)
    require(box is not None or len(points) > 0, '请先画目标框或添加提示点。')
    require(len(points) == len(labels) <= 200, '提示点与标签数量不一致或过多。')
    for point, label in zip(points, labels):
        require(isinstance(point, list) and len(point) == 2 and label in (0, 1), '无效提示点。')
        require(0 <= point[0] < image['width'] and 0 <= point[1] < image['height'], '提示点超出原图。')


def review_check(body):
    status = body.get('review_status', 'draft')
    require(status in ('draft', 'confirmed', 'needs_review'), '无效审核状态。')
    if status == 'confirmed':
        require(body.get('review_ack') is True and bool(str(body.get('reviewer', '')).strip()), '确认前请填写审核人，并勾选已检查真实图像。')


def relation_signature(record, schema):
    r = next((r for r in schema if r['name'] == record['relation_type']), {})
    a, b, name = record['subject_id'], record.get('object_id') or record.get('region_id'), record['relation_type']
    if not r.get('directional', True): return (name, *sorted([a, b]))
    if r.get('inverse') and r['inverse'] < name: return (r['inverse'], b, a)
    return name, a, b


def quality(s, root, images):
    issues = []
    def issue(step, code, text, severity='error', **target):
        issues.append(dict(step=step, code=code, message=text, severity=severity, target=target))
    coord = s['coordinate_system']
    if not coord or coord.get('review_status') != 'confirmed': issue(1, 'coordinate', '工业坐标系尚未人工确认。')
    if not s['geometry_verified']: issue(1, 'correspondence', '请核对 RGB、渲染和相机的对应关系。')
    included = [r for r in s['regions'] if r.get('include')]
    if not included: issue(1, 'regions', '至少定义一个纳入建模的区域。')
    for r in s['regions']:
        if r.get('coordinate_frame') != 'industrial' or r.get('coordinate_revision') != (coord or {}).get('coordinate_revision'):
            issue(1, 'region_frame', f'{r["region_id"]} 需要在当前坐标系下重新确认。')
        if r.get('review_status') != 'confirmed': issue(1, 'region_review', f'{r["name"]} 尚未确认。')
    objects = [o for o in s['objects'].values() if o['status'] != 'excluded']
    if not objects: issue(2, 'objects', '尚未创建纳入建模的对象。')
    if len(objects) < 5: issue(2, 'pilot_size', '首批建议选择 5–8 个对象；当前可先验证单对象闭环。', 'warning')
    arrays = {}
    for o in objects:
        oid = o['object_id']
        from .settings import IMAGES
        anchor = images.get(o['anchor_image_id'])
        if not anchor or not (IMAGES / anchor['filename']).is_file(): issue(2, 'anchor_file', f'{oid} 主参考图不存在。', object_id=oid)
        if o['status'] != 'confirmed': issue(2, 'object_review', f'{oid} 对象身份尚未确认。', object_id=oid)
        if not o.get('candidate_region_id') or o['candidate_region_id'] not in {r['region_id'] for r in included}:
            issue(2, 'candidate_region', f'{oid} 尚未绑定有效建模区域。', object_id=oid)
        anns = [a for a in s['annotations'].values() if a['object_id'] == oid]
        valid_train = [a for a in anns if a['scope'] == 'priors' and a['visibility'] in VISIBLE and a['review_status'] == 'confirmed']
        valid_test = [a for a in anns if a['scope'] == 'ground_truth' and a['visibility'] in VISIBLE and a['review_status'] == 'confirmed']
        if len(valid_train) < 2: issue(3, 'view_count', f'{oid} 至少需要两个确认的训练视角。', object_id=oid)
        roi=s['coarse_rois'].get(oid)
        if roi and (roi.get('coordinate_revision')!=(coord or {}).get('coordinate_revision') or sorted(roi.get('source_masks',[]))!=sorted(a['mask_sha256'] for a in valid_train)):
            issue(3, 'stale_roi', f'{oid} 粗略 ROI 的坐标系或来源掩膜已改变，请重新估计或清除。', object_id=oid)
        if len(valid_train) >= 2:
            vectors = np.array([images[a['image_id']]['forward'] for a in valid_train]); cos = np.clip(vectors @ vectors.T, -1, 1)
            angle = float(np.rad2deg(np.arccos(cos.min())))
            if angle < 10: issue(3, 'view_diversity', f'{oid} 相机朝向最大夹角仅 {angle:.1f}°，请检查是否具有足够不同的观察方向。', 'warning', object_id=oid)
        if not valid_test: issue(6, 'heldout_count', f'{oid} 尚无独立留出视角的确认掩膜。', object_id=oid, scope='ground_truth')
        desc = s['descriptions'].get(oid, {})
        if desc.get('review_status') != 'confirmed': issue(4, 'description', f'{oid} 视觉描述尚未确认。', object_id=oid)
        for a in anns:
            step = 3 if a['scope'] == 'priors' else 6
            target = dict(object_id=oid, image_id=a['image_id'], scope=a['scope'])
            if a['visibility'] == 'unannotated': issue(step, 'unannotated', f'{oid}/{a["image_id"]} 尚未标注。', **target); continue
            if a['review_status'] != 'confirmed': issue(step, 'mask_review', f'{oid}/{a["image_id"]} 未人工确认。', **target)
            im = images.get(a['image_id'])
            if not im or im['split'] != ('train' if a['scope'] == 'priors' else 'heldout'): issue(step, 'split_leak', '建模与评价视角混用。', **target); continue
            if a['visibility'] not in VISIBLE:
                if a.get('mask_path'): issue(step, 'absence_mask', '不可见状态不应保存掩膜负样本。', **target)
                continue
            try:
                with Image.open(Path(root) / a['mask_path']) as m: arr = np.asarray(m).copy()
                if arr.shape != (im['height'], im['width']) or not arr.any(): raise ValueError('尺寸错误或空掩膜')
                import hashlib
                if hashlib.sha256((Path(root) / a['mask_path']).read_bytes()).hexdigest() != a.get('mask_sha256'): raise ValueError('掩膜内容在保存后发生变化')
                arrays[(a['scope'], a['image_id'], oid)] = arr > 0
                for p in a['original_mask_paths']:
                    if not (Path(root) / p).is_file(): raise ValueError('原始 SAM 掩膜缺失')
            except (OSError, ValueError, KeyError, TypeError) as e: issue(step, 'mask_file', f'掩膜文件异常：{e}', **target)
    for (scope, image, oid), a in arrays.items():
        for (scope2, image2, oid2), b in arrays.items():
            if scope != scope2 or image != image2 or oid >= oid2: continue
            if s['objects'][oid].get('parent_object_id') == oid2 or s['objects'][oid2].get('parent_object_id') == oid: continue
            overlap = np.count_nonzero(a & b) / max(1, min(np.count_nonzero(a), np.count_nonzero(b)))
            if overlap > .35: issue(3 if scope == 'priors' else 6, 'instance_overlap', f'{oid} 与 {oid2} 的较小掩膜有 {overlap:.0%} 重叠，请检查实例绑定。', object_id=oid, image_id=image, scope=scope)
    core = {'near', 'left_of', 'right_of', 'inside_region'}
    if not core <= {r['name'] for r in s['relation_schema']}: issue(5, 'relation_core', '核心关系定义不完整。')
    for r in s['relation_schema']:
        if not r.get('rule'): issue(5, 'relation_rule', f'{r["name"]} 尚无明确判定规则。')
        if r['name'] == 'near' and (r.get('threshold') is None or not r.get('distance_definition')): issue(5, 'near_rule', '邻近关系需要距离定义、阈值及单位。')
    known = {relation_signature(r, s['relation_schema']) for r in s['known_relations']}
    for collection, step in [('known_relations', 5), ('reference_relations', 6)]:
        for r in s[collection]:
            entities = [r['subject_id']] + ([r['object_id']] if r.get('object_id') else [])
            if any(x not in s['objects'] or s['objects'][x]['status']=='excluded' for x in entities): issue(step, 'relation_entities', '关系引用了不存在或已排除的对象。')
            if r.get('relation_type') not in {x['name'] for x in s['relation_schema']}: issue(step, 'relation_type', '关系记录引用了已移除的关系定义。')
            if r.get('region_id') and r['region_id'] not in {x['region_id'] for x in s['regions']}: issue(step, 'relation_region', '关系引用区域不存在。')
            if r.get('review_status') != 'confirmed': issue(step, 'relation_review', f'{r["relation_id"]} 尚未确认。')
            if collection == 'reference_relations' and relation_signature(r, s['relation_schema']) in known: issue(6, 'relation_leak', '评价关系与先验关系重复（含互逆关系）。')
            if collection == 'reference_relations' and r.get('expected_label') == 'unknown': issue(6, 'relation_unknown', '不确定关系保留为 unknown，冻结评价前需澄清或移出评价集。')
    labels = {r['expected_label'] for r in s['reference_relations'] if r.get('review_status') == 'confirmed'}
    if not {'true', 'false'} <= labels: issue(6, 'relation_balance', '独立关系评价至少包含成立与不成立实例。')
    if not s['semantic_queries']: issue(6, 'semantic_queries', '尚无独立语义查询。')
    types = {q['query_type'] for q in s['relational_queries']}
    for missing in set(QUERY_TYPES)-types: issue(6, 'query_coverage', f'缺少 {missing} 类型查询。')
    for collection in ['semantic_queries', 'relational_queries']:
        for q in s[collection]:
            if q.get('review_status') != 'confirmed': issue(6, 'query_review', f'{q["query_id"]} 尚未确认。')
            if any(oid not in s['objects'] or s['objects'][oid]['status']=='excluded' for oid in q.get('expected_object_ids',[])): issue(6, 'query_entities', '查询答案引用了不存在或已排除的对象。')
    steps = []
    for n in range(1, 8):
        errors = [i for i in issues if i['step'] == n and i['severity'] == 'error']
        approved = str(n) in s['approvals']
        if n == 7: complete = not any(i['severity'] == 'error' for i in issues) and all(str(k) in s['approvals'] for k in range(1, 7))
        else: complete = not errors and approved and n not in s['stale_steps']
        steps.append(dict(step=n, complete=complete, errors=len(errors), approved=approved, stale=n in s['stale_steps']))
    return dict(revision=s['revision'], issues=issues, steps=steps, can_freeze=steps[-1]['complete'],
                counts=dict(objects=len(objects), confirmed_objects=sum(o['status']=='confirmed' for o in objects), regions=len(included),
                            prior_masks=sum(a['scope']=='priors' and a['visibility'] in VISIBLE for a in s['annotations'].values()),
                            heldout_masks=sum(a['scope']=='ground_truth' and a['visibility'] in VISIBLE for a in s['annotations'].values())))
