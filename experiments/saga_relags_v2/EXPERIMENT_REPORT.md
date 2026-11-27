# SAGA + ReLaGS 工业世界模型 v2：实际实验报告

本次按照 `docs/USER_REQUEST.md` 完整版本执行。33/33 设备均实际处理；20 个 usable、10 个 partial_usable、3 个 needs_improvement、0 个 failed。30 个精细或局部实例参与常规展示，33 个设备均参与身份及关系查询。无新 SAGA 训练，无几何补造。

审核属于 **Codex 对训练图像、原生3DGS及三向提取结果的视觉检查**，不是独立人工真值。0 个 failed 表示本轮最终没有完全空或完全失去身份的提取结果，并不表示33个完美成功；3个待改进结果明确停用常规精细展示。原始 M0 r29 仍为 draft，没有擅自变更确认状态。

## 1. 输入、冻结与工程保护

- 复用 v1 官方 SAGA iteration_10000、32维亲和特征、尺度门控及K=16平滑结果；原始 1,828,777 个3DGS高斯行号精确对应。关键 SHA256 见 [provenance](evidence/inputs/provenance.json)。
- M0 r29 的33对象、8类别、工业坐标保持不变。+X为右、+Y为前、+Z为上；距离均为SfM相对单位，不能解释为米。
- v1亲和训练含74视角（57真实、17虚拟），新提示允许取306训练图像或其既有完整场景虚拟观测。实际提示去重视角 90；按对象计的视角使用次数：{'in_frozen_affinity_training': 40, 'new_train_split_prompt_view': 63}。这两种统计不能混为新增训练样本数量。
- 44留出图像没有用于提示、门控或阈值。A冻结时间为 `2026-11-26T16:10:06.681395+00:00`；之后只用留出视角生成最终展示。基础3DGS未重新训练，不声称它符合本次新划分的独立重建评测。
- 34178 个既有文件大小及mtime复核无变化，7个关键文件SHA256不变；全部33个输出PLY逐字段等于对应原始高斯子集，最终ID无重复，合计 731,573 个高斯。验证见 [final_checks](evidence/outputs/validation/final_checks.json)。

## 2. A：全33设备与一轮有限改进

原来9个可用实例的Gaussian ID逐项保持完全相同：装配夹具台 02、装配夹具台 03、带黑色工件的夹具台 01、带黑色工件的夹具台 02、物料车 03、立式移动冷风机 01、多层料架 03、立式移动冷风机 03、物料车 01。此前未处理23个及失败料架04重新生成训练视角SAM参考；真实最多3、虚拟最多2，按可见贡献、新增可见候选及方向差异选择，不凑数。新参考采用3×3区域分散安全正提示，通常每图最多7点；有效点受SAM及候选贡献约束。

首轮统一 `(cosine+1)/2 > 0.85` 得到32个非空对象，料架02因掩膜把杆间空洞包入、候选精度门限拒绝全部参考而为空。保留这次初始结果和日志。检查后只对料架02将参考掩膜候选精度门限从0.50放宽至0.40；实际点仍需候选贡献>0.75。frame_000205/207共14点得到14,008个高斯，局部料架身份清楚，判为partial_usable。

料架04的5张初始SAM掩膜都混入相邻灰箱。记录并使用Codex在两张既有训练虚拟图上的10个安全中心料架点（11个提议点中1个贡献不足未用），不是完全自动流程，也不是人工真值。v1为29,926个高斯，v2首轮39,455，修正后25,750；视觉上减少两侧箱体，中央结构仍有缺失，判为partial_usable。具体相机、像素和原因见 [refinement配置](configs/refinement.json) 与 `outputs/A/refinement_prompts/`。

对料架04、蓝箱01/02固定提示比较0.80/0.85/0.90；降低阈值引入漂浮及邻近材料，提高阈值损失箱面和细杆，未见明确净收益。料架04门控±0.1的外观变化很小，继续保留v1尺度估计。没有启动额外训练、候选框扩展、深度尺度新算法或组合参数搜索。诊断阈值图使用已存float16亲和度，边界点可能与正式float32筛选略有差异；它们不是最终实例，不宣称数量即质量。

