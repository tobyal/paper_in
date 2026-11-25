#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT CUDA_HOME=/usr/local/cuda-11.8
export PATH="$ROOT/envs/relags/bin:$CUDA_HOME/bin:$PATH"
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-3}"
export TORCH_CUDA_ARCH_LIST=8.6 MAX_JOBS=8 OMP_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 MKL_NUM_THREADS=8
export GLM_PATH="$ROOT/ReLaGS/submodules/diff-surfel-rasterization-id/third_party/glm"
export HF_HOME="$ROOT/models/huggingface" TORCH_HOME="$ROOT/models/torch" PIP_CACHE_DIR="$ROOT/.cache/pip"
export http_proxy=http://127.0.0.1:17891 https_proxy=http://127.0.0.1:17891
export PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_DISABLE_TELEMETRY=1
