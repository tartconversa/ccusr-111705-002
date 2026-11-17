# 机器人体验预约的跨页占位观察

这是机器人资料的本地演练门户与目录采集器。演练数据仅在环回地址提供，不会操作真实用户、订单或商户。当前 `app.capture.read_catalog` 读取目录；`app.capture.read_detail_entry` 走卡片到详情并接收可选业务选择，`app.domain.interpret_entry` 确认业务身份，`app.records.save_detail_entries` 追加详情入口收据。档期观察由 `app.observe` 承担：经过项目详情、日期选择与预约预览（含模拟临时占位步骤），把候选档期与最终预览状态关联；`app.review.build_difference_list` 输出可追溯差异清单，全程只发 GET 请求、不提交真实预约，未渲染或占位失败记为“未观察”而非售罄，每个项目使用独立浏览器上下文。

站点约定见 `docs/portal.md`；测试时从本地任意空闲端口启动演练站点。安装锁定依赖并准备 Chromium 后：

- `python -m unittest discover -s tests -v`：运行基线浏览器测试。
- `python -m compileall -q app tests`：检查代码。
- `python -m app.site`：启动本地演练站点。
- `python -m app.cli`：另一个终端观察目录输出。
- `python -m app.cli observe [收据.sqlite3]`：运行全项目档期观察，打印差异清单并可选追加观察收据。

两个终端命令用于人工演示，自动测试不依赖固定端口。
