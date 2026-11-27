from pathlib import Path
import sys, json, hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT.parents[1]
V1 = ROOT.parent / 'saga_relags_v1'
sys.path.insert(0, str(PROJECT))

def read(path): return json.loads(Path(path).read_text())
def write(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
def save(path, image):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    (Image.fromarray(image) if isinstance(image, np.ndarray) else image).save(path)
def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 << 20), b''): h.update(b)
    return h.hexdigest()
def norm(a): return a / np.maximum(np.linalg.norm(a, axis=-1, keepdims=True), 1e-9)
def scaled_camera(im, width=960):
    import copy
    c = copy.deepcopy(im); h = round(im['height'] * width / im['width'])
    K = np.array(c['K'], float); K[0] *= width / im['width']; K[1] *= h / im['height']
    c.update(width=width, height=h, K=K.tolist()); return c
def grid(paths, destination, labels=None, columns=4, tile=(400,330)):
    if not paths: return
    canvas = Image.new('RGB', (columns*tile[0], int(np.ceil(len(paths)/columns))*tile[1]), '#15212d')
    d = ImageDraw.Draw(canvas)
    for i,p in enumerate(paths):
        im = Image.open(p).convert('RGB'); im.thumbnail((tile[0],tile[1]-45))
        x=i%columns*tile[0]; y=i//columns*tile[1]; canvas.paste(im,(x,y))
        d.text((x+5,y+tile[1]-40), labels[i] if labels else Path(p).stem, fill='white')
    save(destination,canvas)
class NativeContext:
    def __init__(self): self.project=PROJECT; self.state=read(ROOT/'inputs/m0_state.json')
def candidate_ids(oid): return np.load(V1/'inputs/geometry/object_candidates'/oid/'gaussian_ids.npy')
def original_ply(): return PROJECT/read(ROOT/'inputs/manifest.json')['ply']
def existing_instances(): return V1/'outputs/A/extractions/iteration_10000'
