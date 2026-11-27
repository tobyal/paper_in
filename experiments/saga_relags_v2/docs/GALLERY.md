# 全33设备与关键结果图集

所有图来自实际RGB或原生3DGS，不使用生成图。质量为Codex视觉检查；M0框不是真值。20 usable、10 partial_usable、3 needs_improvement均列出。

[全部33紧凑总览](figures/all_33_compact.jpg) · [独立实例关系图](figures/instance_graph_compact.jpg) · [工业俯视图](figures/industrial_top_plan.png) · [查询示例](figures/query_examples.jpg)

分类图每行依次：训练RGB、同相机完整原生场景、M0粗候选、SAGA斜视、侧视、顶视、真实三维投影。行首含设备ID和两个独立质量状态。图中O01—O33只用于索引，不修改原设备编号。

|类别|数量|完整对照图|
|---|---:|---|
|物料车|6|[查看](figures/category_01.jpg)|
|装配夹具台|3|[查看](figures/category_02.jpg)|
|带黑色工件的夹具台|5|[查看](figures/category_03.jpg)|
|多层料架|9|[查看](figures/category_04.jpg)|
|蓝色箱组|3|[查看](figures/category_05.jpg)|
|立式移动冷风机|3|[查看](figures/category_06.jpg)|
|工作台|2|[查看](figures/category_07.jpg)|
|分隔式料架|2|[查看](figures/category_08.jpg)|

## 场景、关系与v1对照

- [完整原生3DGS场景关系图1](figures/full_scene_graph_01.jpg)、[图2](figures/full_scene_graph_02.jpg)。彩色为实际高斯成员，未删除邻近物体。
- [独立实例斜视](figures/instance_graph_oblique.jpg)、[顶视](figures/instance_graph_top.jpg)。3个不可用对象只标M0位置。
- [v1/v2全部10个原对象对比](figures/v1_v2_comparison.jpg)。9台精确复用，料架04保留修正前后。
- [全部18查询](figures/query_gallery.jpg)、[4个关键查询](figures/query_examples.jpg)。红色是真实三维实例投影，黄色框为M0位置。

## 服务器中间数据入口

以下大型中间结果保留在服务器实验目录，查阅图已复制到本地docs/figures。

- `outputs/A/extractions/initial/`：首轮33对象，含空结果。
- `outputs/A/extractions/refined/objects/<object_id>/`：最终原始ID、native PLY、亲和度、提示特征、相机及全部三向图。
- `outputs/A/reference_prompts/`：新SAM候选、掩膜、可见贡献、参考图及像素点；`refinement_prompts/`为已记录修正。
- `outputs/A/bounded_comparison/`：3对象阈值、料架04门控比较；未采用方案也保留。
- `outputs/B/crop_comparison/`：原裁剪、实例贡献与软背景；`validation.json`为实际query接口结果。
- `outputs/C/visualizations/colored_instance_map.ply`：30可用/局部原始高斯的彩色场景，`colored_map_original_gaussian_ids.npy`保留行号对应。
- `outputs/D/query_*/`：18查询原文/result.json、2相机RGB、投影、贡献数组及冻结索引。空/不可用结果也保留。
- `outputs/D/future_evaluation_protocol.json`：后续固定4留出视角/33设备标注入口，尚无真值。
