#!/usr/bin/env python3
import datetime,json,pathlib
from stage_evidence import evidence
ROOT=pathlib.Path(__file__).resolve().parents[1]
stages=['00_data_check','01_gaussian_scene','02_image_encoding','03_gaussian_pruning','04_superpoint_partition','05_hierarchical_grouping','06_semantic_aggregation','07_object_part_modeling','08_scene_graph','09_relational_query']
descriptions=[
('原工程审计与迁移','原视频、去畸变图、COLMAP、最终 3DGS、历史资料','数据副本、逐文件清单、SHA256、相机划分与统一视角'),
('2DGS 场景准备','原始 RGB、COLMAP、306/44 划分','官方 2DGS 检查点、PLY、统一相机渲染和重建指标'),
('二维分割与语言编码','工业 RGB、原始 SAM/OpenCLIP/OpenSeg 权重','全新四层掩膜、512D CLIP、768D OpenSeg、可视化'),
('最大权重裁剪','训练完成的 2DGS、训练相机','每点贡献、保留/删除索引、裁剪前后 PLY 与图像'),
('初始几何邻接与划分','裁剪后 Gaussian','原始邻接图；原始邻接 Cut Pursuit 诊断（主流程使用重加权邻接）'),
('层次分组','邻接、全新 SAM、相机、高斯','正负边证据、重加权邻接、Cut Pursuit 分组、逐层投影和成员索引'),
('ROFA 语义聚合','逐层分组、逐视角新特征','聚合前特征、视角 ID、异常值掩膜、聚合后特征'),
('对象与部件导出','官方多层 NAG','对象/部件成员、父子关系、着色 PLY、统一视角'),
('场景图与关系预测','768D OpenSeg NAG、官方 GNN、Jina','节点几何、候选边、预测关系和分数、场景图'),
('开放词汇与关系查询','NAG、文本、关系嵌入','官方查询输出、候选分数、选择索引、三维子集与二维图')]
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
rows=[];details=[]
for i,name in enumerate(stages):
    base=ROOT/'outputs/relags_baseline'/name
    state=json.loads((base/'status.json').read_text()) if (base/'status.json').exists() else {'status':'not_started'}
    jobs=[]
    for p in sorted((base/'metrics').glob('*.json')):
        try:
            d=json.loads(p.read_text())
            if 'job' in d:jobs.append(d)
        except Exception:pass
    if state['status'] not in ['completed','failed_full_graph','partial_blocked'] and jobs:
        if any(j['status']=='running' for j in jobs):state['status']='running'
        elif any(j['status']=='failed' for j in jobs):state['status']='failed_partial'
        else:state['status']='partial_outputs_verified'
    if i==1 and state['status']=='not_started':state['status']='environment_preparing' if not (ROOT/'logs/environment.completed').exists() else 'ready_not_run'
    if i==6 and (base/'data/audit_latest.json').exists() and state['status']=='not_started':state['status']='partial_outputs_present'
    label={'completed':'完成并核验','not_started':'尚未执行','running':'运行中','failed_partial':'存在失败尝试，保留日志','failed_full_graph':'完整场景图失败；根层诊断完成','partial_blocked':'开放词汇完成；完整关系查询受阻','partial_outputs_verified':'已有经过核验的子步骤输出','environment_preparing':'环境准备中，兼容性审计已完成','ready_not_run':'依赖就绪，尚未执行','partial_outputs_present':'已有中间产物，尚未完成核验'}.get(state['status'],state['status'])
    rows.append(f'| {i:02d} | {descriptions[i][0]} | {label} | `outputs/relags_baseline/{name}/` |')
    d=f'\n## Stage {i:02d}：{descriptions[i][0]}\n\n状态：**{label}**。\n\n输入：{descriptions[i][1]}。\n\n预期输出：{descriptions[i][2]}。这里只列交付约定；实际生成项以本阶段文件和执行记录为准。\n\n中间结果目录：`outputs/relags_baseline/{name}/data/`；图像/PLY：`visualizations/`；测量与命令：`metrics/`、`runs/`、`run.log`。\n'
    for j in jobs:
        d+='\n- `'+j['job']+'`：'+j['status']+'；命令：`'+j['shell_command']+'`；日志：`'+str(pathlib.Path(j['attempt']).relative_to(ROOT))+'/run.log`。'
        if 'elapsed_seconds' in j:d+=f" 耗时 {j['elapsed_seconds']:.2f} 秒；进程显存采样峰值 {j.get('peak_sampled_own_gpu_mib',0)} MiB。"
        if j.get('validation_error'):d+=' 输出校验异常：`'+j['validation_error']+'`。'
    if state.get('observations'):d+='\n实际观察：'+state['observations']+'\n'
    d+='\n\n实际证据与限制：\n\n'+evidence(ROOT,i,base)+'\n'
    (base/'README.md').write_text(d)
    (base/'config.yaml').write_text(json.dumps({'stage':name,'status':state['status'],'jobs':[{'job':j['job'],'command':j['command'],'inputs':j.get('inputs',[]),'environment':j.get('environment',{}),'attempt':j['attempt']} for j in jobs]},indent=2,ensure_ascii=False))
    details.append(d)
