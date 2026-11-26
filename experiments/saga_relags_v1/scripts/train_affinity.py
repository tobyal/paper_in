"""Enter the official training script with the experiment's recorded settings."""
import os,sys,json,runpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SAGA=ROOT/'third_party/SegAnyGAussians';cfg=json.loads((ROOT/'configs/experiment.json').read_text())
sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(SAGA));os.chdir(SAGA)
sys.argv=['train_contrastive_feature.py','-m',str(ROOT/'outputs/A/saga_model'),'--iteration','30000','--iterations',str(cfg['iterations']),'--num_sampled_rays',str(cfg['num_sampled_rays']),'--smooth_K',str(cfg['smooth_K']),'--feature_lr',str(cfg['feature_lr']),'--resolution',str(cfg['training_resolution']),'--data_device','cpu','--allow_principle_point_shift']
runpy.run_path(str(SAGA/'train_contrastive_feature.py'),run_name='__main__')
