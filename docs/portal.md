# 本地来源行为

机器人目录列出稳定的 `data-key` 和详情路径；详情需由浏览器导航读取，`日期`选择改变当前页面状态，`人数`和`占位预览`是分步出现的可见内容。日期切换期间档期元素暂时复用。详情接口是浏览器页面，不是业务 API；运行时只允许访问环回来源。

`fixtures/portal.json` 提供合成业务资料，不包含真实个人数据。`records.save_catalog` 覆盖同一目录身份；`records.save_detail_entries` 以业务键追加入口访问，不把入口访问等同于资格、授权、可预约或正式提交。测试均只访问本地环回页面。

## 档期观察（不提交真实预约）

`app.observe` 让真实 Chromium 走接待员的核对路径：目录卡片 → 项目详情 → 逐日期选档期 → 逐人数点占位预览，并单独复现“模拟临时占位”步骤，把候选档期与最终预览状态关联成观察行；`app.review.build_difference_list` 据此输出可追溯差异清单。

纪律与对应实现：

- **骨架不是售罄**：`加载中`、`占位核对中`、空文本由 `domain.parse_slot_text` / `parse_preview_text` 返回 `None`，`observe.wait_for_rendered` 轮询到真实文本为止；超时记 `unobserved`，无法识别的真实文本直接报错。状态空间里没有 `sold_out`，未观察与不可预约严格区分。
- **同名元素复用**：日期切换后同一 `#slot-text` 元素被复用，观察器等到渲染完成并校验文本中的日期身份等于所选日期，杜绝读到上一日期的残留名额。
- **返回列表保留筛选**：`open_detail_from_catalog` 发现目标卡片不在文档时重新导航目录后再找，仍缺失才报错。
- **会话隔离**：`observe_portal` 为每个项目创建用后即关的独立浏览器上下文（独立 cookie/存储），项目间不共享页面或会话；每行的请求轨迹只允许出现本项目详情。
- **只浏览不提交**：观察只触发 GET 页面请求；请求监听一旦发现非 GET 的提交式请求立即中止并报错。
- **追加留痕**：`records.save_slot_observations` 向 `slot_observations` 表追加观察收据，每行带 `observation_id`、业务键、来源 URL、页面原文与请求轨迹，差异清单可回溯到具体观察步骤与阶段（`candidate` / `after_hold`）。

