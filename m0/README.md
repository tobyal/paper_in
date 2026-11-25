# M0 v2：三维工业先验工作台

M0 只准备研究空间、工业对象粗框、基础文本以及可选的一张训练参考掩膜。正式多视角建模、语义融合、场景图和查询属于 M1–M5。新版替换七步主流程，**不再要求二维锚框、区域、多视角掩膜、关系或评价标注**。

## 启动与访问

服务器工程：/mnt/sda/ubuntu/lkx/papers/paper_in。

~~~bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in
# 仅首次安装；复用已有研究环境中的 CUDA/2DGS/SAM，独立安装 Web 依赖
envs/relags/bin/python -m venv --system-site-packages envs/m0
envs/m0/bin/python -m pip install -r m0/requirements.txt
# 生成新的几何显示与原始相机索引；不读取旧语义或旧 M0 标注
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 envs/m0/bin/python -m m0.prepare
bash m0/service.sh start
bash m0/service.sh status
# 停止自己的服务
bash m0/service.sh stop
~~~

默认 GPU 3、服务器 127.0.0.1:28760。Windows 运行 m0/forward.ps1，浏览器打开 **http://127.0.0.1:18766**。启动脚本也支持前台运行 bash m0/start.sh。若修改端口/GPU，首次启动前设置 M0_PORT/M0_GPU；已有活动服务不会被重复启动。它是单研究项目服务，使用 SSH 隧道访问，没有公网登录或多租户管理。

所有静态依赖在本地加载，无 CDN 或外部视觉服务。新数据目录为 industrial_scene_prior_v2/；旧 industrial_scene_prior/ 保留原样，完整备份位置记录于部署报告。不要将 M0_DATA 指向 V1 目录。

## 两个主页面

**01 工业场景确定**

四个窗口共享同一空间框：自由三维、俯视、正视、侧视。左键旋转三维，右键平移，滚轮缩放；正交视图中拖动黄色边界/角点改变尺寸，拖动圆形中心移动。绿色线表示研究范围。可用“场景全览”“聚焦对象”和各视窗 ↺ 调整观察。

初始方向仅来自当前几何和相机的自动候选。右侧滑杆改变场景方向，“翻转上下”“调转前方”处理符号。初始底面取稳健高度范围，不把最大平面冒充地面。调整框底面，与真实地板核对后，再勾选底面和方向并确认。所有尺寸是 **SfM 相对单位，不是米**。

**02 工业对象确定**

点击“新建对象”，再点击三维设备表面，自动分配永久 ID 和初始粗框。用三视图调整中心和大小；填写中英文名称、简短双语视觉描述，人工核对后确认。允许框含少量背景；框内点只可作为粗略候选。类似设备单独创建。显示/隐藏不改变身份确认；删除为可追踪的软删除。

对象编辑中可打开“可选：单张 SAM 参考”。依据相机投影推荐少量完整入镜的训练图像，选择一张，使用投影提示框和正负点运行 SAM。支持三个候选、画笔/橡皮、多边形、撤销重做及原分辨率保存。它不运行批量分割或三维融合。推荐仅依据几何投影，不能保证遮挡情况或设备身份。

**检查 / 导出**

场景、至少一个对象及其基础文本经人工确认即可冻结，SAM 不必填写；没有 5–8 个对象不会阻止导出。导出中没有评价数据、最终对象高斯索引或场景图。候选参考掩膜不进入正式导出。冻结会校验来源及文件哈希，旧版本不可覆盖。

## 自动保存与恢复

鼠标框调整和文字在约 0.65 秒后保存为服务器草稿；参考掩膜约 0.8 秒。请看到保存完成后再关闭。刷新可恢复同一修订的草稿。切换对象/页面会先保存待修改内容。显式确认只在人工点击确认时发生，不把自动保存变成确认。

SQLite 保存事务修订，标准 JSON/NPY/JPEG 为可重建投影。并发旧修订返回 409。改变场景框/坐标会重新表达现有粗框并置为待复核，保留原始世界范围；旋转坐标后 AABB 可能扩大，需要重新调整。旧参考降为草稿。冻结版本保持原状。

## 文档与验证

- [新版需求](docs/REQUIREMENTS_V2.zh.md)
- [数据格式](docs/DATA_FORMAT.md)
- [M1–M5 输入接口](docs/M1_M5_INTERFACE.md)
- [实际验收、备份与限制](docs/IMPLEMENTATION_REPORT.md)

~~~bash
# 隔离目录软件契约测试；不会将正式数据确认为人工真值
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 envs/m0/bin/python -m m0.tests.test_contract
# 读取真实浏览器验收对象与新 SAM/渲染结果，核对尺寸、来源及恢复
envs/m0/bin/python -m m0.tests.real_scene_acceptance
# 更新正式目录状态报告
envs/m0/bin/python -m m0.report
~~~

浏览器显示所有有限的 MWP 高斯中心和 SH DC 颜色（本场景 816,661 点），并提供服务器官方 2DGS 渲染。浏览器不是普通 3DGS splat 渲染器；没有将二维高斯错误解读为三维高斯。细结构和表面完整性仍应结合原图与真实渲染检查。

Three.js r169 / OrbitControls、Vue 3.5.13、Konva 9.3.18 均保留原许可。OrbitControls 的唯一依赖改为本地相对路径。参考 [Three.js BufferGeometry](https://threejs.org/docs/#api/en/core/BufferGeometry)、[OrbitControls](https://threejs.org/docs/#examples/en/controls/OrbitControls)、[官方 SAM predictor](https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/predictor.py)。V1 源码可从 Git 提交 6d50092 或服务器备份恢复。
