---
name: video-skills
description: 自媒体内容生产与多平台发布完整链路。从灵感建发布包、四平台稿生成、手绘动画视频产线（TTS→渲染→混音），到 X 自动直发、微信公众号 HTML 交付、视频号/小红书手动上传，再到发布状态回填与归档。Use when 用户提到 发布内容、同步发行、出视频、发X、发推文、发视频号、发公众号、发小红书、自媒体发布、发布包、成片，或执行内容分发任务。
---

# video-skills：内容生产与多平台发布链路

适配任意工作区目录（下称工作区）。建议规则层（账号、路径、平台政策定案）放在工作区根目录的 `AGENTS.md`，机器配置放 `同步发布配置.json`，单篇事实源放发布包 `原文.md`。本 skill 是操作方法层，与工作区文件冲突时以工作区文件为准。

## 0. 一句话链路

> 灵感 → 建发布包 → 原文.md（唯一事实源）→ 四平台稿+素材 →（按需）视频产线 → 统一确认 → 按通道发布 → 回填 发布状态.json / 发布总表.md → 四平台完成 → 归档

## 1. 死规矩（违反即事故，先读这个）

1. **绝不杀用户的 Chrome**：不 `pkill`/`kill`/`TaskStop` 用户 Chrome 的任何进程，无论端口冲突还是"看起来像残留"。端口问题只读排查、如实报告、等指示。
2. **浏览器只驱动用户已登录的主 Chrome**：不复制 Cookie、不建隔离 profile、不另起实例。方法见 §4（JXA）。
3. **发布是向外不可逆动作**：必须用户明确授权；漏传排期参数 = 报错，不是静默发布。
4. **`approvalStatus` 只能由用户改**；只有平台返回成功才写 `已发布` + url + publishedAt。
5. **风控红线**：单账号单平台每天 1–2 条，不并发，失败不自动重试。
6. 探测截图和临时文件用完即删；记录里永不写 API Key/Cookie/Token 正文。

## 2. 发布通道表

| 平台 | 方式 | 状态 |
|---|---|---|
| X | **自动直发**（§4 JXA 方法） | ✅ 实测成功 |
| 微信公众号 | **HTML 源码交付**（`微信公众号.html`，用户插件导入） | ✅ 闭环 |
| 微信视频号 | **手动上传**（成片 + 发布要素清单，§6） | ✅ 实测走通 |
| 小红书 图文 | **手动交付包**（`图片/`+`文案/`） | ✅ 闭环 |
| 小红书 视频 | **手动上传** | 规则已定 |
| 抖音 | CDP 驱动已登录浏览器 | ⚠️ 待连接 |

## 3. 标准发布包与建包

包结构（`内容库/待发布/YYYY-MM-DD-标题/`）：`原文.md`（事实源）· `小红书.md` · `微信公众号.html` · `X.md` · `抖音.md` · `配图方案.md` · `配图提示词/` · `imgs/` · `video/成片.mp4` · `统一确认单.md` · `发布状态.json`。

生成阶段铁律：**首发平台不缩减范围，四平台稿必须全出**；抖音图文文案直接复用 `X.md` 主帖+串文，只做 9:16 适配不重写。

各平台适配要点：

- **小红书**：标题 = 人群 + 场景 + 数字/痛点钩子；正文 = 问题引入 → 3~5 条可执行干货 → 案例 → 收藏理由 → 评论/私信引导；首图 3:4，每图一个重点。
- **X**：主帖首句直接给结论/冲突/数字；超长拆串文，一条一个观点；默认沿用原文语言。
- **公众号**：扩展为完整长文（3~5 章节）；见 §7 HTML 规范。
- **抖音**：9:16 图文卡片，顺序 = 问题 → 证据/截图 → 方法 → 结果 → 行动引导。

## 4. X 自动直发（核心方法）

用 JXA 驱动用户正在运行的 Chrome，全程不碰用户标签：

