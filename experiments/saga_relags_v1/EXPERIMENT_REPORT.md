# SAGA + ReLaGS 工业世界模型实验总结

生成时间：2026-11-26T15:20:40.622660+00:00。实验目录：`/mnt/sda/ubuntu/lkx/papers/paper_in/experiments/saga_relags_v1`。

## 实际结果

- A完成官方SAGA 10,000步共享亲和训练；尝试10个对象，9个通过当前用途的视觉审核，1个保留为失败/待改进结果。通过审核表示设备级查询展示可用，不等于完整精细网格或具有真值认证的分割。
- B构建8类512维共享语义，使用44张真实训练图像裁剪；8/8个小规模表达检查正确。
- C包含33个M0节点、2020条有向几何关系。SoM本地模型已实际运行，可靠视觉语义新增边为0；关系查询主要由几何支持。
- D实际运行5个类别查询和5个关系查询，保存高斯集合、全场景高亮、原始留出RGB的红色投影掩膜。

## 技术路线及复用边界

A使用SAGA v2官方32维亲和特征、尺度门控、对比损失、K=16局部平滑、渲染点击特征及(cos+1)/2阈值筛选。M0替代对象发现、实例身份与粗空间搜索；没有用粗框中的全部高斯冒充分割。B使用已知8类知识、别名和已有CLIP。C保留ReLaGS的编号视觉提示、关系到固定三维ID的映射和多视角证据融合思想，省去2DGS、THGS、群组匹配及GNN。D只查询已经构建的知识，不重新运行SAM/SAGA。

