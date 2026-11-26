"""Geometry and unchanged baseline visibility, independent of SAM/CLIP."""
import itertools
import numpy as np
from scipy.spatial import cKDTree, ConvexHull
from m0.spatial import corners, transform, box_rotation


def unit(vector):
    vector=np.asarray(vector,dtype=float)
    return vector/max(np.linalg.norm(vector),1e-12)


def project(points, camera):
    p=np.asarray(points)@np.asarray(camera['world_to_camera_R']).T+camera['world_to_camera_t']
    uvw=p@np.asarray(camera['K']).T
    return uvw[:,:2]/np.maximum(p[:,2,None],1e-10),p[:,2]


def box_projection(box, transform_matrix, camera):
    """Clip box edges at the near plane so useful truncated observations survive."""
    raw=transform(corners(box),np.linalg.inv(transform_matrix))
    p=raw@np.asarray(camera['world_to_camera_R']).T+camera['world_to_camera_t']
    near=.01;points=[v for v in p if v[2]>=near]
    signs=list(itertools.product([-1,1],repeat=3))
    for i in range(8):
        for j in range(i):
            if sum(a!=b for a,b in zip(signs[i],signs[j]))!=1:continue
            if (p[i,2]>=near)!=(p[j,2]>=near):
                t=(near-p[i,2])/(p[j,2]-p[i,2]);points.append(p[i]+t*(p[j]-p[i]))
    if not points:return None
    points=np.array(points);uv=points@np.array(camera['K']).T;uv=uv[:,:2]/points[:,2,None]
    lo=uv.min(0);hi=uv.max(0);clo=np.maximum(lo,0);chi=np.minimum(hi,[camera['width']-1,camera['height']-1])
    if np.any(chi-clo<8):return None
    return dict(bbox=[*clo.tolist(),*chi.tolist()],unclipped_bbox=[*lo.tolist(),*hi.tolist()],
                area_fraction=float(np.prod(chi-clo)/(camera['width']*camera['height'])),
                image_coverage=float(np.prod(chi-clo)/max(np.prod(hi-lo),1e-12)),near_plane_clipped=bool(np.any(p[:,2]<near)))


def visible_centers(xyz, scales, ids, camera, moments, cfg):
    """Exactly the baseline Context.visibility definition, using already loaded arrays."""
    uv,z=project(xyz[ids],camera);pixels=np.rint(uv).astype(np.int32)
    valid=(z>.01)&(pixels[:,0]>=0)&(pixels[:,0]<camera['width'])&(pixels[:,1]>=0)&(pixels[:,1]<camera['height'])
    local=np.flatnonzero(valid)
    if not len(local):return local,pixels[local],np.empty(0,np.float32)
    px=pixels[local];x,y=px.T
    d=moments['depth'][y,x].astype(float);std=moments['std'][y,x].astype(float);alpha=moments['alpha'][y,x].astype(float)
    tol=cfg['absolute_depth_tolerance']+cfg['relative_depth_tolerance']*z[local]+np.minimum(std,cfg['maximum_std_allowance'])+np.minimum(scales[ids[local]],cfg['gaussian_scale_allowance'])
    error=abs(z[local]-d)
    valid=(alpha>=cfg['minimum_alpha'])&(std<=cfg['maximum_depth_std'])&(error<=tol)&(d>0)
    weights=alpha*np.exp(-.5*(error/np.maximum(tol,1e-8))**2)
    return local[valid],px[valid],weights[valid].astype(np.float32)


def look_at(eye, center, T, width, height, fov):
    eye=np.asarray(eye);forward=unit(np.asarray(center)-eye);up=np.array([0.,0.,1.])
    if abs(forward@up)>.98:up=np.array([0.,1.,0.])
    right=unit(np.cross(forward,up));up=np.cross(right,forward)
    pose=np.eye(4);pose[:3,:3]=np.stack([right,up,-forward],1);pose[:3,3]=eye
    raw=np.linalg.inv(T)@pose;R=np.diag([1,-1,-1])@raw[:3,:3].T;t=-R@raw[:3,3]
    focal=width/(2*np.tan(np.deg2rad(fov)/2))
    return dict(width=width,height=height,K=[[float(focal),0.,(width-1)/2],[0.,float(focal),(height-1)/2],[0.,0.,1.]],
                world_to_camera_R=R.tolist(),world_to_camera_t=t.tolist(),center=raw[:3,3].tolist(),industrial_eye=eye.tolist(),horizontal_fov_degrees=float(fov))


