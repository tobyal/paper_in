#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$ROOT/ReLaGS"
python -m pip install --no-build-isolation ./submodules/diff-surfel-rasterization-trace-maxcontrib ./submodules/diff-surfel-rasterization-id
python -m pip install --no-build-isolation ./ext/spt/dependencies/FRNN/external/prefix_sum
python -m pip install --no-build-isolation ./ext/spt/dependencies/FRNN
python -m pip install --no-build-isolation 'git+https://github.com/facebookresearch/pytorch3d.git@v0.7.8' 'git+https://github.com/drprojects/point_geometric_features.git'
python scripts/setup_dependencies.py build_ext
python -c "import torch; from gaussian_renderer import render; print(torch.__version__,torch.cuda.is_available())"
python -m pip freeze > "$ROOT/logs/relags.pip.freeze.txt"
date -Iseconds > "$ROOT/logs/environment.completed"