参考：[SAGA官方固定版本](https://github.com/Jumpat/SegAnyGAussians/tree/2d4c5d77c857c956d747e4775d3d72c4ec5dfe16)、[SAGA论文](https://arxiv.org/abs/2312.00860)、[ReLaGS论文](https://arxiv.org/html/2603.17605v1)、[ReLaGS SoM代码](https://github.com/dfki-av/ReLaGS/tree/main/scene_graph/som)。本实验为工业先验适配和方法集成，不将原论文创新归为新算法。

## 数据、环境与兼容性

最新M0保存版本r29，33个对象、8类；原formal review flag仍为draft，保留原样。原生3DGS共1,828,777个Gaussian。训练观测74个：57真实、17已有完整场景虚拟图；44个原始留出图像不参与本次亲和训练、提示和调参。没有使用旧LangSplat特征、旧SAM结果或M2最终实例。

新venv隔离官方SAM与SAGA扩展，基础Torch等库继承既有只读运行环境；Python3.10.13、Torch2.2+cu118、CUDA11.8、A6000。数据包可独立读取，CUDA环境仍需按README安装；未宣称环境完全可搬移。

必要适配包括RGB顺序、CPU序列化、逐相机主点缩放及半像素约定、深度反投影行列坐标、精确邻域缓存和日志/恢复。原损失、门控网络和平滑表达式保留。74个相机的抽样投影最大误差为0.007254像素。原始Gaussian行序已检查，训练后位置/尺度/旋转/透明度与原PLY逐字段一致。

## A：实例分割

训练耗时1852.5秒；Torch训练峰值分配6.86 GiB。整卡显存采样包含原有进程和短时本地VLM，另见日志。保存1,000、2,500、5,000、10,000步完整状态；原始高斯属性未优化。学习率0.0025，采样1000条射线，特征维度32，空间平滑K=16。

重新生成官方SAM自动监督，并加入24张经过可见性与视觉检查的辅助参考掩膜。4张混入邻近设备的高置信度提示被剔除，全部失败掩膜和原始自动掩膜保留。两个带工件夹具台各补两个覆盖物/黑色主体正点击；这些点击坐标明确记录于配置。全部提示仅来自训练观测。

分割采用阈值0.85；设备尺寸经训练尺度分布映射到尺度门控，多个正点击取相似度并集，再施加M0范围约束。重叠候选按学习到的亲和度分配，不做高斯中心投票。

| 对象 | 候选高斯 | 最终高斯 | 查询可用 | 实际检查 |
|---|---:|---:|---|---|
| 物料车 03 / `obj_f9a0e863e32d` | 28512 | 27176 | 是 | 车体、框架及主要底部结构完整，地面背景大幅减少；边缘仍有少量重建伪影。 |
| 物料车 01 / `obj_57b0f30bdd9e` | 7887 | 6409 | 是 | 箱体及蓝色内部主体保留，相邻设备和大部分地面被排除；顶部/背侧有局部漂浮和模糊。 |
| 装配夹具台 02 / `obj_d058f708eb01` | 34150 | 20186 | 是 | 长底座、立柱和主要夹具主体连贯；细线缆、轮缘及少量细杆存在缺失。 |
| 装配夹具台 03 / `obj_09a35ba03c92` | 30873 | 16536 | 是 | 长底座及上部夹持结构保留，未明显混入后方设备；局部细结构有孔洞。 |
| 带黑色工件的夹具台 01 / `obj_ad85774e5f18` | 20962 | 11956 | 是 | 底座、黑色工件及补点后的浅色覆盖物均可见；遮挡侧和黑色结构仍有局部缺口。 |
| 带黑色工件的夹具台 02 / `obj_c812ae8b15bd` | 23676 | 17755 | 是 | 底座、工件和覆盖物主体保留，与邻近料架区分；细支撑及底部有少量模糊残影。 |
| 立式移动冷风机 01 / `obj_04c477562e49` | 10371 | 9442 | 是 | 冷风机机身和正面格栅清楚，周围背景减少；背面存在原3DGS带来的彩色伪影，底部细节不足。 |
| 立式移动冷风机 03 / `obj_c57876bf22ca` | 7431 | 7093 | 是 | 冷风机主体、顶部和格栅保留；下部轮脚及侧面仍有模糊或漂浮高斯。 |
| 多层料架 03 / `obj_b8542dc54ed2` | 30924 | 25553 | 是 | 多层横杆、侧框和架内物料主体保留，未明显吞入旁边冷风机；细杆和少量漂浮背景仍需改进。 |
| 多层料架 04 / `obj_5bfd32389355` | 48158 | 29926 | 否 | 上部架体可辨，但下部明显缺失，并混入邻近白色结构/漂浮背景；保留失败结果，不进入查询可用实例。 |

所有尝试合计选择172,032个互不重复的Gaussian行。对象索引、原生PLY、全场景亲和度、点击向量、投影贡献、三向渲染及粗框参照保存在`outputs/A/extractions/iteration_10000/`。较早检查点和补点前后尝试单独保留。

## B：类别共享语义

每类保存中英文名、同义表达、共有视觉描述、归一化文本与图像向量。同类对象共用类别表示，实例身份由M0和场景图区分。中文主要使用明确别名，英文可用CLIP相似度回退；这不是通用开放词汇类别发现。8个检查样例只是功能检查，不能解释为统计识别准确率。

## C：几何图与视觉关系检查

关系数：`{'behind': 430, 'near': 130, 'left_of': 383, 'right_of': 383, 'nearest_to': 264, 'in_front_of': 430}`。+X为右，+Y为前，+Z为上，使用SfM相对单位。左右/前后需要工业轴向包围区间间隔超过0.02；near为包围区间距离小于0.35；nearest_to按参照对象和目标类别，在全部33个对象中比较中心距离，保留并列。显示图仅抽取少量可读关系，全图保留全部证据。

SoM在3个真实训练视角上使用M0已知ID和可见粗候选轮廓标号。服务器本地qwen3.5:9b进行了3次初始推理及2次描述补查，没有工业图像外传。初始两次说明过于简略，补查中仍出现冷风机/工作台识别混淆；这部分不能视为可靠的对象识别验证。没有获得满足多视角和几何接触条件的支撑/包含边，未强行补造关系，也不能据此断言场景不存在此类关系。

本次设备级节点通常是彼此独立的完整设备，架内物料、设备部件未另立节点，也限制了包含/支撑关系的可表达范围。C的可用成果是带证据的几何场景图，视觉语义关系提升仍需后续验证。

彩色实例PLY保留真实Gaussian结构；三维关系线PLY与原场景同坐标；展示图由完整原生3DGS渲染叠加真实实例颜色和三维中心投影连线生成。路径：`outputs/C/visualizations/`。

## D：语言与关系查询

类别候选只包含审核可用的实例；所有M0节点可作为参照。关系查询的参照可为类别或具体设备名称，满足多个条件时允许多结果。演示文本按真实图中能够区分同类设备的条件选择，执行时只传文本给统一解析器，不传预设答案。

| 查询 | 同类候选数 | 返回数 | 返回对象 |
|---|---:|---:|---|
| 物料车 | 2 | 2 | obj_f9a0e863e32d, obj_57b0f30bdd9e |
| 装配夹具台 | 2 | 2 | obj_d058f708eb01, obj_09a35ba03c92 |
| 带黑色工件的夹具台 | 2 | 2 | obj_ad85774e5f18, obj_c812ae8b15bd |
| 多层料架 | 1 | 1 | obj_b8542dc54ed2 |
| 立式移动冷风机 | 2 | 2 | obj_04c477562e49, obj_c57876bf22ca |
| 距离装配夹具台 01最近的物料车 | 2 | 1 | obj_57b0f30bdd9e |
| 距离装配夹具台 01最近的装配夹具台 | 2 | 1 | obj_d058f708eb01 |
| 距离装配夹具台 01最近的带黑色工件的夹具台 | 2 | 1 | obj_ad85774e5f18 |
| 距离装配夹具台 01最近的立式移动冷风机 | 2 | 1 | obj_04c477562e49 |
| 位于装配夹具台 01左侧的物料车 | 2 | 1 | obj_57b0f30bdd9e |

每个查询保存两个留出视角，投影由完整场景alpha合成后的目标贡献大于0.5产生，保留真实遮挡。最初仅按框面积选展示相机，产生了被遮挡目标几乎不可见的图；该图集保存在outputs/D_history/bbox_only_display_selection。最终使用冻结实例在44个留出相机下的实际可见贡献选择展示相机，没有据此修改实例、提示或阈值。红色区域来自固定三维实例，而非直接复制输入SAM掩膜。没有独立人工真值，不报告IoU准确率；训练提示一致性仅保留为内部检查。

## 验证及失败保留

整体产物检查：`True`。检查22273个既有输出文件的大小/修改时间及受保护输入源码哈希，旧文件改动0项；旧输出新增0项。独立包查询退出码0；独立包渲染最大贡献误差0、掩膜一致性1.00000000。这项一致性验证接口实现，不是分割精度。

保留的工程失败包括旧SAM接口不兼容、第一次批量提取缺少MiniCam特征尺寸字段、OpenCV绘图输入内存布局不连续；均已定位并只在新方案内修复。语义分割失败对象、受污染提示和VLM不充分回复分别保留，无粗框结果替换。另保存独立彩色Gaussian实例图，减少背景遮挡对空间关系查看的影响；完整场景图仍保留。完整运行记录如下。

| 阶段 | 状态 | 秒数 | 日志记录 |
|---|---|---:|---|
| A_affinity_training | completed | 1852.5 | `logs/A_affinity_training/20261126T144157724918Z/result.json` |
| A_final_extraction | completed | 25.2 | `logs/A_final_extraction/20261126T151254562306Z/result.json` |
| A_final_render | completed | 8.5 | `logs/A_final_render/20261126T151319881383Z/result.json` |
| A_mask_scales | completed | 112.6 | `logs/A_mask_scales/20261126T143151382542Z/result.json` |
| A_mask_scales_final | completed | 118.0 | `logs/A_mask_scales_final/20261126T143959625790Z/result.json` |
| A_masks | failed | 15.8 | `logs/A_masks/20261126T142259312289Z/result.json` |
| A_masks | completed | 250.6 | `logs/A_masks/20261126T142623811261Z/result.json` |
| A_preview_1000 | failed | 4.3 | `logs/A_preview_1000/20261126T144550437620Z/result.json` |
| A_preview_1000 | completed | 26.5 | `logs/A_preview_1000/20261126T144609194400Z/result.json` |
| A_preview_2500 | completed | 28.8 | `logs/A_preview_2500/20261126T145058226435Z/result.json` |
| A_preview_render_1000 | completed | 9.1 | `logs/A_preview_render_1000/20261126T144635731421Z/result.json` |
| A_preview_render_2500 | completed | 11.8 | `logs/A_preview_render_2500/20261126T145127331440Z/result.json` |
| A_prompt_check_2500 | completed | 33.7 | `logs/A_prompt_check_2500/20261126T145326712472Z/result.json` |
| A_prompt_render_2500 | completed | 9.0 | `logs/A_prompt_render_2500/20261126T145400494481Z/result.json` |
| A_reference_prompts | completed | 38.8 | `logs/A_reference_prompts/20261126T143112529847Z/result.json` |
| A_reference_prompts_visibility | completed | 44.6 | `logs/A_reference_prompts_visibility/20261126T143826779635Z/result.json` |
| A_training_plot | completed | 1.3 | `logs/A_training_plot/20261126T151326335539Z/result.json` |
| B_category_semantics | completed | 8.6 | `logs/B_category_semantics/20261126T144038178949Z/result.json` |
| C_final_visualizations | failed | 4.6 | `logs/C_final_visualizations/20261126T151420877707Z/result.json` |
| C_final_visualizations | completed | 4.8 | `logs/C_final_visualizations/20261126T151440695852Z/result.json` |
| C_geometry_and_local_som | completed | 53.7 | `logs/C_geometry_and_local_som/20261126T144203239621Z/result.json` |
| C_grounding_review | completed | 19.8 | `logs/C_grounding_review/20261126T145450540920Z/result.json` |
| C_readable_instance_graph | completed | 4.6 | `logs/C_readable_instance_graph/20261126T151741474286Z/result.json` |
| C_visible_context_labels | completed | 5.2 | `logs/C_visible_context_labels/20261126T151855987148Z/result.json` |
| D_heldout_queries | completed | 7.9 | `logs/D_heldout_queries/20261126T151445517371Z/result.json` |
| D_query_logic_check | completed | 0.4 | `logs/D_query_logic_check/20261126T150308703597Z/result.json` |
| D_visible_heldout_displays | completed | 10.7 | `logs/D_visible_heldout_displays/20261126T151639512912Z/result.json` |
| final_validation | completed | 12.2 | `logs/final_validation/20261126T151538089385Z/result.json` |
| final_validation_after_display_selection | completed | 5.8 | `logs/final_validation_after_display_selection/20261126T151901298667Z/result.json` |
| portable_render_final | completed | 4.3 | `logs/portable_render_final/20261126T151907154406Z/result.json` |
| portable_render_validation | completed | 4.4 | `logs/portable_render_validation/20261126T151550348730Z/result.json` |
| result_gallery | completed | 0.4 | `logs/result_gallery/20261126T151554867110Z/result.json` |
| result_gallery_final | completed | 0.5 | `logs/result_gallery_final/20261126T151746103271Z/result.json` |
| world_model_package | completed | 2.1 | `logs/world_model_package/20261126T151418741811Z/result.json` |

## 后续可改进点

优先处理料架的镂空细杆、被遮挡底部及邻近结构混入；进一步检查SAM跨材质的一致性和提示粒度。物料车与冷风机的背面模糊、漂浮高斯部分来自原3DGS，应与分割错误区分。语义关系需要更清楚的局部SoM证据和具有独立节点的真实接触案例；当前几何图受粗M0边界及相对单位影响。语言接口可扩充别名和解析形式，但不应把8类范围内的功能检查夸大为通用语言理解。

最终包：`world_model/`。详细运行命令、断点恢复和查看路径见`README.md`。本次没有改动旧Web、原M0及旧研究模块，也没有重新训练基础3DGS。
