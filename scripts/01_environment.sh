#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export http_proxy=http://127.0.0.1:17891 https_proxy=http://127.0.0.1:17891
export HTTP_PROXY="$http_proxy" HTTPS_PROXY="$https_proxy"
export CUDA_HOME=/usr/local/cuda-11.8
export PATH="$CUDA_HOME/bin:$PATH"
export TORCH_CUDA_ARCH_LIST=8.6 MAX_JOBS=8
export PIP_CACHE_DIR="$ROOT/.cache/pip" HF_HOME="$ROOT/models/huggingface" TORCH_HOME="$ROOT/models/torch"
export CONDA_PKGS_DIRS="$ROOT/.cache/conda"
mkdir -p envs logs models references
if [ ! -x envs/relags/bin/python ]; then
  /home/ubuntu/anaconda3/bin/conda create -y -p "$ROOT/envs/relags" --override-channels -c conda-forge python=3.10.13 pip
fi
export PATH="$ROOT/envs/relags/bin:$PATH"
python -m pip install 'pip<25' 'setuptools<70' wheel ninja 'numpy==1.26.4'
python -m pip install torch==2.2.0 torchvision==0.17.0 torchaudio==2.2.0 --index-url https://download.pytorch.org/whl/cu118
python -m pip install 'plyfile==0.8.1' tqdm einops trimesh kiui pymeshlab open3d openai matplotlib pillow scipy dearpygui omegaconf 'open_clip_torch==2.24.0' transformations 'transformers==4.44.2' yapf pycocotools mediapy lpips scikit-image 'opencv-python==4.7.0.72' h5py colorhash seaborn pyrootutils hydra-core hydra-colorlog hydra-submitit-launcher numba 'torch_geometric==2.3.0' 'pytorch-lightning==2.2.5' 'torchmetrics==1.3.2' rich ipyfilechooser natsort tensorboard 'numpy==1.26.4' 'huggingface_hub==0.25.2'
python -m pip install pyg_lib torch_scatter torch_cluster -f https://data.pyg.org/whl/torch-2.2.0+cu118.html
python -m pip install --no-build-isolation 'git+https://github.com/minghanqin/segment-anything-langsplat.git'
cd "$ROOT/ReLaGS"
python -m pip install --no-build-isolation ./submodules/diff-surfel-rasterization-trace-maxcontrib ./submodules/diff-surfel-rasterization-id ./submodules/simple-knn
python -m pip install --no-build-isolation ./ext/spt/dependencies/FRNN/external/prefix_sum ./ext/spt/dependencies/FRNN
python -m pip install --no-build-isolation 'git+https://github.com/facebookresearch/pytorch3d.git@v0.7.8' 'git+https://github.com/drprojects/point_geometric_features.git'
python scripts/setup_dependencies.py build_ext
python -c "import torch; from gaussian_renderer import render; print(torch.__version__,torch.cuda.is_available())"
python -m pip freeze > "$ROOT/logs/relags.pip.freeze.txt"
date -Iseconds > "$ROOT/logs/environment.completed"
