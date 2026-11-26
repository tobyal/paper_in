# 仓库归档范围与恢复

本目录提交代码、配置、报告、关键结果图和轻量数值证据。`evidence/`按服务器相对路径归档实际记录；报告中的`outputs/`、`inputs/`、`logs/`和`world_model/`路径指服务器完整实验。

未上传原始图像集、M0数据库、PLY、Gaussian索引/特征张量、模型权重、环境及检查点。Git克隆不能直接复现完整运行，需要按原始实验README准备相应输入。代码使用同仓库已发布的`m0`及`industrial_world_model`通用渲染/几何接口。

## 获取本次固定上游及完整适配

在本实验目录执行（新目录；已有上游修改请先检查，不要覆盖）：

```bash
git clone https://github.com/Jumpat/SegAnyGAussians.git third_party/SegAnyGAussians
git -C third_party/SegAnyGAussians checkout 2d4c5d77c857c956d747e4775d3d72c4ec5dfe16
git -C third_party/SegAnyGAussians -c url.https://github.com/.insteadOf=git@github.com: submodule update --init --recursive
git -C third_party/SegAnyGAussians apply --check ../../docs/patches/saga_complete.patch
git -C third_party/SegAnyGAussians apply ../../docs/patches/saga_complete.patch
bash scripts/setup_environment.sh
```

完整补丁与服务器四个改动文件逐字节对应，包含相机主点/缩放、CPU张量读取、RGB及断点记录适配。`patch_official.py`是实验准备阶段入口；已应用完整补丁时不重复执行。环境脚本需要兼容的基础Python/Torch/PyTorch3D，未包含权重和平台二进制。

SAGA/SAM许可证保存在`licenses/`；其他嵌套组件保留原许可证。上游版权不属于本项目，本仓库不为工业图像另行授予开放许可。

- [运行说明](README.md)
- [完整实验报告](EXPERIMENT_REPORT.md)
- [关键结果图集](docs/GALLERY.md)
- [实际数值及执行记录](evidence/)
