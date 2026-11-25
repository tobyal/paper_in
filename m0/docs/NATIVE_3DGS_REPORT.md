# M0 v2.2：切换原工程原生 3DGS

2026-11-26。按用户要求仅修改 M0 Web 及其数据、渲染和导出绑定。未重新训练，未修改 ReLaGS、Baseline 0/R1 或 M1–M5 实现。旧 2DGS 数据退出当前 M0，保留归档。

## 复用来源

工程根目录：`/mnt/sda/ubuntu/lkx/papers/paper_in`。以下目标路径均相对此根目录；运行时无 paper_eli 绝对路径依赖。

| 原工程来源（paper_eli/ 下） | 当前工程已有副本 | 用途 |
| --- | --- | --- |
| outputs/reconstruction/point_cloud/iteration_30000/point_cloud.ply | data/gaussian_scene/original_3dgs/point_cloud/iteration_30000/point_cloud.ply | 未编辑原生 3DGS，1,828,777 个高斯，三轴尺度、旋转、不透明度、三阶 SH |
| data/industrial/images | data/images | 350 张去畸变 RGB，1875 × 1056 |
| data/industrial/sparse/0 | data/colmap/sparse/0 | 原 COLMAP 世界坐标、内外参和稀疏重建 |
| outputs/reconstruction/cfg_args、cameras.json | data/gaussian_scene/original_3dgs/ 下同名文件 | 模型来源记录；不读取 cfg_args 中旧绝对路径运行 |
| 原训练/留出划分 | data/scene_information/camera_split.json | 保持 306 / 44；M0 参考只允许训练图 |

逐项核对原工程和当前副本：PLY、3 个 COLMAP BIN、350 张图像，共 354 个文件 SHA-256 一致。未复制生成模型、历史检查点、LangSplat 特征、旧设备定位或编辑结果。

PLY SHA-256：`1d5cc6a5b58e7d99fbefd54ba6de7ab351ee23b884b2fcacba11720906b5bf7a`。完整来源校验保存在 `logs/m0_native3dgs_source_audit.json`。

## 渲染与交互

原生渲染器来自原工程的官方 Gaussian Splatting 源码，固定提交 `2eee0e26d2d5fd00ec462df47752223952f6bf4e`。最小 Python 源码置于 `m0/vendor/gaussian_splatting/`，原许可与逐文件哈希完整保留。仅包初始化文件为 M0 精简，不运行上游 Scene 构造器或训练。

CUDA rasterizer 提交 `59f5f77e3ddbac3ed9db93ec2cfe99ed6c5d121d`，源码复制到 `envs/m0_build/` 后，以 CUDA 11.8 / PyTorch 2.2.0 / SM86 编译并只安装到 `envs/m0`。构建日志：`logs/m0_native3dgs_build.log`。不在 paper_eli 中编译，不改变 envs/relags。

`native_3dgs.py` 负责加载完整三轴高斯、MiniCam 相机适配和可选范围子集。未将 3DGS 压缩为两尺度，也不调用 ReLaGS 语义缓冲。固定参考视图保留 COLMAP 的 fx/fy，输出 RGB 和真实可见高斯统计；原生渲染器未提供的表面深度/alpha 不生成伪数据。

第一步沿用几何总览；第二步移动、环绕、缩放始终显示原生 3DGS，点中心仅用于内部拾取。保留单请求流式渲染、图像与框相机同步、失败时保留上一高斯帧、可旋转 OBB、显隐和一键保存。页面标注 v2.2 / 原生 3DGS，服务 `/api/health` 和渲染响应头也标记实际后端。

## 人工标注迁移

新目录 `industrial_scene_prior_3dgs/`，旧目录 `industrial_scene_prior_v2/` 保持原样，原冻结版本仍属于旧数据集。迁移 r18 → r19，并分配新的 dataset_id；禁止旧浏览器修订覆盖新 workspace 草稿。

原 COLMAP 图像/相机清单逐项一致，因此保留用户确认的 T、场景框、`coord_2755efc4f61b`、对象 ID、OBB、文字、状态、显隐、删除记录，以及两份自动草稿。保留 M0 自身的单张参考及原 SAM 候选和编辑历史；没有导入 paper_eli 的语义标注，也没有把草稿变成人工确认。

场景索引从新 PLY 原始 vertex 顺序重新计算：当前范围包含 **1,760,745** 个高斯。场景总览和对象预览重新生成。新 manifest 明确记录 native_3dgs、源 PLY 哈希和迁移来源，旧高斯行号未复用。正式完整记录见 `industrial_scene_prior_3dgs/MIGRATION.json`。

切换前代码和标注备份：`backups/m0_v2_before_obb_20261126T013933/`（沿用备份脚本名称）。停止服务后的最终事务快照、参考和旧版本备份：`backups/m0_before_native3dgs_4df898eeb4fd/`。后者为 r18 的权威迁移来源。

## 实际验证

- 来源、人工字段和草稿逐字段一致；新场景索引与 1,828,777 个原始中心的包含判定完全相等。旧 workspace 修订返回 409。`logs/m0_native3dgs_contract.json`。
- 以 COLMAP 原始外参独立构造同一漫游相机，与服务返回 RGB 逐像素比较，JPEG 平均绝对误差 **0.0**。原固定参考 `frame_000340` 成功渲染完整模型。相机保持 Three 的右/上/后与 COLMAP 右/下/前转换。
- 两个 1250 × 704 训练位姿，场景内 1,760,745 个高斯，服务器端单帧约 **50.7 / 51.7 ms**；PyTorch 已分配约 **855 MB**。这些是本次服务内测量，不是浏览器端帧率保证。`logs/m0_native3dgs_renderer/result.json`。
- 22 组真实几何 Web 契约，以及 OBB、批量事务、保存恢复、旋转导出、可选参考原像素和冻结版本校验通过。全部确认/冻结测试在 logs 下隔离副本中运行；未确认正式对象。日志 `m0_native3dgs_web_contract.log`、`m0_native3dgs_obb_contract.log`、`m0_native3dgs_reference_contract.log`。
- 10 项连续高斯显示调度契约通过。实际浏览器聚焦和拖动后，高斯呈现帧计数 3 → 10，框仍叠加在高斯画面；本地截图 `logs/m0_native3dgs_web.jpg`。
- ReLaGS 已有工作区差异 SHA-256 仍为 `2418e82357232c76300b5de6563bca0bc1756ce9325def19b44c5eae615880a8`。

首次相机图像比较测试错误地假设原始 fx=fy；实际为 1412.5745 / 1406.3618，且半分辨率取整也改变宽高比，导致两种不同内参的图像差异 4.90。修正测试为同一实际漫游 FOV 后误差 0.0，未修改渲染算法或放宽阈值。失败日志保留在 `logs/m0_native3dgs_contract_first_attempt.log`。

## 当前限制

自由视点超出原图充分覆盖的位置仍可见原模型的漂浮、模糊或拉伸；本次按要求原样复用，未修复模型或优化算法。人工旧框的空间位置被精确保留，设备身份仍由用户复核。现有 M1–M5/Baseline 的旧 2DGS 索引不能用于新 M0 模型；其代码尚未调整，也未重新执行。
