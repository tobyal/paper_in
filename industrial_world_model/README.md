# 工业空间先验与原生 3DGS 世界模型

这是一条独立的 M1—M5 流程。输入是 M0 的对象清单、工业坐标系和粗略框，以及原生 3DGS、原始 RGB、COLMAP 和原有训练/留出划分。M0 只读，旧 ReLaGS Baseline 0/R1 保留。

采用完整原生场景遮挡、SAM box prompt、高斯中心深度一致性加权投票、双分支 CLIP、几何场景图和固定阈值查询。没有 2DGS、MWP、Superpoint、THGS、OpenSeg、GNN 或新模型训练。所有掩膜、特征和关系由本次原始输入重新计算。

## 运行

在服务器项目根目录 `/mnt/sda/ubuntu/lkx/papers/paper_in`，使用已经兼容原生光栅化器的 `envs/m0/bin/python`。统一配置是 `configs/industrial_world_model.json`。GPU 在配置中指定；不要使用其他共享任务占用的卡。

```bash
# 完整流程；已完成且代码、配置、上游执行记录一致的阶段自动复用。
envs/m0/bin/python -u -m industrial_world_model.run --config configs/industrial_world_model.json

# 独立阶段，直接读取已保存上游结果。
envs/m0/bin/python -u -m industrial_world_model.run --stage M2.4

# 从改动模块继续执行受影响的下游；不调用前置模块。
envs/m0/bin/python -u -m industrial_world_model.run --from M4 --to package

# 显式重跑该阶段；已完成旧结果复制到 .history 后保留。
envs/m0/bin/python -u -m industrial_world_model.run --stage M2.4 --force

# 检查实际数据、生成简洁报告。
envs/m0/bin/python -m unittest industrial_world_model.test_contracts -v
envs/m0/bin/python -m industrial_world_model.validate
envs/m0/bin/python -m industrial_world_model.report
```

全部阶段名：`M1 M2.1 M2.2 M2.3 M2.4 M2.5 M2.6 M3.1 M3.2 M3.3 M3.4 M4 M5 package`。

`--stage` 检查所需上游结果已完成；它不会擅自重跑上游。改动上游后请先运行该上游，再用 `--from` 继续。上游的执行记录变化会使相关下游缓存失效。共享几何工具修改会更广泛地失效，避免使用过期坐标结果。首批运行的旧版指纹不与新版指纹混用，升级后第一次调用旧阶段会保留旧结果并重算。

## 输入与环境

- 原生 PLY：`data/gaussian_scene/original_3dgs/point_cloud/iteration_30000/point_cloud.ply`。
- RGB：`data/images/`；COLMAP：`data/colmap/sparse/0/`；split：`data/scene_information/camera_split.json`。
- M0：`industrial_scene_prior_3dgs/.m0.sqlite3` 只读事务快照，源 ID 和正式 review flag 不改。
- 权重：`models/sam/sam_vit_h_4b8939.pth`、`models/openclip_vit_b16/open_clip_pytorch_model.bin`；CLIP ViT-B-16 视觉/文本使用同一 checkpoint，512 维。
- Python 3.10、torch、numpy、scipy、Pillow、plyfile、matplotlib、segment_anything、open_clip_torch，以及已有 `diff_gaussian_rasterization`/`simple_knn` CUDA 扩展。沿用现有 `envs/m0`，不安装第二套冲突扩展。
- `m0/vendor/gaussian_splatting` 是现有固定版本上游代码，许可见其 LICENSE。仅复用 `m0.spatial` 的几何函数及 `m0.native_3dgs` 原生渲染适配器，不调用 Web 或标注写入接口。

本次用户明确授权使用当前完成的 M0；数据库仍保留 draft 标志。`expected_revision` 锁定 29，发现未保存工作区或不同 revision 时不会静默忽略。英文描述缺失时只编码已有英文名称；源描述不改。

## 输出与判定

输出根目录：`outputs/industrial_world_model/baseline_20261126_r29/`。每阶段有 `summary.json`，完整命令、配置、代码、日志、GPU 采样在 `runs/<stage>/<attempt>/`。输入哈希、相机/先验快照和统一参考相机位于 `manifest.json`、`config/`。报告为该输出根目录的 `EXPERIMENT_REPORT.md`。

- M1 的 `gaussian_id` 始终是原 PLY 行号。M0 框内候选允许包含背景，不是最终实例。
- M2.1 为全部训练视角保存几何排名，对每对象前 30 个候选计算完整场景可见性，再按质量和方向差异选择最多 8 个。无有效视角允许为空。
- M2.2 保存全部三个 SAM 候选、低分辨率 logits、选定掩膜、自动拒绝原因和原始分辨率。图像编码仅复用当前实验的缓存，不引用旧实验输出。
- M2.3 保存完整筛选前得分及逐视角证据。仅可见观测进入分母；被遮挡、出视野及无有效观测为未知。得分是加权正向支持比例。
- M2.4 使用统一得分/有效次数/正向次数阈值。竞争对象支持差不足时保留不确定；无去噪，处理前后索引均保存。证据不足的对象保留失败记录，不拿粗框替代。
- M2.5 在完整场景遮挡下比较最终实例投影与输入 SAM；IoU、覆盖率、超出比例仅为内部一致性诊断，另存独立原生渲染及三种虚拟视角对照。
- M2.6 标签 `0` 为未研究背景，`-1` 为候选但未归属，正数对应 `label_lookup.json`。背景高斯保留原外观。
- M3 使用灰色背景的 mask crop，保存所有视觉/文本特征。聚合为质量加权归一化平均；仅视角数量和相似度离散度足够时做 median-MAD 异常过滤，属于 ROFA 思想适配。
- M4 的中心/AABB 来自最终实例。`+X right, +Y forward, +Z up`；`in_front_of` 指 +Y 方向范围分离。near 按 AABB 最小距离，单位是 SfM 相对单位，不是米。
- M5 保留完整候选视觉/文本/联合分数和关系筛选；不降低固定阈值补结果。中文仅使用小型明确词典和规则，任意外观描述建议直接输入英文。相似度不是概率。

## 独立世界模型

`final_world_model/` 内复制完整场景、语义地图、每对象 PLY/原始索引、双分支特征、图、图像/掩膜证据、相机、CLIP 权重及读取代码，所有引用为相对路径，不依赖原 M0 数据库或旧实验目录。

```bash
MODEL=outputs/industrial_world_model/baseline_20261126_r29/final_world_model
envs/m0/bin/python -m industrial_world_model.model "$MODEL" --query '找到料架' --output query.json
```

```python
from industrial_world_model.model import WorldModel
w = WorldModel('outputs/industrial_world_model/baseline_20261126_r29/final_world_model')
r = w.query({'subject': '物料车', 'relation': 'left_of', 'object': '料架'})
for oid in r['matched_ids']:
    print(w.get_object(oid)['name_zh'], w.gaussian_ids(oid).shape)
# 查看两个指定对象的所有出向关系：
edges = w.relationships('subject_object_id', 'anchor_object_id')
# 可选原生 CUDA 渲染，只读取打包场景；空结果不强制高亮。
if r['matched_ids']:
    w.render(r['matched_ids'], image_id='frame_000221', output='highlight.png')
```

查询不会重新跑 SAM 或三维实例提取。CPU 可执行读取和 CLIP 查询；可选原生渲染需要已有兼容 CUDA 扩展。数据、权重和完整实验产物留在服务器。经用户授权，Git 同时收录已展示的 [阶段图集](../docs/industrial_world_model/GALLERY.md)，图像来源及哈希保存在图集目录的 `manifest.json`。