33对象之间有 13,376 个冲突Gaussian ID。按存储float16亲和度最大值分配，相等时固定M0顺序。料架08失去6479、料架09失去6895、物料车04失去2个，9个原可用对象没有改变。不同门控/提示的分数尚未校准，料架08/09相邻区域的归属仍需独立核查，不能把无重复当作分割正确率。

所有初始、修正、阈值及门控尝试均保留。最终 [33设备图集](docs/GALLERY.md) 每台有训练RGB、同相机完整原生渲染、M0粗裁剪、SAGA斜/侧/顶视与真实三维投影。M0粗裁剪不是真值。

## 3. 按类别与逐设备结果

全局重建状态：{'well_reconstructed': 14, 'partially_reconstructed': 18, 'uncertain': 1}。细杆、镂空结构及背侧缺失常已存在于原始3DGS；同一对象可以重建局部而提取可用。下面的状态分别判断，不能合并成单一成功率。

|类别|数量|可用|局部可用|待改进|重建状态统计|
|---|---:|---:|---:|---:|---|
|物料车|6|5|1|0|{'well_reconstructed': 1, 'partially_reconstructed': 5}|
|装配夹具台|3|3|0|0|{'well_reconstructed': 3}|
|带黑色工件的夹具台|5|5|0|0|{'well_reconstructed': 5}|
|多层料架|9|4|3|2|{'partially_reconstructed': 4, 'well_reconstructed': 4, 'uncertain': 1}|
|蓝色箱组|3|0|2|1|{'partially_reconstructed': 3}|
|立式移动冷风机|3|3|0|0|{'well_reconstructed': 1, 'partially_reconstructed': 2}|
|工作台|2|0|2|0|{'partially_reconstructed': 2}|
|分隔式料架|2|0|2|0|{'partially_reconstructed': 2}|

