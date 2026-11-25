"""Fresh promptable SAM. Cache is private to M0, never legacy SAM output."""
import collections
import json
import threading
import time
import uuid
import numpy as np
from PIL import Image
from .settings import SAM_WEIGHTS, IMAGES, ROOT, ASSETS
from .storage import atomic_json, now


class SamService:
    def __init__(self):
        self.lock = threading.Lock(); self.predictor = None; self.cache = collections.OrderedDict(); self.calls = 0; self.encodings = 0

    def predict(self, image, prompts):
        from segment_anything import SamPredictor, sam_model_registry
        import torch
        with self.lock, torch.inference_mode():
            start = time.monotonic()
            if self.predictor is None:
                model = sam_model_registry['vit_h'](checkpoint=str(SAM_WEIGHTS)); model.to('cuda'); model.eval()
                self.predictor = SamPredictor(model)
            torch.cuda.reset_peak_memory_stats()
            p = self.predictor; image_id = image['image_id']; key = image['sha256']; cache_hit = key in self.cache
            if cache_hit:
                features, original_size, input_size = self.cache.pop(key)
                p.features = features.to('cuda'); p.original_size = original_size; p.input_size = input_size; p.is_image_set = True
            else:
                p.set_image(np.asarray(Image.open(IMAGES / image['filename']).convert('RGB')))
                features, original_size, input_size = p.features.cpu(), p.original_size, p.input_size
                self.encodings += 1
            self.cache[key] = (features, original_size, input_size)
            while len(self.cache) > 8: self.cache.popitem(last=False)
            points = prompts.get('points', []); labels = prompts.get('labels', []); bbox = prompts.get('bbox')
            masks, scores, logits = p.predict(point_coords=np.asarray(points, np.float32) if points else None,
                                              point_labels=np.asarray(labels, np.int32) if points else None,
                                              box=np.asarray(bbox, np.float32) if bbox else None, multimask_output=True)
            job_id = 'sam_' + uuid.uuid4().hex; folder = ROOT / '.inference' / job_id; folder.mkdir(parents=True)
            for i, mask in enumerate(masks): Image.fromarray(mask.astype('uint8') * 255).save(folder / f'candidate_{i}.png')
            np.savez_compressed(folder / 'low_resolution_logits.npz', logits=logits)
            self.calls += 1
            record = dict(job_id=job_id, created_at=now(), image_id=image_id, image_sha256=key, prompts=prompts,
                          scores=scores.tolist(), width=image['width'], height=image['height'], model='SAM ViT-H',
                          source='fresh M0 prompt inference', cache_hit=cache_hit, seconds=time.monotonic()-start,
                          gpu_peak_bytes=torch.cuda.max_memory_allocated(), gpu_peak_scope='image encoding and prompt decoding', inference_calls=self.calls, image_encodings=self.encodings)
            atomic_json(folder / 'inference.json', record)
            return record


class SamClient:
    """Keep native CUDA/model failures isolated from HTTP and annotation storage."""
    def __init__(self):
        self.process = None; self.lock = threading.Lock(); self.predictor = None

    def predict(self, image, prompts):
        import subprocess
        import sys
        from .settings import PROJECT
        with self.lock:
            if self.process is None or self.process.poll() is not None:
                (ROOT / '.jobs').mkdir(exist_ok=True)
                self.log = open(ROOT / '.jobs/sam_worker.log', 'a', buffering=1)
                self.process = subprocess.Popen([sys.executable, '-X', 'faulthandler', '-m', 'm0.sam_worker'],
                                                cwd=PROJECT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                                stderr=self.log, text=True, bufsize=1)
            self.process.stdin.write(json.dumps(dict(image=image, prompts=prompts)) + '\n'); self.process.stdin.flush()
            line = self.process.stdout.readline()
            if not line: raise RuntimeError('SAM worker exited; annotation data is safe. See .jobs/sam_worker.log and retry.')
            result = json.loads(line)
            if 'error' in result: raise RuntimeError(result['error'])
            self.predictor = True
            return result['result']

