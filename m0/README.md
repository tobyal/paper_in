# M0 v2.2：原生 3DGS 工业先验工作台

M0 只准备研究空间、工业对象粗框、基础文本以及可选的一张训练参考掩膜。正式多视角建模、语义融合、场景图和查询属于 M1–M5。新版替换七步主流程，**不再要求二维锚框、区域、多视角掩膜、关系或评价标注**。

## 启动与访问

服务器工程：/mnt/sda/ubuntu/lkx/papers/paper_in。

~~~bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in
# 仅首次安装；独立安装 Web 依赖和原生 3DGS 渲染扩展，不改 ReLaGS 环境
envs/relags/bin/python -m venv --system-site-packages envs/m0
envs/m0/bin/python -m pip install -r m0/requirements.txt
# 从已有原工程复制并编译固定版本的官方 CUDA 源码；原目录只读
envs/m0/bin/python -m m0.install_native_renderer --source /mnt/sda/ubuntu/lkx/papers/paper_eli/repos/gaussian-splatting/submodules/diff-gaussian-rasterization
# 生成新的几何显示与原始相机索引；不读取旧语义或旧 M0 标注
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 envs/m0/bin/python -m m0.prepare
bash m0/service.sh start
bash m0/service.sh status
# 停止自己的服务
bash m0/service.sh stop
~~~

默认 GPU 3、服务器 127.0.0.1:28760。Windows 运行 m0/forward.ps1，浏览器打开 **http://127.0.0.1:18766**。启动脚本也支持前台运行 bash m0/start.sh。若修改端口/GPU，首次启动前设置 M0_PORT/M0_GPU；已有活动服务不会被重复启动。它是单研究项目服务，使用 SSH 隧道访问，没有公网登录或多租户管理。

所有静态依赖在本地加载，无 CDN 或外部视觉服务。当前数据目录为 industrial_scene_prior_3dgs/。原生 3DGS 来自 data/gaussian_scene/original_3dgs/ 的未编辑 30000 次迭代场景，已与 paper_eli 原文件校验一致。运行时不依赖 paper_eli 路径。旧 industrial_scene_prior/、industrial_scene_prior_v2/ 和冻结版本保留归档。不要将 M0_DATA 指向旧目录。已有标注的切换记录见 [3DGS 迁移报告](docs/NATIVE_3DGS_REPORT.md)。

## 两个主页面

**01 工业场景确定**

四个窗口共享同一空间框：自由三维、俯视、正视、侧视。左键旋转三维，右键平移，滚轮缩放；正交视图中拖动黄色边界/角点改变尺寸，拖动圆形中心移动。绿色线表示研究范围。可用“场景全览”“聚焦对象”和各视窗 ↺ 调整观察。

初始方向仅来自当前几何和相机的自动候选。右侧滑杆改变场景方向，“翻转上下”“调转前方”处理符号。初始底面取稳健高度范围，不把最大平面冒充地面。调整框底面，与真实地板核对后，再勾选底面和方向并确认。所有尺寸是 **SfM 相对单位，不是米**。

**02 工业对象确定**

第二步使用一个大幅高斯三维视窗。左键环绕、右键平移、滚轮缩放；点击画面后 WASD 移动、Q/E 升降、Shift 加速。移动、旋转和缩放期间持续请求服务器官方原生 3DGS 画面，不切换点云。等待新帧或网络失败时保留上一张高斯画面，包围框、手柄和拾取使用与该画面完全相同的相机。一次只发送一个渲染请求，后续请求采用最新相机位置，避免积压旧操作。首次打开等待高斯加载；实际帧率仍受 GPU、网络和 JPEG 传输影响，它不是浏览器逐帧本地 splatting。

点击“新建对象”，再点击设备表面创建独立框。使用“移动 / 缩放 / 旋转”切换彩色箭头、轴向方块和旋转圆环。左侧逐个显示/隐藏，也可全部显示/隐藏；选中对象后可聚焦。连续修改多个设备，最后点击顶部“一键保存全部”，全部变化写入同一事务修订。未保存新对象使用 draft_ ID，提交时统一分配永久 obj_ ID。同类设备分别建框。显示/隐藏不会取消已确认身份；删除为可追踪的软删除。

