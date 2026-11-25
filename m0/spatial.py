"""M0 geometry only: coordinate frames, coarse boxes and single-reference projection."""
import itertools
import numpy as np
from PIL import Image, ImageDraw


def transform(points, matrix):
    t = np.asarray(matrix, dtype=float)
    return np.asarray(points) @ t[:3, :3].T + t[:3, 3]


def corners(box):
    c, s = np.asarray(box['center']), np.asarray(box['size'])
    return c + np.array(list(itertools.product([-1, 1], repeat=3))) * s / 2


def inside(points, box):
    return np.all(np.abs(points - np.asarray(box['center'])) <= np.asarray(box['size']) / 2 + 1e-7, axis=1)


def initialize(xyz, images):
    """Deterministic geometry-only candidate. Human must verify floor and directions."""
    rng = np.random.default_rng(20261125)
    q = xyz[rng.choice(len(xyz), min(24000, len(xyz)), replace=False)]
    lo, hi = np.percentile(q, [5, 95], axis=0)
    q = q[np.all((q >= lo) & (q <= hi), axis=1)]
    hint = -np.mean([np.asarray(i['world_to_camera_R'])[1] for i in images], axis=0)
    hint /= np.linalg.norm(hint)
    tolerance = np.linalg.norm(hi - lo) * .002
    score, normal, offset = 0, hint, 0.
    for _ in range(700):
        a, b, c = q[rng.choice(len(q), 3, replace=False)]
        n = np.cross(b-a, c-a); norm = np.linalg.norm(n)
        if norm < 1e-7: continue
        n /= norm
        if n @ hint < 0: n = -n
        if n @ hint < .80: continue
        d = -n @ a; count = np.count_nonzero(np.abs(q @ n + d) < tolerance)
        if count > score: score, normal, offset = count, n, d
    inliers = q[np.abs(q @ normal + offset) < tolerance]
    if len(inliers) >= 30:
        centroid = np.mean(inliers, axis=0)
        _, _, vt = np.linalg.svd(inliers-centroid, full_matrices=False)
        normal = vt[-1] * (1 if vt[-1] @ hint > 0 else -1)
        offset = -normal @ centroid
    horizontal = q - np.outer(q @ normal, normal)
    _, vectors = np.linalg.eigh(np.cov(horizontal.T))
    y = vectors[:, -1]; y -= (y @ normal)*normal; y /= np.linalg.norm(y)
    if y[np.argmax(np.abs(y))] < 0: y = -y
    x = np.cross(y, normal); rotation = np.stack([x, y, normal])
    industrial = xyz @ rotation.T
    low, high = np.percentile(industrial, [3, 97], axis=0)
    # Dominant horizontal surfaces in workshops can be equipment tops or ceilings.
    # Use the robust full vertical extent, never promote the plane to a confirmed floor.
    origin = np.array([(low[0]+high[0])/2, (low[1]+high[1])/2, low[2]])
    t = np.eye(4); t[:3, :3] = rotation; t[:3, 3] = -origin
    low -= origin; high -= origin
    return dict(transform=t.tolist(), bbox=dict(center=((low+high)/2).tolist(), size=(high-low).tolist()),
                estimation=dict(method='geometry-only constrained plane RANSAC + horizontal PCA', seed=20261125,
                                inliers=int(score), tolerance=float(tolerance), human_confirmation_required=True))


def recommend(box, matrix, images, limit=6):
    raw = transform(corners(box), np.linalg.inv(matrix))
    center = np.mean(raw, axis=0); result = []
    for im in images:
        if im['split'] != 'train': continue
        cam = raw @ np.asarray(im['world_to_camera_R']).T + im['world_to_camera_t']
        # Near-plane crossings cannot produce a reliable bounded reference prompt.
        if np.any(cam[:, 2] <= .01): continue
        uvw = cam @ np.asarray(im['K']).T; uv = uvw[:, :2] / uvw[:, 2:]
        rawlo, rawhi = uv.min(0), uv.max(0)
        low, high = np.maximum(rawlo, 0), np.minimum(rawhi, [im['width'], im['height']])
        size = high-low
        if np.any(size < 12): continue
        fraction = float(np.prod(size)/(im['width']*im['height']))
        if fraction > .85: continue
        visible = float(np.prod(size)/np.prod(np.maximum(rawhi-rawlo, 1)))
        if visible < .95: continue
        bias = np.linalg.norm((low+high)/2 / [im['width'], im['height']] - .5)
        score = visible*np.sqrt(fraction)/(1+bias)
        result.append(dict(image_id=im['image_id'], bbox=[*low.tolist(), *high.tolist()], score=score,
                           projected_fraction=fraction, clipped_fraction=visible,
                           purpose='optional single reference only; no occlusion or semantic guarantee'))
    return sorted(result, key=lambda r:r['score'], reverse=True)[:limit]


def overview(path, xyz, rgb, matrix, scene_box, object_box=None):
    """Actual geometry preview, with the same industrial box corners used by the UI."""
    points = transform(xyz, matrix)
    focus = object_box or scene_box
    in_scene = inside(points, scene_box)
    points, colors = points[in_scene], rgb[in_scene]
    canvas = Image.new('RGB', (1600, 1100), '#101b29'); draw = ImageDraw.Draw(canvas)
    matrices = [np.array([[.707,-.707,0],[.4,.4,.824],[.582,.582,-.566]]), np.array([[1,0,0],[0,1,0],[0,0,1]]),
                np.array([[1,0,0],[0,0,1],[0,-1,0]]), np.array([[0,1,0],[0,0,1],[1,0,0]])]
    labels = ['3D / Gaussian centers', 'TOP / X right, Y forward', 'FRONT / X right, Z up', 'SIDE / Y right, Z up']
    for i, (basis, label) in enumerate(zip(matrices, labels)):
        ox, oy = (i % 2)*800, (i//2)*550
        cp = corners(focus) @ basis.T; mid = np.asarray(focus['center']) @ basis.T
        span = np.maximum(np.ptp(cp[:, :2], axis=0), .1) * (1.6 if object_box else 1.12)
        scale = min(750/span[0], 490/span[1])
        pp = points @ basis.T
        u = np.rint((pp[:, 0]-mid[0])*scale+400).astype(int)
        v = np.rint(285-(pp[:, 1]-mid[1])*scale).astype(int)
        valid = (u>=0)&(u<800)&(v>=35)&(v<550)
        ids = np.flatnonzero(valid); ids = ids[np.argsort(pp[ids,2])]
        tile = np.full((550,800,3), [16,27,41], dtype=np.uint8)
        tile[v[ids],u[ids]] = colors[ids]
        canvas.paste(Image.fromarray(tile), (ox,oy))
        draw = ImageDraw.Draw(canvas)
        for box, color in [(scene_box,'#38bea9')] + ([(object_box,'#ffc65a')] if object_box else []):
            bc = corners(box) @ basis.T
            xy = [(ox+400+(p[0]-mid[0])*scale,oy+285-(p[1]-mid[1])*scale) for p in bc]
            for a in range(8):
                for b in range(a+1,8):
                    if (a^b) in (1,2,4): draw.line([xy[a],xy[b]],fill=color,width=2)
        draw.text((ox+16,oy+12),label,fill='white')
    path.parent.mkdir(parents=True,exist_ok=True); canvas.save(path,quality=94)
