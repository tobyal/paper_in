# 工业世界模型数据包

此目录可以整体复制到其他位置。元数据和模型路径均相对于本目录；运行环境需另行准备。

- `manifest.json`：版本、实例数量、坐标约定。
- `scene/scene.ply`：完整原生3DGS，原始Gaussian行序不变。
- `objects/<object_id>/`：Gaussian索引和原生对象PLY；可查询状态以`scene_graph.json`的`segmentation_available`为准。
- `categories.json`、`category_features.npz`：8类共享语义；`models/`为既有CLIP权重。
- `scene_graph.json`：全部M0节点、几何或视觉来源的关系及证据。
- `cameras.json`、`m0_scene.json`：COLMAP相机和工业坐标变换。`evaluation_rgb/`只包含演示中实际使用的部分原始图像。
- `quality_review.json`：实例用途审核及仍存在的问题。
- `query.py`、`render.py`、`vendor/`：查询与原生渲染代码。

## 查询

将下面路径替换为此数据包的实际位置。已知别名和关系查询需要Python与NumPy；CLIP自由表达回退还需要Torch/OpenCLIP。

```bash
python /path/to/world_model/query.py --model /path/to/world_model \
  --text '距离装配夹具台 01最近的物料车' --output /path/to/query_result
```

结果保存原始文本、类别候选、参照对象、关系证据、匹配ID和`gaussian_indices.npy`。参照对象允许没有精确分割；目标只返回审核可用实例。`nearest_to`在全部M0同类别设备间比较，不限定在已分割子集中。

## 渲染

需要CUDA11.8兼容Torch及SAGA官方RGB、深度、特征扩展、simple-knn、PyTorch3D等现有依赖。实验根目录提供环境脚本和完整版本快照。

```bash
CUDA_VISIBLE_DEVICES=0 python /path/to/world_model/render.py \
  --model /path/to/world_model --camera frame_000001 \
  --indices /path/to/query_result/gaussian_indices.npy --output /path/to/query_result/render
```

按`cameras.json`选择目标可见相机。输出完整场景RGB、目标贡献图与贡献大于0.5的投影掩膜。所有原生高斯参与遮挡合成。

几何使用SfM相对单位；左右/前后指工业坐标，未必与屏幕方向一致。未获得可靠的视觉支撑/包含关系；当前关系筛选主要依赖几何。实例存在细结构缺失和原3DGS伪影，不代表真值标注。
