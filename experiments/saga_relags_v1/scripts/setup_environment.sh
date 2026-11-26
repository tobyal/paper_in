#!/usr/bin/env bash
set -euo pipefail
EXPERIMENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$EXPERIMENT_ROOT/../.." && pwd)"
BASE_PYTHON="${BASE_PYTHON:-$PROJECT_ROOT/envs/relags/bin/python}"
export CUDA_HOME="${CUDA_HOME:-/usr/local/cuda-11.8}"
export PATH="$CUDA_HOME/bin:$PATH"
export TORCH_CUDA_ARCH_LIST="${TORCH_CUDA_ARCH_LIST:-8.6}"
export MAX_JOBS="${MAX_JOBS:-4}"
export PIP_CACHE_DIR="$EXPERIMENT_ROOT/cache/pip"
export TORCH_EXTENSIONS_DIR="$EXPERIMENT_ROOT/cache/torch_extensions"
if [[ ! -x "$EXPERIMENT_ROOT/envs/saga/bin/python" ]]; then
  "$BASE_PYTHON" -m venv --system-site-packages "$EXPERIMENT_ROOT/envs/saga"
fi
PYTHON="$EXPERIMENT_ROOT/envs/saga/bin/python"
for module in diff-gaussian-rasterization diff-gaussian-rasterization-depth diff-gaussian-rasterization_contrastive_f; do
  "$PYTHON" -m pip install --no-deps --no-build-isolation "$EXPERIMENT_ROOT/third_party/SegAnyGAussians/submodules/$module"
done
"$PYTHON" -m pip install --no-deps --no-build-isolation "$EXPERIMENT_ROOT/third_party/SegAnyGAussians/third_party/segment-anything"
"$PYTHON" -c 'import torch,segment_anything,diff_gaussian_rasterization,diff_gaussian_rasterization_depth,diff_gaussian_rasterization_contrastive_f; print(torch.__version__)'