text='# ReLaGS 工业场景复现报告 — Baseline 0\n\n更新时间（北京时间）：'+now+'。\n\n这是基于真实执行状态生成的报告。**尚未生成的结果不视为复现成功**，具体状态见下表。\n\n工作目录：`'+str(ROOT)+'`。原工程严格只读。执行方案见 `EXECUTION_PLAN.md`；迁移见 `DATA_MIGRATION.md` 和逐文件 `DATA_MIGRATION.tsv`。\n\n| 阶段 | 内容 | 实际状态 | 位置 |\n|---|---|---|---|\n'+'\n'.join(rows)+'\n\n## 已确认的适配与边界\n\n- 旧 3DGS 的三轴椭球与官方 2DGS 面元不兼容；重用原图像/COLMAP，重新训练 2DGS。详细静态证据：`outputs/relags_baseline/01_gaussian_scene/data/compatibility_audit.json`。\n- 固定原划分：306 训练、44 测试。统一参考相机见 `configs/reference_views.json`。保留原 COLMAP 坐标，不擅自宣称米制或用旧 LangSplat 地面调整。\n- 512D OpenCLIP 用于开放词汇查询；关系网络需要 768D OpenSeg。同维度 CLIP 不能替代 OpenSeg。采用作者指向的 OpenSeg 函数与公开官方权重进行数据接口适配。\n- 原始 MWP 阈值按论文/launcher 取 0.0005；ROFA tau=3。配置与 CLI 默认存在差异，详见执行方案。\n- 首次 sp_partition 只构造 KNN，真正 Cut Pursuit 在 graph_weight 后执行。层次分组与 ROFA 在同一脚本中交替发生，保存钩子不改变公式、阈值或合并决策。\n- 非核心补丁：明确随机种子、项目内同一预训练权重路径、完整特征文件对恢复、保留异常堆栈、保存中间张量。补丁见 `logs/patches/`。\n- 没有独立语义、实例或关系 GT，不能虚构准确率/mIoU；工业设备型号与公制尺寸缺少来源时标记未知。\n- 共享 GPU，耗时含记录开销，显存为每 5 秒进程采样峰值；不解释为独占硬件论文速度。\n' + ''.join(details)+'\n## 工业问题检查清单（等待真实结果）\n\n逐项检查细杆/管线裁剪、过分割/欠分割、对象部件混合、重复设备实例粘连、跨视角语义漂移、空间关系方向与尺度、查询对象身份。发现的问题以阶段图、索引和日志作为证据；不为了改善表现修改官方核心算法。\n\n## 上游证据\n\n- 论文及附录：`references/ReLaGS_2603.17605.pdf`（20 页）。\n- 官方代码固定提交：`52cc0c98b0ccf9afebea31901bf79246650286b3`。\n- 作者确认 OpenSeg 数据适配与域差异：https://github.com/dfki-av/ReLaGS/issues/3#issuecomment-4507638043 。\n- 作者确认 CLIP/OpenSeg 不可替换：https://github.com/dfki-av/ReLaGS/issues/4#issuecomment-4903379261 。\n- 2DGS README 的 plumerai 链接失效；使用作者官方仓库 hbb1/2d-gaussian-splatting，失败与后续下载日志均保留。\n'
review=ROOT/'INDUSTRIAL_REVIEW.md'
if review.exists():
    start=text.index('## 工业问题检查清单（等待真实结果）')
    end=text.index('## 上游证据',start)
    text=text[:start]+review.read_text()+'\n\n'+text[end:]
final_state=ROOT/'BASELINE_STATUS.json'
if final_state.exists():
    state=json.loads(final_state.read_text())
    text=text.replace('这是基于真实执行状态生成的报告。',state['conclusion_zh']+'\n\n这是基于真实执行状态生成的报告。',1)
(ROOT/'EXPERIMENT_REPORT.md').write_text(text)
print('Updated',ROOT/'EXPERIMENT_REPORT.md')
