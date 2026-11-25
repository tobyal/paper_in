"""Build the pinned native CUDA renderer in M0 only, from a local source checkout."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
from .settings import PROJECT

PIN='59f5f77e3ddbac3ed9db93ec2cfe99ed6c5d121d'
parser=argparse.ArgumentParser();parser.add_argument('--source',required=True,help='Local diff-gaussian-rasterization checkout')
args=parser.parse_args();source=Path(args.source).resolve()
assert Path(sys.prefix).resolve()==(PROJECT/'envs/m0').resolve(), 'Run with envs/m0/bin/python'
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=source,text=True).strip()==PIN, 'Unexpected native rasterizer version'
assert not subprocess.check_output(['git','diff','HEAD','--'],cwd=source), 'Source has tracked modifications'
target=PROJECT/'envs/m0_build/diff-gaussian-rasterization'
if not target.exists():
    shutil.copytree(source,target,ignore=shutil.ignore_patterns('.git','build','*.so','*.egg-info','__pycache__'))
env=dict(os.environ);env.setdefault('CUDA_HOME','/usr/local/cuda-11.8');env.setdefault('TORCH_CUDA_ARCH_LIST','8.6');env.setdefault('MAX_JOBS','2')
subprocess.run([sys.executable,'-m','pip','install','--no-build-isolation','--no-deps',str(target)],env=env,check=True)
