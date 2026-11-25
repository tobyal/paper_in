#!/usr/bin/env bash
set -euo pipefail
M0_PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$M0_PROJECT_ROOT"
export CUDA_VISIBLE_DEVICES="${M0_GPU:-3}"
export PYTHONUNBUFFERED=1
export PYTHONFAULTHANDLER=1
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1
export M0_PROJECT="$M0_PROJECT_ROOT"
export M0_DATA="${M0_DATA:-$M0_PROJECT_ROOT/industrial_scene_prior_v2}"
mkdir -p logs
if [[ ! -f "$M0_DATA/.assets/initial_scene.json" ]]; then
  envs/m0/bin/python -m m0.prepare > logs/m0_prepare.log 2>&1
fi
if [[ "${1:-}" == "--background" ]]; then
  if [[ -f logs/m0_server.pid ]] && ps -p "$(cat logs/m0_server.pid)" -o args= 2>/dev/null | grep -q 'uvicorn m0.app:app'; then
    echo 'M0 PID is still running; inspect logs/m0_server.pid before starting another instance.'
    exit 1
  fi
  nohup envs/m0/bin/python -m uvicorn m0.app:app --host 127.0.0.1 --port "${M0_PORT:-28760}" --workers 1 > logs/m0_server.log 2>&1 < /dev/null &
  echo $! > logs/m0_server.pid
  echo "M0 started: PID $(cat logs/m0_server.pid), http://127.0.0.1:${M0_PORT:-28760}"
else
  exec envs/m0/bin/python -m uvicorn m0.app:app --host 127.0.0.1 --port "${M0_PORT:-28760}" --workers 1
fi
