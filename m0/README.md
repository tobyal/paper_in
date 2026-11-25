# M0：工业场景先验标注平台

服务器本地运行的 Vue 3 + Konva + FastAPI 标注工作台。全部视觉模型推理在 A6000 上执行；前端依赖已打包为本地静态文件，无 CDN、外部模型服务或遥测请求。

## 启动与访问

工程目录：`/mnt/sda/ubuntu/lkx/papers/paper_in`。

```bash
cd /mnt/sda/ubuntu/lkx/papers/paper_in
# 现有服务器环境已经安装。新环境仅第一次执行：
envs/relags/bin/python -m venv --system-site-packages envs/m0
envs/m0/bin/python -m pip install -r m0/requirements.txt
envs/m0/bin/python -m m0.prepare

# 推荐：独立用户级服务，不依赖 SSH 会话存活
bash m0/service.sh start
bash m0/service.sh status
# 可选：前台运行
bash m0/start.sh
```

默认使用 GPU 3，监听 `127.0.0.1:28760`。使用 `M0_GPU=... M0_PORT=... bash m0/service.sh start` 可选择空闲设备及端口；不要重复启动同一服务。

Windows 本机运行 `m0/forward.ps1` 并保持 SSH 进程存活，然后打开 **http://127.0.0.1:18766**。脚本使用现有 A6000 密钥和证书；`-F NUL` 避免重复建立 SSH 配置中的代理反向转发。

通用 SSH 命令（若配置已有反向转发，请不要重复申请同一端口）：

```bash
ssh -N -L 18766:127.0.0.1:28760 ubuntuA6000
```

此服务面向单研究项目的受信任 SSH 用户，只绑定环回地址。没有开发公网身份认证或多租户系统，不应直接暴露到公网。

## 七步工作流

1. **场景与区域**：浏览真实 RGB、相机轨迹和高斯中心；选择至少三个非共线地面点、原点和两个主通道方向点；拟合并核对轴向。在工业 XY 俯视图绘制区域。新渲染由官方几何接口生成，未读取旧地面估计。
2. **对象清单**：在训练图像上画粗框，填写中英文类别、建模粒度和候选区域。每次创建分配永久实例 ID；相似设备分别创建。
3. **SAM 分割**：框、正点、负点联合提示；选择三个真实候选之一；画笔、橡皮、多边形修正；撤销/重做、缩放和平移。掩膜以原始去畸变图像分辨率保存。多视角绑定同一个 object_id。
4. **语义描述**：查看原图、掩膜叠加、对象裁剪；编辑中英文名称、同义词、简短描述和可见属性。可粘贴候选 JSON，未知填写 unknown。视觉描述中不写待评价的空间关系。
5. **关系定义**：定义 near、left_of、right_of、inside_region；明确方向、单位、距离规则和阈值。仅填写必要的非几何已知知识；允许已知先验集合为空。
6. **实验评价**：留出掩膜仅允许原始 44 张测试图像；独立管理语义查询、true/false/unknown 关系和七类查询。禁止与先验重复的关系（含对称/互逆形式）。
7. **检查与导出**：问题可定位到对应对象/视角。六步均满足实际检查并经人工确认后，才允许冻结。先验与评价分别导出，不混合目录。

界面里的“确认”表示人工审核。开发验收生成的真实对象候选、真实 SAM 掩膜和候选描述均保留为 draft/candidate；不能据此宣称正式 M0 已完成。

## 保存、恢复与版本

- 掩膜编辑草稿在操作后约 0.8 秒保存到服务器。已有对象切换视角/页面时先提交待保存草稿；刷新后恢复。
- 保存/确认生成不可覆盖的掩膜文件，保存原始三个候选、最终二值 PNG、提示、像素尺寸、编辑操作、叠加图、透明背景裁剪和 SHA-256。
- SQLite 事务修订是权威存储；标准 JSON/NPY 是其可恢复投影。服务重启可重建 JSON，避免半次保存。
- 每次数据写入检查 revision；过期编辑返回 409，保留草稿并要求刷新，避免静默覆盖。
- 上游修改清除本步和下游完成确认，记录受影响步骤。已有结果保留供复核；坐标系变化后的区域必须重新确认。
- 冻结前验证原图、几何、相机、划分和模型来源哈希。下载冻结版本时再次验证文件哈希；旧版本不随新编辑变化。
- 原始推理与服务日志分别在 `industrial_scene_prior/.inference/`、`.jobs/`、`logs/m0_*`。独立用户服务停止命令：`bash m0/service.sh stop`。

## 数据、接口与验证

- [数据格式](docs/DATA_FORMAT.md)
- [M1–M5 输入契约](docs/M1_M5_INTERFACE.md)
- [开发与实际验收报告](docs/IMPLEMENTATION_REPORT.md)
- [原始用户需求](docs/REQUIREMENTS.zh.md)

```bash
# 真实数据闭环验收：复用工作台中真实推车对象，生成新的 SAM 草稿，不设置人工确认
envs/m0/bin/python -m m0.tests.real_scene_acceptance
# 隔离目录中的 API、版本、泄漏防护、导出校验
OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=1 envs/m0/bin/python -m m0.tests.test_contract
# 更新当前正式目录的实际数据完成状态
envs/m0/bin/python -m m0.report
```

自动测试只验证软件行为，不能替代人工确认设备身份、地面方向、实例边界、语义或评价答案。M2–M5 正式算法未在本平台中实现。

## 依赖来源

Vue 3.5.13 与 Konva 9.3.18 的原许可保留在 `static/vendor/`。SAM 使用现有官方 ViT-H 权重与 [SamPredictor 接口](https://github.com/facebookresearch/segment-anything/blob/main/segment_anything/predictor.py)；画布采用 [Konva](https://konvajs.org/docs/overview.html)，前端按 [Vue 无构建工具用法](https://vuejs.org/guide/quick-start.html)加载本地依赖，后端静态资源由 [FastAPI](https://fastapi.tiangolo.com/tutorial/static-files/) 提供。几何渲染仍使用仓库所固定的 ReLaGS 官方接口与原许可。
