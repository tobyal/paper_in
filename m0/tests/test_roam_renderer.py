"""Read-only RGB renderer check at two original training poses; no annotations created."""
import io,json,math,time,urllib.request
from pathlib import Path
import numpy as np
from PIL import Image
URL='http://127.0.0.1:28760/api'
def get(path):return json.load(urllib.request.urlopen(URL+path))
def post(path,b):
    return urllib.request.urlopen(urllib.request.Request(URL+path,data=json.dumps(b).encode(),headers={'Content-Type':'application/json','X-M0-Client':'1'}),timeout=65)
s=get('/state');images={i['image_id']:i for i in get('/images')};oid=next(oid for oid,o in s['objects'].items() if not o.get('deleted'))
recommendations=json.load(post('/objects/'+oid+'/recommend',{}))['recommendations'];assert len(recommendations)>=2
out=Path(__file__).resolve().parents[2]/'logs/m0_native3dgs_renderer';out.mkdir(exist_ok=True);results=[]
for item in recommendations[:2]:
    im=images[item['image_id']];r=np.asarray(im['world_to_camera_R']);t=np.asarray(im['world_to_camera_t']);k=im['K']
    raw=np.eye(4);raw[:3,:3]=r.T@np.diag([1,-1,-1]);raw[:3,3]=-r.T@t
    world=np.asarray(s['scene']['transform'])@raw
    # Test the inverse axis conversion independently of the image content.
    back=np.linalg.inv(s['scene']['transform'])@world;rc=np.diag([1,-1,-1])@back[:3,:3].T
    np.testing.assert_allclose(rc,r,atol=1e-7);np.testing.assert_allclose(-rc@back[:3,3],t,atol=1e-7)
    b=dict(camera_world=world.tolist(),width=1250,height=704,fov=math.degrees(2*math.atan(im['height']/(2*k[1][1]))),coordinate_version=s['scene']['coordinate_version'],show_outside=False)
    start=time.monotonic();response=post('/roam/render',b);data=response.read();elapsed=time.monotonic()-start
    assert response.headers['X-M0-Renderer']=='official-3dgs';assert int(response.headers['X-M0-Gaussians'])==s['scene']['gaussian_count']
    pixels=np.asarray(Image.open(io.BytesIO(data)));assert pixels.shape==(704,1250,3);fraction=float(np.mean(np.max(pixels,2)>15));assert fraction>.03
    (out/(im['image_id']+'.jpg')).write_bytes(data)
    results.append(dict(image_id=im['image_id'],seconds=elapsed,render_ms=response.headers['X-M0-Render-Ms'],gpu_mb=response.headers['X-M0-GPU-MB'],nonblack_fraction=fraction,gaussians=response.headers['X-M0-Gaussians']))
assert get('/state')==s
report=dict(status='passed',read_only=True,pose_conversion='Three right/up/back to COLMAP right/down/forward roundtrip verified',views=results)
(out/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