|设备ID / 图中编号|设备名称|类别|有效真实 / 虚拟|提示点|M0候选|最终高斯|重建状态|提取状态|精细可用|额外优化|主要问题|
|---|---|---|---:|---:|---:|---:|---|---|---|---|---|
|obj_8429bc5f3c33 / O01|装配夹具台 01|装配夹具台|3 / 0|21|28512|20477|well_reconstructed|usable|是|否|底座、立柱及主要夹具得到保留；细线缆和轮缘局部缺失。|
|obj_d058f708eb01 / O02|装配夹具台 02|装配夹具台|2 / 1|9|34150|20186|well_reconstructed|usable|是|否|直接复用v1；长底座和夹具连贯，细线缆仍不完整。|
|obj_09a35ba03c92 / O03|装配夹具台 03|装配夹具台|1 / 1|6|30873|16536|well_reconstructed|usable|是|否|直接复用v1；主要支架保留，局部细杆有孔洞。|
|obj_ad85774e5f18 / O04|带黑色工件的夹具台 01|带黑色工件的夹具台|1 / 1|8|20962|11956|well_reconstructed|usable|是|否|直接复用v1及已记录补点；黑色工件、浅色覆盖物和底座保留。|
|obj_c812ae8b15bd / O05|带黑色工件的夹具台 02|带黑色工件的夹具台|2 / 1|11|23676|17755|well_reconstructed|usable|是|否|直接复用v1及已记录补点；主要设备结构保留，底部细支撑有模糊。|
|obj_485ade540e7d / O06|多层料架 05|多层料架|3 / 2|33|82242|66137|partially_reconstructed|needs_improvement|否|否|架体保留，但M0范围及SAM掩膜同时覆盖前方灰箱/小架；粗框边界、遮挡与提示混入共同影响。常规精细查询停用，保留诊断结果。|
|obj_f9a0e863e32d / O07|物料车 03|物料车|2 / 1|9|28512|27176|well_reconstructed|usable|是|否|直接复用v1；箱体和车架完整，边缘少量原始重建伪影。|
|obj_126125e3a773 / O08|多层料架 02|多层料架|2 / 0|14|18391|14008|partially_reconstructed|partial_usable|是|是|首轮因镂空结构SAM粗贡献精度门槛而无提示。一次放宽参考掩膜检查后提取出主体架和细杆；遮挡侧及底部仍不足。未放宽最终亲和阈值。|
|obj_aad6e7f85a9a / O09|多层料架 08|多层料架|2 / 0|14|99089|71325|well_reconstructed|usable|是|否|大部分层架横杆保留；与料架09有候选重叠，按亲和分配后保持独立，细杆仍有少量漂浮。|
|obj_5bfd32389355 / O10|多层料架 04|多层料架|0 / 2|10|48158|25750|partially_reconstructed|partial_usable|是|是|用10个经Codex视觉检查的中央料架点击替换受污染提示，明显减少两侧独立灰箱。保留中央上部和部分层架，底部仍不完整；阈值和门控有限比较无明确收益。|
|obj_141f3e5dbe3a / O11|蓝色箱组 01|蓝色箱组|3 / 0|19|40443|21501|partially_reconstructed|needs_improvement|否|是|只保留部分蓝箱表面，前方小架仍混入；原始重建、遮挡及跨材质亲和筛选共同影响。0.80/0.90比较未明显改善，常规精细查询停用。|
|obj_3c963764ddb5 / O12|蓝色箱组 02|蓝色箱组|2 / 0|13|60391|27191|partially_reconstructed|partial_usable|是|是|保留箱组的可见上表面和局部立面；部分原始箱体已不完整，另有亲和筛选孔洞。有限阈值比较无明确收益，查询明确显示局部实例。|
|obj_e57b3a886c2d / O13|立式移动冷风机 02|立式移动冷风机|3 / 0|18|11511|10952|well_reconstructed|usable|是|否|冷风机机身及格栅清晰，底部脚轮在原始重建中模糊。|
|obj_04c477562e49 / O14|立式移动冷风机 01|立式移动冷风机|2 / 1|9|10371|9442|partially_reconstructed|usable|是|否|直接复用v1；已有机身结构提取有效，背面彩色伪影来自原始3DGS，不能解释为补全失败。|
|obj_2e1a6e5960f5 / O15|工作台 01|工作台|3 / 0|21|15234|13214|partially_reconstructed|partial_usable|是|否|台面与主要正面结构保留；原生3DGS下部、背侧本就模糊或缺失，少量漂浮仍在。|
|obj_8528f4bf8a3d / O16|带黑色工件的夹具台 03|带黑色工件的夹具台|3 / 0|21|26263|15546|well_reconstructed|usable|是|否|底座与黑色工件主体保留；部分轮脚、细线缆未完全选择。|
|obj_8e79bd39b8b9 / O17|带黑色工件的夹具台 04|带黑色工件的夹具台|2 / 2|25|30218|22085|well_reconstructed|usable|是|否|设备主体和细长底座连贯；局部反光、细杆仍有孔洞。|
|obj_087984e7c374 / O18|带黑色工件的夹具台 05|带黑色工件的夹具台|3 / 0|21|31925|24692|well_reconstructed|usable|是|否|工件及底座整体提取有效；原始重建底部有少量模糊残影。|
|obj_b7e0494ce9dd / O19|多层料架 01|多层料架|2 / 0|13|16204|14169|partially_reconstructed|partial_usable|是|否|主要层架和可见物料保留；镂空背侧与细杆在原始重建和提取中均存在不足。|
|obj_b8542dc54ed2 / O20|多层料架 03|多层料架|1 / 1|6|30924|25553|well_reconstructed|usable|是|否|直接复用v1；层架主体保留，局部细杆及边界仍有漂浮。|
|obj_7463bab859d0 / O21|蓝色箱组 03|蓝色箱组|2 / 0|13|14336|9278|partially_reconstructed|partial_usable|是|否|原始高斯主要表达箱组的部分可见面；提取保留这些结构，不宣称获得完整箱体。|
|obj_c57876bf22ca / O22|立式移动冷风机 03|立式移动冷风机|2 / 1|9|7431|7093|partially_reconstructed|usable|是|否|直接复用v1；机身格栅有效，原始轮脚与下部模糊。|
|obj_06d9693cfb0a / O23|多层料架 06|多层料架|3 / 0|19|10056|9131|well_reconstructed|usable|是|否|窄架及蓝箱主体保留，底部有少量地面/漂浮残留。|
|obj_c7c9293c6c6d / O24|分隔式料架 02|分隔式料架|3 / 2|34|49463|42391|partially_reconstructed|partial_usable|是|否|分隔式架体轮廓与正面槽位可辨；背面和部分内槽原始重建不足，不能要求恢复不存在的面。|
|obj_5746b7e7d040 / O25|分隔式料架 01|分隔式料架|3 / 1|26|54146|47337|partially_reconstructed|partial_usable|是|否|两段相连架体和顶部保留；深色槽内及背侧不完整，保留原始局部实例。|
|obj_933bd7d6e703 / O26|多层料架 09|多层料架|3 / 2|34|30916|21457|well_reconstructed|usable|是|否|架体、平台及黑色物料保留；与料架08重叠部分经统一归属处理，仍可区分两台设备。|
|obj_4fd05384c476 / O27|物料车 06|物料车|3 / 1|26|25029|23434|partially_reconstructed|usable|是|否|车体框架及已重建箱面保留；遮挡背面在原始场景中存在模糊。|
|obj_dee5bef52687 / O28|多层料架 07|多层料架|3 / 1|24|36480|30386|uncertain|needs_improvement|否|否|粗框内包含台面、立式面板、小架及邻近结构，现有视角难以可靠核定M0设备边界；提取仍混杂。保留身份和诊断，不作为常规精细实例。|
|obj_3efbeb5e8179 / O29|物料车 05|物料车|3 / 0|20|24981|21684|partially_reconstructed|usable|是|否|主要车架及箱体范围保留，布罩和背侧原始重建欠完整。|
|obj_7047e5f33259 / O30|物料车 04|物料车|3 / 0|16|14618|12071|partially_reconstructed|partial_usable|是|否|原生场景中只有展开箱面及底部局部结构，提取保留该实际形态；不补造不可见侧面。|
|obj_df0a6cc33263 / O31|工作台 02|工作台|3 / 2|35|19881|14362|partially_reconstructed|partial_usable|是|否|已有面板和台面可辨，腿部、背面缺失较多；原始欠重建与亲和筛选共同影响，查询显示局部结果。|
|obj_c0162cd69680 / O32|物料车 02|物料车|3 / 2|35|15421|10889|partially_reconstructed|usable|是|否|箱体和布罩主体保留；原始视角截断、背面模糊及边缘漂浮仍可见。|
|obj_57b0f30bdd9e / O33|物料车 01|物料车|1 / 1|6|7887|6409|partially_reconstructed|usable|是|否|直接复用v1；箱体及蓝色内部主体保留，顶部和背侧仍有原始漂浮。|

