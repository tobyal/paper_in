"""Integration check: standalone package projection equals saved full-scene result."""
import sys,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from package_renderer import Renderer
d=json.loads((ROOT/'outputs/D/summary.json').read_text());first=d['queries'][0];folder=ROOT/'outputs/D'/first['query_id'];view=first['evaluation_views'][0];camera=json.loads((ROOT/view['camera_path']).read_text());ids=np.load(folder/'gaussian_indices.npy');renderer=Renderer(ROOT/'world_model');actual=renderer.contribution(camera,ids);expected=np.load(folder/(view['image_id']+'_contribution.npz'))['contribution'];error=float(abs(actual-expected).max());iou=float(((actual>.5)&(expected>.5)).sum()/max(((actual>.5)|(expected>.5)).sum(),1));result=dict(max_absolute_contribution_error=error,binary_mask_iou=iou,independent_package_renderer=True,passed=error<1e-5 and iou>.9999);(ROOT/'outputs/validation/portable_render.json').write_text(json.dumps(result,indent=2));print(result);assert result['passed']
