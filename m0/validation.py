"""V2 validates only coarse spatial/text priors; no seven-step or evaluation requirements."""
import re
import numpy as np
from .spatial import corners,inside

def require(condition,message):
    if not condition:raise ValueError(message)

def box_check(box):
    require(isinstance(box,dict),'需要三维框。')
    c=np.asarray(box.get('center'),dtype=float);s=np.asarray(box.get('size'),dtype=float)
    require(c.shape==(3,) and s.shape==(3,) and np.isfinite(c).all() and np.isfinite(s).all(),'包围框中心和尺寸必须为有限三维坐标。')
    require(np.all(s>1e-5) and np.all(s<1e5),'三维框尺寸须大于零且在有效范围内。')
    return dict(center=c.tolist(),size=s.tolist())

def transform_check(matrix):
    t=np.asarray(matrix,dtype=float)
    require(t.shape==(4,4) and np.isfinite(t).all(),'需要有限的 4×4 转换矩阵。')
    require(np.allclose(t[3],[0,0,0,1],atol=1e-6) and np.allclose(t[:3,:3]@t[:3,:3].T,np.eye(3),atol=1e-5) and abs(np.linalg.det(t[:3,:3])-1)<1e-5,'坐标转换必须为右手刚体变换，不允许缩放或反射。')
    return t

def review_check(b):
    if b.get('status')=='confirmed':require(b.get('review_ack') is True and bool(str(b.get('reviewer','')).strip()),'确认前请填写审核人并勾选人工核对。')

def text_check(b,confirmed=False):
    for f in ('name_zh','name_en','description_zh','description_en'):
        require(isinstance(b.get(f,''),str) and len(b.get(f,''))<3000,'名称或描述格式无效。')
        if confirmed:require(bool(b.get(f,'').strip()) and b[f].strip().lower()!='unknown',f+' 尚未填写确认内容。')
    content=b.get('description_zh','')+' '+b.get('description_en','')
    require(not re.search(r'\b(left of|right of|next to|in front of|behind)\b|位于.+[左右]侧|在.+[左右]边',content,re.I),'基础描述只描述对象本身，不填设备间空间关系。')

def prompts_check(p,im):
    box=p.get('bbox');points=p.get('points',[]);labels=p.get('labels',[])
    require(box is not None or len(points)>0,'至少需要提示框或正负点。')
    if box is not None:
        a=np.asarray(box,dtype=float);require(a.shape==(4,) and np.isfinite(a).all(),'提示框格式无效。')
        require(0<=a[0]<a[2]<=im['width'] and 0<=a[1]<a[3]<=im['height'],'提示框必须在原图范围内。')
    require(len(points)==len(labels) and len(points)<=200,'提示点与标签数量不匹配。')
    for p,l in zip(points,labels):require(len(p)==2 and np.isfinite(p).all() and 0<=p[0]<im['width'] and 0<=p[1]<im['height'] and l in (0,1),'提示点或标签无效。')

def quality(s):
    issues=[];scene=s['scene'];objects=[o for o in s['objects'].values() if not o.get('deleted')]
    def error(msg,oid=None):issues.append(dict(severity='error',message=msg,object_id=oid))
    if scene['status']!='confirmed':error('请确认场景范围、底面与方向。')
    if not scene['floor_confirmed'] or not scene['directions_confirmed']:error('场景底面和空间方向尚未人工核对。')
    if not objects:error('至少保存一个工业对象。')
    for o in objects:
        oid=o['object_id']
        if o['status']!='confirmed':error('对象 '+(o['name_zh'] or oid)+' 尚未确认。',oid)
        if o['coordinate_version']!=scene['coordinate_version']:error('对象坐标版本已过期，请重新核对粗框。',oid)
        if not inside(corners(o['bbox']),scene['bbox']).all():error('对象粗框超出场景范围，请调整场景或设备框。',oid)
        try:text_check(o,True)
        except ValueError as e:error(str(e),oid)
        ref=o.get('reference')
        if ref and ref['status']!='confirmed':issues.append(dict(severity='warning',object_id=oid,message='可选参考掩膜为草稿，不会进入导出；可继续确认或移除。'))
    if len(objects)<5:issues.append(dict(severity='warning',message='首轮建议 5–8 个代表性对象；单对象也可保存和导出。',object_id=None))
    return dict(can_freeze=not any(i['severity']=='error' for i in issues),issues=issues,objects=len(objects),confirmed=sum(o['status']=='confirmed' for o in objects),optional_references=sum(bool(o.get('reference')) for o in objects))