## 4. B：类别共享语义

保留8类、512维CLIP文本/视觉原型、中英文名称及别名。对原有44张M0框裁剪作受控比较；其中26张来自usable设备，使用A的完整场景真实贡献图把背景保留30%并向中灰弱化，其他18张保持原裁剪。保存原图、软背景图、贡献图和两套特征。

通过与D完全相同的 `WorldModel.query()` 验证：16个名称/别名、8个未列入别名的合理英文描述、7个目录外表达，共31项。原始与软背景均31/31满足预期，未体现额外收益，因此保留v1原型。最终解析器再次验证31项，并把类别特征矩阵行序反转后验证ID映射，均通过。这是手写功能检查，不是开放词汇准确率。

英文描述使用0.8文本+0.2视觉相似度、最低0.20、首二分差0.015，并与少量目录外概念文本竞争，以避免把叉车/机器人/人等强行归入8类。该拒识方式是有限工程规则，仍可能拒绝合理长描述或误接纳未覆盖概念。中文依赖已知别名，不承诺通用中文语义推理。

## 5. C：完整设备关系图

保留33节点、2020有向几何边：{'behind': 430, 'near': 130, 'left_of': 383, 'right_of': 383, 'nearest_to': 264, 'in_front_of': 430}。独立从M0角点和中心重新计算期望集合，与v1几何边完全一致；左右/前后互逆、near对称、节点ID、自排除、各类别nearest全部通过。near继续使用AABB间隔<0.35，方向间隔0.02，nearest按完整M0中心、并列容差1e-6。

