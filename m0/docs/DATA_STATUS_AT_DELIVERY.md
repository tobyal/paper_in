# M0 数据状态报告

生成时间：2026-11-25T08:19:40.930594+00:00；数据修订：r6。

本报告反映当前正式工作目录的实际记录。自动测试副本位于 logs/m0_contract_qa_*，其确认标志只验证软件状态转换，不是人工真值。

| 步骤 | 人工完成状态 | 自动检查阻断项 |
|---|---|---|
| 01 | 待人工标注 / 复核 | 3 |
| 02 | 待人工标注 / 复核 | 2 |
| 03 | 待人工标注 / 复核 | 3 |
| 04 | 待人工标注 / 复核 | 1 |
| 05 | 待人工标注 / 复核 | 5 |
| 06 | 待人工标注 / 复核 | 11 |
| 07 | 待人工标注 / 复核 | 0 |

## 实际数据
- 对象：1；人工确认对象：0。
- 建模掩膜：2；留出掩膜：1。
- 可冻结：False；最近冻结版本：无。

## 待处理项
- Step 1 [error] 工业坐标系尚未人工确认。
- Step 1 [error] 请核对 RGB、渲染和相机的对应关系。
- Step 1 [error] 至少定义一个纳入建模的区域。
- Step 2 [warning] 首批建议选择 5–8 个对象；当前可先验证单对象闭环。
- Step 2 [error] obj_8df38955b314 对象身份尚未确认。
- Step 2 [error] obj_8df38955b314 尚未绑定有效建模区域。
- Step 3 [error] obj_8df38955b314 至少需要两个确认的训练视角。
- Step 6 [error] obj_8df38955b314 尚无独立留出视角的确认掩膜。
- Step 4 [error] obj_8df38955b314 视觉描述尚未确认。
- Step 3 [error] obj_8df38955b314/frame_000050 未人工确认。
- Step 3 [error] obj_8df38955b314/frame_000066 未人工确认。
- Step 6 [error] obj_8df38955b314/frame_000057 未人工确认。
- Step 5 [error] near 尚无明确判定规则。
- Step 5 [error] 邻近关系需要距离定义、阈值及单位。
- Step 5 [error] left_of 尚无明确判定规则。
- Step 5 [error] right_of 尚无明确判定规则。
- Step 5 [error] inside_region 尚无明确判定规则。
- Step 6 [error] 独立关系评价至少包含成立与不成立实例。
- Step 6 [error] 尚无独立语义查询。
- Step 6 [error] 缺少 attribute 类型查询。
- Step 6 [error] 缺少 relation 类型查询。
- Step 6 [error] 缺少 multi_condition 类型查询。
- Step 6 [error] 缺少 disambiguation 类型查询。
- Step 6 [error] 缺少 no_match 类型查询。
- Step 6 [error] 缺少 category 类型查询。
- Step 6 [error] 缺少 region 类型查询。

## 数据边界
- priors/ 仅供 M1–M5 建模读取；ground_truth/ 仅供独立评价读取。
- 基础几何、COLMAP、原始划分和 SAM 权重的来源校验保存在 .assets/source_manifest.json。
- 未继承旧 SAM/语言特征/分组/对象定位/关系/地面/区域标注。
- 所有候选描述和掩膜仍需真实人工审核。运行通过不等于标注正确。
