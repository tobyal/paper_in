# M0 v2 数据格式

schema_version 为 m0-2.0。只包含粗略空间和文本先验；所有大小是 SfM 相对单位。

~~~text
industrial_scene_prior_v2/
  scene/scene_bbox.json
  scene/coordinate_system.json
  scene/coordinate_transform.npy
  scene/scene_gaussian_indices.npy
  scene/scene_overview.jpg
  objects/object_catalog.json
  objects/<permanent_object_id>/coarse_bbox.json
  objects/<permanent_object_id>/description.json
  objects/<permanent_object_id>/bbox_preview.jpg
  objects/<permanent_object_id>/optional_reference/  # 仅有确认参考时
      reference.json
      prompts.json
      mask.png
      overlay.jpg
      edits.json
      original/candidate_0.png ... candidate_2.png
  source_images.json
  manifest.json
  M0_REPORT.md
~~~

工作目录另外保存 .m0.sqlite3、.assets、.artifacts、.inference、.jobs、operation_history、versions；这些不是后续建模输入。当前标准目录由 SQLite 修订恢复；软删除对象不在当前目录和 catalog 中，原记录仍在修订/.artifacts 中。

## 坐标与框

scene_bbox 和 coarse_bbox 使用 center:[x,y,z]、size:[width,depth,height]。设备框为工业坐标轴对齐 AABB，不是最终 OBB 或实例边界。scene_bbox 通过 coordinate_transform 在原始 COLMAP 中形成有向空间范围。二者带 coordinate_frame=industrial、coordinate_version、units=sfm_relative 和 review_status。

矩阵为列齐次向量约定：p_industrial=T@p_colmap；旋转正交且 det=+1。+X 右、+Y 前、+Z 上。coordinate_system 同时记录 T、逆矩阵及人工方向标志。只有确认底面后才写 floor_plane_colmap，否则为 null；平面由 z_industrial=box_bottom 得出。坐标原点为初始化参考，不强制用户单独选点。

修改场景几何产生新坐标版本；旧对象原始世界角点被变换到新坐标，并用包围 AABB 保留其覆盖范围，置为 draft。旋转后可能扩大；这不是精确实例重建。

scene_gaussian_indices 是 int64、从零开始的原始 MWP PLY vertex 行号，按原顺序升序保存。判定仅为高斯中心在场景框内；manifest 绑定原始路径、SHA-256、vertex 元素与索引顺序。**不提供对象高斯索引**。显示点按所有有限原始中心生成，内部 display_indices 保留显示行与原始行映射。

## 对象与参考

对象 ID 为 obj_ 加随机 UUID 后缀，创建后永久不变。catalog 为当前有效对象的权威清单。同名设备允许独立 ID。granularity 只支持 equipment 或 container_group。

description.json 包含 object_id、name_zh、name_en、description_zh、description_en、status、source、reviewer。草稿可为空；确认时要求基础名称和双语描述，拒绝明显的对象间空间关系句式。不会生成 CLIP 或其他语义特征。

一个对象最多关联一个当前 reference，可替换或移除；旧结果保留在修订和不可覆盖 artifacts。只允许原始 train 图像。PNG 与去畸变原图宽高严格相同，0/255 二值且非空；record 绑定图像哈希、SAM 任务、三个原候选、选中候选、提示、最终掩膜哈希和审核状态。edits.json 保存画笔/多边形、撤销重做及时间记录。mask.png 是人工确认后的参考，不反投影融合到对象高斯。

## 冻结与来源

manifest 引用已有原图、相机、划分、base/MWP 几何、SAM 权重的项目相对路径与 SHA-256，source_images.json 给出图像/相机对应和原始训练/留出划分。原始资源不重复复制。reference 只允许训练图，留出图不会作为模型输入上传或导出掩膜。

冻结版本目录是独立完整数据投影，增加 FROZEN.json 文件哈希表、annotation_history.json。下载 ZIP 再验证冻结内容。新的编辑不会覆盖旧版本。无需 SAM、二维锚框、区域、关系、评价查询或旧七步确认。