节点补充独立重建/提取状态、工业位置、可用性、ID/PLY路径、质量记录及仅作辅助的精细几何范围。没有用局部实例中心替换M0关系几何。SoM不再运行，不人为添加support/contain等边。独立实例彩色图含30个精细/局部结果；3个待改进对象用明确的M0位置标签保留。完整原生场景图保留其他设备和遮挡。

## 6. D：先定位设备，再检查精细实例

修复v1把实例可用性提前用于候选过滤的问题。类别/身份/关系首先查全部33节点；之后分别返回renderable与unavailable设备。多个同类参照对象采用结果并集；未知身份、参照缺失、不支持关系、关系空结果有独立状态。查询不运行SAM或SAGA。

真实回归例：`距离装配夹具台 01最近的蓝色箱组` 返回蓝色箱组01。其M0中心距离为2.32917，另外两组分别6.43633、6.71078（相对单位）；虽精细结果不可用，仍返回正确ID与M0位置，未返回次近箱组。见 [回归证据](evidence/outputs/D/nearest_regressions.json)。

实际查询检查 64/64 通过，其中真实场景功能案例 62、显式合成边界案例 2。合成仅验证全不可用状态与并列最近，不当作工业实验数据。另完成18组查询、各2个留出展示视角，包括8类别、最近/左右/前后/near、局部设备、不可用设备和空关系。红色为冻结Gaussian ID在完整场景中的真实贡献>0.5；黄色框仅M0位置，不是SAM或精细实例。

展示相机按冻结结果的可见性选择，不能当作公平固定测试集。另保存固定列表位置0/14/28/43的4个留出相机及33设备，供后续独立标注；当前没有真值掩膜或IoU。世界模型从 `/tmp` 独立运行类别及关系查询已通过。精细实例索引属于本包；大型CLIP、原生PLY和实例PLY用明确只读引用，搬移作业须按README处理这些依赖。

## 7. 需要明确保留的问题

- 多层料架 05、蓝色箱组 01、多层料架 07：相邻材料混入、设备边界含糊或跨材质特征选择不足，保留真实PLY和诊断图，精细常规展示关闭。
- 料架02/04、蓝箱02/03、分隔架及工作台等仍有局部缺失。部分属于原重建遮挡/反光，部分与提示、亲和选择混合影响；无法仅凭现有数据精确分解。
- M0为draft先验，框/类别/设备边界没有独立人工认证；部分“料架”框还包围邻近小架或箱组。
- 互斥归属是工程一致性保证，跨门控亲和度不能当校准概率；输出点数、保留比例及非空查询不构成准确率。
- 原生3DGS的未重建背侧/底部不能通过实例分割恢复。没有几何补全或新图像生成。

## 8. 对12项交付问题的回答

1. 全33个均处理，首轮失败及修正结果均存；最终20可用、10局部可用、3待改进。
2. 各类及每台重建/提取状态分别列于第3节。
3. 直接复用9台，见第2节及 `outputs/A/v1_comparison.json`，ID精确相同。
4. 料架02补充有效参考后从空结果恢复，料架04经已记录视觉点减少相邻箱体。
5. 0.80/0.90阈值、门控±0.1和CLIP软背景原型没有明确收益，未替换基线设置。
6. 原重建薄杆断裂、背面空缺、金属/透明区域漂浮在完整原生渲染中已可见，逐对象记录不强行归因。
7. 料架05/07及蓝箱01仍困难；局部可用对象也保留问题说明，没有继续无限优化。
8. 全2020几何边正确保留并独立复算，未因实例缺失删节点。
9. 最近关系候选范围冲突已修复，真实不可用目标回归及合成边界通过。
10. 纯别名/关系查询仅Python+NumPy，世界模型可从其他工作目录独立运行；描述CLIP及渲染有明确大型只读依赖。
11. 33设备M0与SAGA三向对比、v1/v2十台对比、有限参数诊断、完整实例图与关系缩减案例可作为后续论文实验基础。
12. 分割质量、关系正确性、检索泛化及优于ReLaGS的结论仍需独立人工真值、公平固定视角与外部对照；本次没有宣称这些指标。