def framed_camera(eye, box, T, cfg):
    camera=look_at(eye,box['center'],T,cfg['width'],cfg['height'],cfg['fov_degrees'])
    raw=transform(corners(box),np.linalg.inv(T));p=raw@np.array(camera['world_to_camera_R']).T+camera['world_to_camera_t']
    if np.any(p[:,2]<=.02):return None,'Target box crosses the camera near plane'
    ratios=np.abs(p[:,:2]/p[:,2,None]);required=max(ratios[:,0].max(),ratios[:,1].max()*cfg['width']/cfg['height'])/(1-cfg['framing_margin'])
    fov=np.rad2deg(2*np.arctan(required))
    if fov>cfg['maximum_fov_degrees']:return None,'Required field of view exceeds the configured reliability limit'
    return look_at(eye,box['center'],T,cfg['width'],cfg['height'],max(fov,cfg['minimum_fov_degrees'])),None


def fit_distance(direction, box, cfg):
    """Find a box-fitting distance by a short deterministic geometric search."""
    center=np.array(box['center']);direction=unit(direction)
    for distance in np.linspace(max(.35,np.linalg.norm(box['size'])/2),max(1.,np.linalg.norm(box['size'])*3),60):
        cam=look_at(center+direction*distance,center,np.eye(4),cfg['width'],cfg['height'],cfg['fov_degrees'])
        projection=box_projection(box,np.eye(4),cam)
        if projection and not projection['near_plane_clipped'] and projection['image_coverage']>.999:
            x0,y0,x1,y1=projection['bbox'];m=cfg['framing_margin']/2
            if x0>=m*cfg['width'] and x1<=(1-m)*cfg['width'] and y0>=m*cfg['height'] and y1<=(1-m)*cfg['height']:return float(distance)
    return float(np.linalg.norm(box['size'])*3)


class CameraSafety:
    def __init__(self, inputs, cfg):
        self.cfg=cfg;self.inputs=inputs;self.eyes=transform([im['center'] for im in inputs.train],inputs.T)
        self.camera_tree=cKDTree(self.eyes);self.hull=ConvexHull(self.eyes[:,:2])
        keep=(inputs.opacity>=cfg['opaque_tree_minimum_opacity'])&(inputs.scales<=cfg['opaque_tree_maximum_scale'])
        self.surface_ids=np.flatnonzero(keep);self.surface_tree=cKDTree(inputs.industrial[self.surface_ids])
        self.maximum_height=float(self.eyes[:,2].max()+cfg['maximum_height_above_training'])
    def evaluate(self, eye, target):
        eye=np.array(eye);cfg=self.cfg;reasons=[];distance,index=self.camera_tree.query(eye)
        signed=self.hull.equations[:,:2]@eye[:2]+self.hull.equations[:,2]
        outside=max(0.,float(signed.max()))
        near,idx=self.surface_tree.query(eye,k=16);near=np.atleast_1d(near);idx=np.atleast_1d(idx)
        surface_scales=self.inputs.scales[self.surface_ids[idx]]
        clearance=float(near.min());intersects=bool(np.any(near<np.maximum(cfg['minimum_surface_clearance'],surface_scales*.8)))
        if not cfg['minimum_camera_height']<=eye[2]<=self.maximum_height:reasons.append('Outside supported camera height interval')
        if outside>cfg['trajectory_hull_margin']:reasons.append('Outside expanded training-trajectory XY hull')
        if distance>cfg['maximum_trajectory_distance']:reasons.append('Too far from the original training trajectory')
        if intersects:reasons.append('Camera too close to an opaque Gaussian surface')
        inside=[]
        for obj in self.inputs.objects:
            b=obj['bbox'];q=(eye-b['center'])@box_rotation(b)
            if np.all(abs(q)<=np.array(b['size'])/2+cfg['object_box_margin']):inside.append(obj['object_id'])
        if inside:reasons.append('Camera lies inside an expanded M0 object box')
        direction=unit(eye-target);directions=np.array([unit(e-target) for e in self.eyes]);gap=float(np.rad2deg(np.arccos(np.clip((directions@direction).max(),-1,1))))
        if gap>cfg['maximum_direction_gap_degrees']:reasons.append('Viewing direction unsupported by training cameras')
        reliability=float(np.exp(-.5*(distance/cfg['maximum_trajectory_distance'])**2)*np.cos(np.deg2rad(min(gap,89))))
        return dict(accepted=not reasons,reasons=reasons,nearest_training_image_id=self.inputs.train[int(index)]['image_id'],nearest_trajectory_distance=float(distance),outside_trajectory_hull=outside,nearest_surface_distance=clearance,inside_object_ids=inside,minimum_training_direction_gap_degrees=gap,trajectory_reliability=reliability)


