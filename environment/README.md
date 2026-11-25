# 实际成功环境与安装边界

`environment_manifest.json` 是成功版本摘要；`relags.pip.freeze.txt` 是当时 Torch 环境的观察快照，包含服务器本地安装路径，不能直接 `pip install -r` 用于新机器。

| 组件 | 实际版本 |
|---|---|
| Python / CUDA | 3.10.13 / 11.8 |
| torch / torchvision | 2.2.0+cu118 / 0.17.0+cu118 |
| NumPy / torch_geometric | 1.26.4 / 2.5.3 |
| OpenCLIP / transformers | 2.24.0 / 4.44.2 |
| pytorch3d / pgeof | 0.7.7 / 0.3.4；精确提交见 manifest |
| Open3D / Matplotlib | 0.20.0 / 3.10.9 |
| OpenSeg 单独环境 | TensorFlow 2.14.1、CUDA 11.8、cuDNN 8.7 |

编译官方 2DGS rasterizer、ReLaGS id/trace-maxcontrib rasterizers、simple-knn、FRNN/prefix_sum 和 SPT Cut Pursuit 依赖。源码补丁保留了实际编译/接口适配；Python 3.8 预编译二进制不随本仓库重新分发，需按目标 Python 重建扩展。

`scripts/01_environment.sh` 与恢复脚本是历史执行记录，曾有失败版本，例如 torch_geometric 2.3.0 与 vendored SPT API 不匹配。以本目录成功版本摘要、报告以及固定上游源码为准。数据、权重及独立环境不在 Git 中。
