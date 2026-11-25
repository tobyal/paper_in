# M0 数据格式 v1.0

正式工作目录为项目下的 `industrial_scene_prior/`，可通过 `M0_DATA` 指定独立测试目录。不要把自动验收目录当作正式数据。

## 来源及像素/空间坐标

`.assets/images.json` 记录每张原始去畸变图像的永久 `image_id`、文件名、1875×1056 原始尺寸、train/heldout、SHA-256、COLMAP K、世界到相机 R/t、相机中心与朝向。原始划分为 306 训练 / 44 留出，不能在 UI 改写。

像素坐标 x 向右、y 向下，整数为像素中心。目标框使用 `[x0,y0,x1,y1]`，右下边界按半开区间解释。SAM 提示按原始坐标提交，SAM 内部执行其原有缩放。画布的平移缩放只影响显示。二值 PNG 使用 L 模式和 0/255，尺寸必须与图像完全一致。

工业坐标转换采用列向量齐次形式：`p_industrial = coordinate_transform @ p_colmap`。+X 右，+Y 前，+Z 上。`coordinate_system.json` 保留原始选点、平面、拟合误差、方向提示、审核和 `coordinate_revision`。所有区域与粗略 ROI 都引用此修订。没有真实尺度标定，因此单位仅为 `sfm_relative`；关系也可使用显式定义的 normalized 距离。

## 主文件

| 文件 | 内容 |
|---|---|
| `priors/scene/coordinate_system.json` | 人工地面/轴向定义、审核、4×4 转换 |
| `priors/scene/coordinate_transform.npy` | float64，形状 (4,4)，COLMAP → 工业坐标 |
| `priors/scene/regions.json` | region_id、名称、工业 XY 多边形、include、参考图及审核 |
| `priors/scene/scene_reference_views.json` | 人工核对坐标/渲染所用的 image_id 列表 |
| `priors/objects/object_catalog.json` | 永久 object_id、双语类别、granularity、候选区域、anchor_image_id/bbox、可选 parent、状态及排除原因 |
| `priors/objects/object_descriptions.json` | 按 object_id 索引的名称、synonyms_en 数组、双语视觉描述、可见属性、字段来源与审核 |
| `priors/masks/<object_id>/annotations.json` | 本对象的训练图像标注记录 |
| `priors/masks/<object_id>/original/` | 本次 M0 推理的原始候选 PNG 与推理配置 |
| `priors/masks/<object_id>/confirmed/` | 不可覆盖的保存结果；是否正式确认以 annotation.review_status 为准 |
| `priors/masks/<object_id>/edits/` | 选择候选、原始像素编辑操作、操作者和时间 |
| `priors/masks/<object_id>/overlays/` | 叠加 JPEG、按掩膜提取的 RGBA PNG |
| `priors/spatial/coarse_rois.json` | 可选候选范围；仅搜索约束，没有最终高斯实例索引 |
| `priors/relations/relation_schema.json` | 词汇、双语表达、方向/互逆、实体类型、工业参考系、距离定义、阈值/单位、规则来源 |
| `priors/relations/known_relations.json` | 必要已知知识；可为空，不作为自动预测评价目标 |
| `ground_truth/heldout_masks/<object_id>/` | 与训练掩膜同构的独立留出标注 |
| `ground_truth/semantic_queries.json` | 不直接复制输入名称/描述的语义查询 |
| `ground_truth/reference_relations.json` | 人工参考关系及 true / false / unknown；unknown 不是负例 |
| `ground_truth/relational_queries.json` | 七种查询类型、expected_object_ids 数组、allow_multiple、证据与审核 |
| `operation_history/` | 每次修订的操作、操作者、时间、失效下游步骤 |
| `versions/<version>/` | 冻结快照、文件哈希、当次数据来源、分开的导出包 |
| `PRIOR_MANIFEST.json` | schema_version、dataset_id、revision、审核、待复核步骤和版本 |

## 每条掩膜记录

包含 `object_id, image_id, scope, width, height, image_sha256, pixel_coordinates, bbox, area, prompts, sam_job_id, candidate, original_mask_paths, original_sam_mask_path, mask_path, final_confirmed_mask_path, mask_sha256, manually_corrected, edit_history_path, overlay_path, crop_path, visibility, review_status, reviewer, reviewed_at, notes`。

`visibility` 为 `clear / partial / uncertain / not_present / fully_occluded / unannotated`。前三项必须有非空掩膜；后三项没有掩膜文件，不能折叠成负样本。`review_status` 为 `draft / confirmed / needs_review`。只有明确确认的可见掩膜才是后续建模或评价输入。`uncertain` 需要标注者决定是否可接受；应保留备注并在实验中报告。

## API

FastAPI API 文档位于 `/docs`。写操作需要同源请求头 `X-M0-Client: 1`，正式数据修改需要最新 `revision`。确认还需要 `review_ack: true` 和 `reviewer`。草稿不进入正式输入；服务不是多人身份认证系统，审核人姓名由标注者负责。

主要路由：`/api/state`、`/images`、`/objects`、`/sam`、`/jobs/<id>`、`/annotations`、`/drafts/<scope>/<object_id>/<image_id>`、`/descriptions/<id>`、`/scene/fit`、`/scene/reference`、`/regions`、`/relations/schema`、`/relations/records`、`/evaluation/queries`、`/quality`、`/steps/<n>/confirm`、`/freeze`、`/exports/<version>/<scope>`。

后台原始事务保存在 `.m0.sqlite3`。备份时同时保留 SQLite、原始/最终掩膜、`.inference/` 和 `.assets/`；不要只复制 JSON 而遗漏图片。