## 9. 运行证据与资源

所有实际命令、源代码快照、stdout/stderr、退出码、耗时和5秒GPU采样保存在 `logs/<stage>/<UTC timestamp>/`。完整清单见 [runtime](evidence/outputs/validation/runtime_complete.json)。GPU采样属于指定整卡（可能含其他进程），不是本任务独占峰值；短运行可能漏采峰值。总运行秒数不包含检查、编程及视觉审核时间。

|运行|退出状态|秒|日志|
|---|---|---:|---|
|A_bounded_comparison|completed|5.82|[logs/A_bounded_comparison/20261126T160742959753Z/run.log](evidence/logs/A_bounded_comparison/20261126T160742959753Z/run.log)|
|A_freeze|completed|0.55|[logs/A_freeze/20261126T161006085400Z/run.log](evidence/logs/A_freeze/20261126T161006085400Z/run.log)|
|A_initial_extraction|completed|40.89|[logs/A_initial_extraction/20261126T160043831230Z/run.log](evidence/logs/A_initial_extraction/20261126T160043831230Z/run.log)|
|A_initial_inspection|completed|14.22|[logs/A_initial_inspection/20261126T160158024111Z/run.log](evidence/logs/A_initial_inspection/20261126T160158024111Z/run.log)|
|A_prompt_refinement|completed|0.48|[logs/A_prompt_refinement/20261126T160539430906Z/run.log](evidence/logs/A_prompt_refinement/20261126T160539430906Z/run.log)|
|A_references|completed|79.15|[logs/A_references/20261126T155910538410Z/run.log](evidence/logs/A_references/20261126T155910538410Z/run.log)|
|A_refined_extraction|completed|7.77|[logs/A_refined_extraction/20261126T160539978478Z/run.log](evidence/logs/A_refined_extraction/20261126T160539978478Z/run.log)|
|A_refined_inspection|completed|16.40|[logs/A_refined_inspection/20261126T160606598991Z/run.log](evidence/logs/A_refined_inspection/20261126T160606598991Z/run.log)|
|A_scale_lower|completed|4.99|[logs/A_scale_lower/20261126T160623075262Z/run.log](evidence/logs/A_scale_lower/20261126T160623075262Z/run.log)|
|A_scale_upper|completed|4.99|[logs/A_scale_upper/20261126T160628137499Z/run.log](evidence/logs/A_scale_upper/20261126T160628137499Z/run.log)|
|BC_world_model|completed|13.65|[logs/BC_world_model/20261126T161433568461Z/run.log](evidence/logs/BC_world_model/20261126T161433568461Z/run.log)|
|D_regression|completed|0.54|[logs/D_regression/20261126T161602120962Z/run.log](evidence/logs/D_regression/20261126T161602120962Z/run.log)|
|compact_gallery|completed|1.05|[logs/compact_gallery/20261126T162417528900Z/run.log](evidence/logs/compact_gallery/20261126T162417528900Z/run.log)|
|final_validation|completed|8.72|[logs/final_validation/20261126T161951113533Z/run.log](evidence/logs/final_validation/20261126T161951113533Z/run.log)|
|final_visualizations|completed|26.12|[logs/final_visualizations/20261126T161752108303Z/run.log](evidence/logs/final_visualizations/20261126T161752108303Z/run.log)|
|initialize|completed|3.21|[logs/initialize/20261126T155752955562Z/run.log](evidence/logs/initialize/20261126T155752955562Z/run.log)|
