# 图表索引

|编号|论文图名|实验|文件|原始数据|脚本|
|---|---|---|---|---|---|
|F04|工业场景数据及设备空间先验|Dataset|[PNG](figures/F04_dataset/F04_dataset.png) / [SVG](figures/F04_dataset/F04_dataset.svg)|[来源](figures/F04_dataset/sources.json)|[plot_figures.py](scripts/plot_figures.py)|
|F05|空间关系引导工业实例检索的外部对比|E01_external_comparison|[PNG](figures/F05_external_comparison/F05_external_comparison.png) / [SVG](figures/F05_external_comparison/F05_external_comparison.svg)|[来源](figures/F05_external_comparison/sources.json)|[plot_figures.py](scripts/plot_figures.py)|
|F06|工业先验引导的三维关系实体构建|E03|[PNG](figures/F06_entity_construction/F06_entity_construction.png) / [SVG](figures/F06_entity_construction/F06_entity_construction.svg)|[来源](figures/F06_entity_construction/sources.json)|[plot_figures.py](scripts/plot_figures.py)|
|F07|工业空间关系表达与关系约束检索|E04|[PNG](figures/F07_relation_retrieval/F07_relation_retrieval.png) / [SVG](figures/F07_relation_retrieval/F07_relation_retrieval.svg)|[来源](figures/F07_relation_retrieval/sources.json)|[plot_figures.py](scripts/plot_figures.py)|
|F08|精细实体和空间关系约束的消融结果|E02_ablation|[PNG](figures/F08_ablation/F08_ablation.png) / [SVG](figures/F08_ablation/F08_ablation.svg)|[来源](figures/F08_ablation/sources.json)|[plot_figures.py](scripts/plot_figures.py)|
|F09|多视角关系检索及工业应用展示|E05|[PNG](figures/F09_multiview_application/F09_multiview_application.png) / [SVG](figures/F09_multiview_application/F09_multiview_application.svg)|[来源](figures/F09_multiview_application/sources.json)|[plot_figures.py](scripts/plot_figures.py)|
|T01|T01_external|E01|[表格](tables/T01_external.md) / CSV / TSV / LaTeX|E01 原始JSON与逐视角指标|[publish.py](scripts/publish.py)|
|T02|T02_relations|E01|[表格](tables/T02_relations.md) / CSV / TSV / LaTeX|E01 原始JSON与逐视角指标|[publish.py](scripts/publish.py)|
|T03|T03_ablation|E02|[表格](tables/T03_ablation.md) / CSV / TSV / LaTeX|E02 原始JSON与逐视角指标|[publish.py](scripts/publish.py)|
|T04|T04_efficiency|E06|[表格](tables/T04_efficiency.md) / CSV / TSV / LaTeX|E06 原始JSON与逐视角指标|[publish.py](scripts/publish.py)|

F01—F03仅导出真实素材，见 [manifest](method_figure_assets/manifest.json)。大型数组及模型保留服务器；图像来源路径为权威远程绝对路径。

<!-- DATA_ANALYSIS_F10_F12_START -->
## F10—F12 数据分析补充

|编号|内容|实验|文件|数据与来源|
|---|---|---|---|---|
|F10|不同方法的空间关系引导实例检索性能分布|E01_external_comparison|[PNG](figures/F10_query_performance/F10_query_performance.png) · [SVG](figures/F10_query_performance/F10_query_performance.svg) · [PDF](figures/F10_query_performance/F10_query_performance.pdf)|[数据](figures/F10_query_performance/) · [来源](figures/F10_query_performance/sources.json)|
|F11|精细三维实体表达与空间关系约束的贡献分析|E02_ablation|[PNG](figures/F11_mechanism_contribution/F11_mechanism_contribution.png) · [SVG](figures/F11_mechanism_contribution/F11_mechanism_contribution.svg) · [PDF](figures/F11_mechanism_contribution/F11_mechanism_contribution.pdf)|[数据](figures/F11_mechanism_contribution/) · [来源](figures/F11_mechanism_contribution/sources.json)|
|F12|空间关系约束下的工业设备候选筛选分析|E04_relation_retrieval|[PNG](figures/F12_candidate_reduction/F12_candidate_reduction.png) · [SVG](figures/F12_candidate_reduction/F12_candidate_reduction.svg) · [PDF](figures/F12_candidate_reduction/F12_candidate_reduction.pdf)|[数据](figures/F12_candidate_reduction/) · [来源](figures/F12_candidate_reduction/sources.json)|

绘图脚本：[plot_data_analysis.py](scripts/plot_data_analysis.py)。
<!-- DATA_ANALYSIS_F10_F12_END -->
