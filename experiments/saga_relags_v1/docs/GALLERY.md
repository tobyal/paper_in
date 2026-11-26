# SAGA + ReLaGS：关键实际结果

10个对象尝试中9个可用于设备级查询展示；1个多层料架失败。图中保留实际缺失和伪影。
场景图有33个M0节点，查询目标只包含9个审核可用实例。视觉语义新增边为0。
关系图仅展示部分几何边；没有人工分割真值，不把提示一致性解释为准确率。

图像为服务器结果的原样复制，来源和SHA-256见 [PUBLICATION_MANIFEST.json](../PUBLICATION_MANIFEST.json)。

## 9个审核可用实例

![9个审核可用实例](figures/instances.jpg)

## 全部10次提取（含失败料架）

![全部10次提取（含失败料架）](figures/all_ten_objects.jpg)

## 训练视角投影检查

![训练视角投影检查](figures/training_projections.jpg)

## 实际训练曲线

![实际训练曲线](figures/training_curves.png)

## 8类代表图像

![8类代表图像](figures/category_representatives.jpg)

## SoM视觉关系检查

![SoM视觉关系检查](figures/som_review.jpg)

## 独立实例与几何关系

![独立实例与几何关系](figures/instance_graph.jpg)

## 完整场景中的实例与关系

![完整场景中的实例与关系](figures/scene_graph.jpg)

## 类别及关系查询示例

![类别及关系查询示例](figures/query_examples.jpg)

## 全部10项查询

![全部10项查询](figures/all_queries.jpg)