设备框保存中心、局部三轴尺寸和 xyzw 四元数，旋转在刷新、可选参考投影和导出中保留。基础名称/描述可稍后填写；“一键保存”允许草稿，不会替用户确认身份。填写中英文名称、简短双语描述并核对后，再使用“确认并保存对象”。允许框含少量背景；框内点只可作为粗略候选。

对象编辑中可打开“可选：单张 SAM 参考”。依据相机投影推荐少量完整入镜的训练图像，选择一张，使用投影提示框和正负点运行 SAM。支持三个候选、画笔/橡皮、多边形、撤销重做及原分辨率保存。它不运行批量分割或三维融合。推荐仅依据几何投影，不能保证遮挡情况或设备身份。

**检查 / 导出**

场景、至少一个对象及其基础文本经人工确认即可冻结，SAM 不必填写；没有 5–8 个对象不会阻止导出。导出中没有评价数据、最终对象高斯索引或场景图。候选参考掩膜不进入正式导出。冻结会校验来源及文件哈希，旧版本不可覆盖。

## 自动保存与恢复

鼠标框调整、文字和所有待修改设备在约 0.65 秒后保存为服务器工作草稿；参考掩膜约 0.8 秒。请看到保存完成后再关闭。刷新可恢复同一修订的草稿，升级前的单对象自动草稿也会恢复。切换对象保留未提交编辑，切换页面/打开参考或导出时统一提交。显式确认只在人工点击确认时发生，不把自动保存或批量保存变成确认。

SQLite 保存事务修订，标准 JSON/NPY/JPEG 为可重建投影。并发旧修订返回 409；整批验证失败不提交任何对象。改变场景框/坐标会通过刚体变换重新表达 OBB 并置为待复核，保持原始世界角点及局部尺寸。旧参考降为草稿。冻结版本保持原状。

## 文档与验证

- [原生 3DGS 切换、来源及验证](docs/NATIVE_3DGS_REPORT.md)
- [新版需求](docs/REQUIREMENTS_V2.zh.md)
- [数据格式](docs/DATA_FORMAT.md)
- [M1–M5 输入接口](docs/M1_M5_INTERFACE.md)
- [实际验收、备份与限制](docs/IMPLEMENTATION_REPORT.md)
- [单视窗、OBB 与批量保存验收](docs/OBB_ROAMING_REPORT.md)
- [移动期间保持高斯显示的修复与验证](docs/CONTINUOUS_GAUSSIAN_FIX.md)

~~~bash
# 隔离目录软件契约测试；不会将正式数据确认为人工真值
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 envs/m0/bin/python -m m0.tests.test_contract
# 独立数据副本上验证 OBB、批量保存和可选参考导出
envs/m0/bin/python -m m0.tests.test_obb_roaming
envs/m0/bin/python -m m0.tests.test_optional_reference
# 只读验证实际高斯漫游
envs/m0/bin/python -m m0.tests.test_roam_renderer
# 更新正式目录状态报告
envs/m0/bin/python -m m0.report
~~~

第一步场景总览和内部拾取使用原生 3DGS 的全部 1,828,777 个有限中心；第二步始终显示服务器原生三维高斯椭球渲染，保留完整三轴尺度、旋转、不透明度和三阶 SH。支持场景范围内 / 完整背景，移动时不切换点云。固定参考相机保留 COLMAP 内参；本版本只输出原生 RGB，不伪造 2DGS 表面深度。后续 M1–M5 代码和 Baseline 0/R1 尚未切换。

Three.js r169 / OrbitControls、Vue 3.5.13、Konva 9.3.18 均保留原许可。OrbitControls 的唯一依赖改为本地相对路径。参考 [Three.js BufferGeometry](https://threejs.org/docs/#api/en/core/BufferGeometry)、[OrbitControls](https://threejs.org/docs/#examples/en/controls/OrbitControls)、[官方 SAM predictor](https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/predictor.py)。V1 源码可从 Git 提交 6d50092 或服务器备份恢复。

原生渲染器最小源码位于 vendor/gaussian_splatting/，固定版本和逐文件哈希见 UPSTREAM.json，保留 Inria 的研究 / 非商业评估许可 LICENSE.md。M0 适配器仅加载模型、转换相机和选取场景子集，不改变渲染算法。