```bash
osascript -l JavaScript -e '
const app = Application("Google Chrome");
const win = app.windows()[<含 x.com 的窗口>];   // 先扫描 windows() 定位
const restore = win.activeTabIndex();
const url = "https://x.com/intent/post?text=" + encodeURIComponent("全文");
win.tabs.push(app.Tab({url}));            // 新标签自动激活
const myIdx = win.activeTabIndex();       // 记住我的标签（1-based）
win.activeTabIndex = restore;             // 立即切回用户视图
'
```

关键坑位（全部实测验证）：

- **后台标签被 Chrome 节流**：compose 表单不渲染（`[role=dialog]` 存在但内部空壳）。必须 `win.activeTabIndex = myIdx` 短暂激活等表单初始化。
- **就绪信号**：`[data-testid=tweetTextarea_0]` 的 innerText = 全文。
- **发帖按钮**：点 `[data-testid=tweetButton]`。**别点** `tweetButtonInline`——那是常驻侧栏的禁用按钮。
- **成功判定**：`[data-testid=toast]` 出现 "Your post was sent" + URL 跳回 `x.com/home`。
- **取帖子链接**：从时间线 `a[href*="/<handle>/status/"]` 提取；详情页 `[data-testid=cellInnerDiv]` 含正文做二次验证。
- **并行干扰**：用户/其他 agent 会切走 activeTab 甚至关掉你开的标签——每次执行前重新按 URL 定位自己的标签，不缓存 index。
- **收尾**：只 close 自己开的标签（先验 URL 再关）。

## 5. 视频产线

命令阶梯（免费步骤通过才允许花钱）：

```bash
node release-flow.mjs "包名" plan         # 盘点+建议下一步（免费，随时跑）
node release-flow.mjs "包名" prompt       # 出分镜提示词（模型产出分镜.json）
node release-flow.mjs "包名" tts          # 配音+逐字时间轴（免费）
node release-flow.mjs "包名" dryrun       # 渲染工程演练（免费）
node release-flow.mjs "包名" render --yes # 真渲染（花钱！必须用户点头）
node release-flow.mjs "包名" mux          # 混音+白片校验 → video.status=待确认
```

规格：720×960、35–45 秒、7–9 场景、必须带音轨。产线细节和状态回写映射见 [reference.md](reference.md) §2。

## 6. 手动上传平台交付（视频号 / 小红书视频）

交付包提供：`video/成片.mp4` + 发布要素清单，用户手动发布后回填状态。

**视频号发布要素**（实测）：上传成片 → 标题 → 简介（正文+CTA+话题 2–4 个）→ 短标题（填钩子，如反常识首句）→ **「包含 AI 生成内容」必勾**（2025-09-01 起国标要求，未标取消推荐资格，勾选不影响正常流量）→ 位置选「不显示位置」→ 不定时 → 发表。

## 7. 微信公众号 HTML 交付

交付物固定为发布包根目录 `微信公众号.html`：UTF-8 完整文档、行内 CSS 为主、`imgs/` 相对路径、每图有 alt、引用带查询日期、本地双击可开且手机宽度无横向滚动。不包含 Markdown 残留、脚本、占位词。默认任务到 HTML 交付为止，不自动发布。

## 8. 状态回写

- 状态词：`草稿` `待连接` `待生成` `待确认` `已发布` `失败待处理`
- 发布成功 → 更新发布包 `发布状态.json`（该平台 `status/url/publishedAt`）+ 工作区 `发布总表.md`
- 手动发布平台：等用户告知成功后回填
- 四平台全 `已发布` → 发布包移入 `内容库/已发布/`
- 数据复盘记 `performance`；阶段切换要证据（收藏/有效评论/私信/合格需求），不按发布天数自动推进

## 深入参考

平台技术坑位、JXA 完整代码、发布状态 schema、视频号页面细节：[reference.md](reference.md)
