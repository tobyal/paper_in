import numpy as np


def fit_reference(points, origin, heading, up_hint, units='sfm_relative'):
    p = np.asarray(points, dtype=float); o = np.asarray(origin, dtype=float); h = np.asarray(heading, dtype=float); hint = np.asarray(up_hint, dtype=float)
    if p.ndim != 2 or p.shape[1] != 3 or len(p) < 3 or h.shape != (2, 3) or o.shape != (3,) or hint.shape != (3,): raise ValueError('至少选择三个地面点、一个原点和两个通道方向点。')
    if not all(np.isfinite(a).all() for a in (p, o, h, hint)): raise ValueError('坐标必须为有限数值。')
    center = p.mean(0); _, singular, vt = np.linalg.svd(p - center)
    if singular[1] < 1e-7: raise ValueError('地面参考点共线，无法拟合平面。')
    z = vt[-1]
    if np.linalg.norm(hint) < 1e-7 or abs(z @ hint / np.linalg.norm(hint)) < .05: raise ValueError('竖直方向提示与法线不明确，请选择正确方向。')
    if z @ hint < 0: z = -z
    y = h[1] - h[0]; y -= (y @ z) * z
    if np.linalg.norm(y) < 1e-7: raise ValueError('通道方向长度为零或垂直于地面。')
    y /= np.linalg.norm(y); x = np.cross(y, z); x /= np.linalg.norm(x)
    o = o - ((o - center) @ z) * z
    rotation = np.stack([x, y, z]); transform = np.eye(4); transform[:3, :3] = rotation; transform[:3, 3] = -rotation @ o
    if units != 'sfm_relative': raise ValueError('本场景未标定真实尺度，只允许 SfM 相对单位。')
    return dict(coordinate_frame='industrial', parent_frame='colmap_raw', units=units, transform=transform.tolist(),
                origin=o.tolist(), x_right=x.tolist(), y_forward=y.tolist(), z_up=z.tolist(),
                floor_plane=[*z.tolist(), float(-z @ center)], floor_points=p.tolist(), heading_points=h.tolist(), up_hint=hint.tolist(),
                fit_rmse=float(np.sqrt(np.mean(((p - center) @ z)**2))), review_status='draft',
                convention='column homogeneous points: industrial = T @ colmap; +X right, +Y forward, +Z up')


def project(xyz, image):
    camera = np.asarray(xyz) @ np.asarray(image['world_to_camera_R']).T + np.asarray(image['world_to_camera_t'])
    pixels = camera @ np.asarray(image['K']).T
    valid = camera[:, 2] > 1e-5
    uv = pixels[:, :2] / np.maximum(pixels[:, 2:], 1e-5)
    valid &= (uv[:, 0] >= 0) & (uv[:, 0] < image['width']) & (uv[:, 1] >= 0) & (uv[:, 1] < image['height'])
    return uv, valid

