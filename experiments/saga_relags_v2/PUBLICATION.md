# v2 仓库归档范围

本目录从服务器完整实验只读复制，归档v2代码、配置、README、实验报告、修改报告、19张关键结果图及轻量验证证据。`evidence/`按服务器相对路径保存JSON与执行记录。报告中的点击链接已指向这些归档副本；代码块中的路径仍指服务器完整实验。

没有上传原始RGB数据集、M0数据库、模型权重、检查点、PLY、Gaussian索引、亲和特征、深度/贡献数组、环境或压缩中间包。Git克隆不是完整数据发行版，恢复运行仍需README中列出的只读数据和v1环境/检查点。

代码使用同仓库已发布的m0与industrial_world_model接口，以及v1固定SAGA/SAM源码和适配。上游来源/许可参见 [v1固定版本](../saga_relags_v1/UPSTREAM.lock.json)、[v1归档说明](../saga_relags_v1/PUBLICATION.md) 和 [许可证](../saga_relags_v1/licenses/)。没有将上游或工业数据重新授权为其他许可证。

33台设备的结果包括20 usable、10 partial_usable、3 needs_improvement。Codex视觉审核、功能回归和几何一致性不等于独立人工真值准确率。3台待改进结果保留，未隐藏。

- [运行说明](README.md)
- [完整实验报告](EXPERIMENT_REPORT.md)
- [相对v1修改记录](MODIFICATION_REPORT.md)
- [33台设备及查询图集](docs/GALLERY.md)
- [实际证据](evidence/)

`PUBLICATION_MANIFEST.json`记录每个服务器来源文件的原始与发布哈希。仅文档导航作发布适配；算法代码逐字节一致。原v1、M0、基线和本次服务器实验均不修改。
