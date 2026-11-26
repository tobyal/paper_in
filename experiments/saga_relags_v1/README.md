# SAGA + ReLaGS 工业世界模型

服务器目录：`/mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v1`。

本方案使用已有原生3DGS和M0 r29：A运行SAGA v2共享亲和特征学习与提示式三维分割；B构建8类CLIP共享语义；C结合工业几何与本地SoM视觉关系检查；D查询已存类别、关系和高斯实例。旧M0、M1—M5、M2.1和ReLaGS结果保持只读。

实际完成状态、对象质量和限制见 `EXPERIMENT_REPORT.md`。方法适配见 `docs/IMPLEMENTATION_NOTES.md`，上游原文件和补丁见 `docs/upstream_original/`、`docs/patches/`。

## GitHub阅读入口

[关键结果图集](docs/GALLERY.md) · [归档范围与恢复](PUBLICATION.md) · [轻量结果证据](evidence/)

仓库只包含精选结果；下文的完整数据和检查点路径指服务器实验目录。

## 环境

- Python 3.10.13；Torch 2.2.0+cu118；CUDA toolkit 11.8；A6000 sm86；PyTorch3D 0.7.7。
- `envs/saga`为独立venv，复用只读`../../envs/relags`中的基础Python库。官方SAM和SAGA三种CUDA扩展只安装在新venv中。它不是完全可搬移的打包环境。
- 版本快照：`inputs/environment_final.txt`、`inputs/upstream_submodules.txt`。
- 同服务器恢复环境：`bash scripts/setup_environment.sh`。可通过`BASE_PYTHON`指定已有兼容Torch/PyTorch3D环境。完整pip快照包含继承环境的其他历史库，不表示本方案使用了那些算法。
- SAGA固定提交：`2d4c5d77c857c956d747e4775d3d72c4ec5dfe16`。需保留`third_party/SegAnyGAussians`及其子模块。远程下载使用已存在的`http://127.0.0.1:17891`代理。
- C仅访问本机Ollama `http://127.0.0.1:11434` 的已有`qwen3.5:9b`，工业图像不上传外部服务。

## 已冻结输入

`inputs/manifest.json`记录原始路径及兼容性；`inputs/m0_state.json`冻结33个对象、8类及工业坐标。`inputs/training_cameras.json`包含57个真实训练视角、17个已有完整场景虚拟视角。44个原始留出视角不用于亲和训练、提示或调参。

`inputs/saga_dataset/`保存复制的RGB、逐相机COLMAP文本参数、新SAM掩膜及尺度。`inputs/geometry/`保存原始Gaussian行号、坐标、精确K=16邻域和只用于约束的M0候选集合。原3DGS不重新训练。

## 模块运行

以下命令均从本目录执行。每次运行通过`run_command.py`记录命令、日志、GPU采样、退出状态和耗时；较新的运行另存代码快照。参数修改应使用新的实验目录或提取标签，保留已有结果。

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v1
PY="$PWD/envs/saga/bin/python"

# A：输入准备已经完成。下列训练复用新生成的监督。
"$PY" scripts/run_command.py --stage A_affinity_training -- "$PY" -u scripts/train_affinity.py

# 从记录的完整训练状态恢复，不重跑已完成迭代。
SAGA_RESUME_CHECKPOINT="$PWD/outputs/A/saga_model/point_cloud/iteration_5000/training_state.pt" \
  "$PY" scripts/run_command.py --stage A_affinity_resume -- "$PY" -u scripts/train_affinity.py

# 指定训练检查点提取对象；--tag用于保存独立提示/阈值尝试。
"$PY" scripts/run_command.py --stage A_extract -- "$PY" -u src/extract_instances.py --iteration 10000
"$PY" scripts/run_command.py --stage A_render -- "$PY" -u src/render_instances.py --iteration 10000

# B、C不依赖A完成。
"$PY" scripts/run_command.py --stage B_semantics -- "$PY" -u src/build_semantics.py
"$PY" scripts/run_command.py --stage C_graph -- "$PY" -u src/build_graph.py

# 人工/视觉审核结果保存为对应提取目录的quality_review.json后打包。
"$PY" scripts/build_world_model.py --iteration 10000
"$PY" scripts/run_command.py --stage C_visualization -- "$PY" -u src/visualize_graph.py
"$PY" scripts/run_command.py --stage C_instance_map -- "$PY" -u src/visualize_instance_graph.py
"$PY" scripts/run_command.py --stage D_queries -- "$PY" -u src/query_demonstrations.py
"$PY" scripts/run_command.py --stage validation -- "$PY" -u scripts/validate_results.py
"$PY" scripts/run_command.py --stage portable_render -- "$PY" -u scripts/check_portable_render.py
```

准备阶段的真实命令保存在`logs/`。新数据重建顺序：`audit_inputs.py` → `prepare_dataset.py` → `patch_official.py` → 官方`extract_segment_everything_masks.py` → `prepare_prompts.py` → `finalize_prompts.py` → `mask_scales.py`。已有数据和检查点可以直接复用。`finalize_prompts.py`的具体拒绝项以及`configs/extra_prompt_points.json`中的四个点击是本场景的已记录辅助先验，不是通用训练标签。

## 查看结果

| 内容 | 路径 |
|---|---|
| A：独立对象、原始索引、相似度和三向渲染 | `outputs/A/extractions/iteration_10000/` |
| A：自动监督、辅助提示及失败尝试 | `inputs/saga_dataset/`、`outputs/A/reference_prompts/`、`outputs/A/history/` |
| A：检查点、门控与训练曲线数据 | `outputs/A/saga_model/` |
| B：类别语义与44张代表裁剪 | `outputs/B/` |
| C：全图、逐边证据、SoM提示与原始回复 | `outputs/C/` |
| C：真实彩色高斯图与关系连线 | `outputs/C/visualizations/` |
| D：自然语言输入、候选缩减、Gaussian IDs、留出RGB掩膜 | `outputs/D/` |
| 原工程保护及独立运行检查 | `outputs/validation/` |
| 可独立读取的世界模型数据包 | `world_model/` |

## 独立查询与渲染

`world_model`内的数据和代码使用相对路径，不依赖原工程的绝对数据路径。查询只读取已审核实例；其余M0节点仍可作为关系参照，未完成分割的对象会在查询结果中明确列出。支持中英文已知类别别名，以及`某对象左侧的物料车`、`距离某对象最近的物料车`等受限表达；不是任意语言推理系统。

```bash
"$PY" world_model/query.py --model "$PWD/world_model" \
  --text '物料车' --output "$PWD/outputs/manual_query"

# 指定cameras.json中的相机，使用完整场景遮挡生成投影。
CUDA_VISIBLE_DEVICES=0 "$PY" world_model/render.py --model "$PWD/world_model" \
  --camera frame_000001 --indices "$PWD/outputs/manual_query/gaussian_indices.npy" \
  --output "$PWD/outputs/manual_query/render"
```

纯别名/关系查询仅需要Python和NumPy；CLIP自由表达回退需要Torch/OpenCLIP；渲染需要CUDA扩展。包中含完整原生PLY、独立对象PLY、语义权重和SAGA原生RGB渲染源码。`cameras.json`保留原始轨迹，部分验证RGB另存`evaluation_rgb/`。

提示掩膜一致性只用于检查，不是真值准确率。工业坐标使用SfM相对单位。世界模型复用了已有3DGS，留出约束指本次亲和训练、提示及参数选择，不声称基础3DGS进行了新的独立重建评测。