def virtual_proposals(obj, inputs, real_rows, safety, cfg):
    center=np.array(obj['bbox']['center']);eyes=safety.eyes;directions=np.array([unit(e-center) for e in eyes])
    by_id={r['image_id']:r for r in real_rows};scores=[]
    for index,im in enumerate(inputs.train):
        row=by_id[im['image_id']];distance=np.linalg.norm(eyes[index]-center)
        scores.append((.3+.7*row.get('quality',0))/(.25+distance))
    chosen=[];pool=list(range(len(eyes)))
    while pool and len(chosen)<cfg['guided_seeds']:
        def value(index):
            angle=90 if not chosen else min(np.rad2deg(np.arccos(np.clip(directions[index]@directions[j],-1,1))) for j in chosen)
            return scores[index]*(.15+.85*min(angle/45,1))
        index=max(pool,key=value);chosen.append(index);pool=[j for j in pool if np.linalg.norm(eyes[j]-eyes[index])>.04]
    proposals=[]
    for index in chosen:
        for offset in cfg['guided_offsets']:
            eye=eyes[index]+offset
            proposals.append(dict(source_type='camera_guided_virtual',parent_image_id=inputs.train[index]['image_id'],industrial_eye=eye.tolist(),generation=dict(method='Original camera position retargeted and adaptively reframed',industrial_offset=offset)))
    # Cardinal equipment faces plus oblique directions toward supported camera regions.
    preferred=unit(eyes[chosen[0]]-center);horizontal=unit([preferred[0],preferred[1],0])
    obliques=[]
    for degrees in [-40,0,40]:
        a=np.deg2rad(degrees);v=np.array([horizontal[0]*np.cos(a)-horizontal[1]*np.sin(a),horizontal[0]*np.sin(a)+horizontal[1]*np.cos(a),0.])
        for elevation in [.35,.8]:obliques.append((f'trajectory_oblique_{degrees}_{elevation}',unit(v+[0,0,elevation])))
    directions_named=[('front',unit([0,-1,.35])),('back',unit([0,1,.35])),('left',unit([-1,0,.35])),('right',unit([1,0,.35]))]+obliques
    free=[]
    for name,direction in directions_named:
        distance=fit_distance(direction,obj['bbox'],cfg)
        for multiplier in cfg['distance_multipliers']:
            eye=center+direction*distance*multiplier;check=safety.evaluate(eye,center)
            free.append(dict(source_type='object_guided_virtual',parent_image_id=None,industrial_eye=eye.tolist(),generation=dict(method='Object-box size fitting in industrial coordinates',direction=name,distance=distance*multiplier),safety=check))
    free.sort(key=lambda p:(p['safety']['accepted'],p['safety']['trajectory_reliability']),reverse=True)
    # Keep rejected proposals for diagnosis, but limit actual full-scene renders.
    accepted=0
    for proposal in free:
        if proposal['safety']['accepted']:
            accepted+=1
            if accepted>cfg['free_maximum_candidates']:proposal['generation_limit_rejection']=True
    return proposals+free
