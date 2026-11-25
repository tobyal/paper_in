# M0 v2 数据格式

schema_version 为 m0-2.0。只包含粗略空间和文本先验；所有大小是 SfM 相对单位。

~~~text
industrial_scene_prior_3dgs/
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

scene_bbox 使用工业坐标中的 AABB：center:[x,y,z]、size:[width,depth,height]。从 Web v2.1 起，设备 coarse_bbox 为可旋转粗 OBB，增加 quaternion:[x,y,z,w]、box_type:OBB 和 rotation_convention。四元数为单位旋转，作用方向为设备框局部坐标到工业坐标；size 是局部三轴全长，绝非世界 AABB 尺寸。旧记录未含 quaternion 时按 [0,0,0,1] 读取；已有冻结文件保持原样。新 manifest 标记 object_bbox_schema=obb-xyzw-v1，整体 schema_version 仍为 m0-2.0。二者带 coordinate_frame=industrial、coordinate_version、units=sfm_relative 和 review_status。粗 OBB 不是精确设备实例边界。

角点：p_industrial = center + R(quaternion) @ (sign * size / 2)。包含判定：abs(R.T @ (p_industrial-center)) <= size/2。可复用 m0.spatial.corners / inside / box_rotation，不能只检查 center ± size/2。

矩阵为列齐次向量约定：p_industrial=T@p_colmap；旋转正交且 det=+1。+X 右、+Y 前、+Z 上。coordinate_system 同时记录 T、逆矩阵及人工方向标志。只有确认底面后才写 floor_plane_colmap，否则为 null；平面由 z_industrial=box_bottom 得出。坐标原点为初始化参考，不强制用户单独选点。

修改场景几何产生新坐标版本；旧对象中心和姿态通过 T_new @ inverse(T_old) 变换，局部尺寸保持不变，原始世界角点精确保留，置为 draft。场景本身继续使用工业坐标 AABB。

scene_gaussian_indices 是 int64、从零开始的原生 3DGS PLY vertex 行号，按原顺序升序保存。判定仅为高斯中心在场景框内；manifest 绑定原始路径、SHA-256、vertex 元素与索引顺序。**不提供对象高斯索引**。显示点按所有有限原始中心生成，内部 display_indices 保留显示行与原始行映射。

## 对象与参考

对象 ID 为 obj_ 加随机 UUID 后缀，提交后永久不变。浏览器工作草稿中的 draft_ 临时 ID 在 /api/objects/batch 一次提交时映射成永久 ID。请求包含 revision、reviewer、objects；响应包含 state、id_mapping、saved。全批先验证，再提交一个修订；非法对象或过期 revision 不产生部分提交。catalog 为当前有效对象的权威清单。同名设备允许独立 ID。granularity 只支持 equipment 或 container_group。

description.json 包含 object_id、name_zh、name_en、description_zh、description_en、status、source、reviewer。草稿可为空；确认时要求基础名称和双语描述，拒绝明显的对象间空间关系句式。不会生成 CLIP 或其他语义特征。

一个对象最多关联一个当前 reference，可替换或移除；旧结果保留在修订和不可覆盖 artifacts。只允许原始 train 图像。PNG 与去畸变原图宽高严格相同，0/255 二值且非空；record 绑定图像哈希、SAM 任务、三个原候选、选中候选、提示、最终掩膜哈希和审核状态。edits.json 保存画笔/多边形、撤销重做及时间记录。mask.png 是人工确认后的参考，不反投影融合到对象高斯。

## 冻结与来源

manifest 引用已有原图、相机、划分、未编辑 native 3DGS 几何、SAM 权重的项目相对路径与 SHA-256，source_images.json 给出图像/相机对应和原始训练/留出划分。原始资源不重复复制。reference 只允许训练图，留出图不会作为模型输入上传或导出掩膜。

冻结版本目录是独立完整数据投影，增加 FROZEN.json 文件哈希表、annotation_history.json。下载 ZIP 再验证冻结内容。新的编辑不会覆盖旧版本。无需 SAM、二维锚框、区域、关系、评价查询或旧七步确认。

## v2.2 几何来源绑定

manifest.geometry_source 和 scene_indices_binding 指向 original_3dgs/point_cloud/iteration_30000/point_cloud.ply，representation=native_3dgs、scale_dimensions=3。renderer=official-3dgs。dataset_id 与旧 2DGS 分开；migration 记录旧数据集及修订、备份和索引重新生成。相同 COLMAP 原始世界坐标允许保留人工 T、OBB 和坐标版本，但不允许复用旧高斯行号。M0 导出接口包含真实来源；后续消费者代码本次未适配。

workspace 草稿 PUT 的 base_revision 必须等于当前修订，否则返回 409，防止升级前页面的自动保存覆盖新工作区。
