# SAGA + ReLaGS 工业世界模型 v2

> Git版本仅含代码、报告、关键图和轻量证据；完整模型与中间数组留在服务器。参见 [归档范围](PUBLICATION.md)。

服务器：`/mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v2`。

33个工业设备全部处理：20可用、10局部可用、3待改进。8类语义、33节点/2020几何边、先设备后实例的查询逻辑已完成。复用v1 iteration_10000，无重新训练。M0 r29、原生3DGS和旧工程保持只读。

先看 [结果图集](docs/GALLERY.md)、[实验报告](EXPERIMENT_REPORT.md) 和 [修改记录](MODIFICATION_REPORT.md)。这些是Codex视觉审核及工程验证结果，不是独立人工真值。

## 直接查询

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v2
PY="$PWD/../saga_relags_v1/envs/saga/bin/python"
PYTHONDONTWRITEBYTECODE=1 "$PY" world_model/query.py --model "$PWD/world_model" \
  --text '距离装配夹具台 01最近的蓝色箱组' --output "$PWD/outputs/manual_query"
```

返回正确设备ID、M0位置、质量状态、可用性、关系证据和可用实例Gaussian IDs。没有可靠精细实例仍返回设备，不替换次近设备。类别与几何查询只需Python/NumPy；英文描述回退还需torch/open_clip及已有CLIP权重。中文仅支持已知名称/别名及限定关系表达。

## 输入与大型只读依赖

`inputs/provenance.json`记录7个关键哈希和版本；`inputs/manifest.json`记录原数据路径。复用v1环境、官方SAGA源码/检查点、M0候选/坐标、74训练视角记录及原始RGB/混合观测。亲和训练未追加样本，44留出只在A冻结后做展示。

`world_model/`复制类别、图、全部33索引和独立query.py。CLIP权重/原生场景用只读符号链接，实例PLY相对链接到本v2输出。纯类别/几何查询可单独搬移包；描述查询需同时携带CLIP权重；可视化仍调用工程已有原生Renderer。此包不宣称包含可搬移CUDA环境。若搬移全实验，应复制所需大型引用并更新链接，而不是改动旧工程。

## 实际运行顺序与复查

本次结果已冻结，不要在当前 `initial` / `refined` 标签上重做提示或调参。新的研究使用新实验目录/标签；只读检查及查询可以直接复用。源代码的实际命令与当次快照全部保存在logs。

1. `scripts/initialize.py`：一次性输入哈希、ID及旧文件保护快照。
2. `src/prepare_references.py`：24对象新SAM参考；9个原可用对象保留原提示。
3. `src/extract_instances.py --tag initial`，`src/inspect_instances.py --tag initial`：33初始提取与三向检查。
4. `scripts/refine_prompts.py`：只对料架02/04做有记录修正。
5. `src/extract_instances.py --tag refined --references outputs/A/refinement_prompts/records.json`；对应inspection。有限比较命令见logs/A_scale_lower、A_scale_upper、A_bounded_comparison。
6. `scripts/freeze_instances.py`：质量记录、9对象复用比较及最终哈希冻结。
7. `src/build_world_model.py`：B原型比较及C完整图验证/打包。
8. `src/test_queries.py`：真实回归与明确标记的合成边界。
9. `src/final_visualizations.py`：全33图集、彩色实例图、完整场景关系和18查询展示。
10. `scripts/validate_final.py`：原文件保护、原始属性、无重复ID、冻结及实际查询接口核验。

运行器例子：

```bash
PYTHONDONTWRITEBYTECODE=1 "$PY" scripts/run_command.py --stage query_recheck --gpu 0 -- "$PY" src/test_queries.py
```

## 数据入口

|内容|路径|
|---|---|
|33最终ID/PLY/亲和度/提示|`outputs/A/extractions/refined/objects/`|
|初始失败及保留尝试|`outputs/A/extractions/initial/`、`scale_lower/`、`scale_upper/`|
|新SAM原始掩膜/相机/点/日志|`outputs/A/reference_prompts/`、`refinement_prompts/`|
|有限参数比较|`outputs/A/bounded_comparison/`|
|最终质量与可用性|`outputs/A/final_summary.json`、`configs/quality_review.json`|
|B真实裁剪及两套特征|`outputs/B/`|
|33节点、2020边及实例彩色PLY|`outputs/C/`、`outputs/C/visualizations/`|
|查询结果、完整贡献、相机与RGB|`outputs/D/query_*/`|
|64查询测试及保护检查|`outputs/D/tests.json`、`outputs/validation/`|
|查阅版图集|`docs/figures/`、`docs/GALLERY.md`|

场景使用SfM相对单位。彩色实例PLY仅为展示覆盖颜色，原始实例PLY所有属性严格未改。3个待改进对象只在常规查询展示中关闭精细输出，其尝试结果始终保留。
