# video-skills 深度参考

SKILL.md 之外的实测技术细节。坑位均来自真机验证；复用前先判断在当前平台版本下是否仍成立。

## §1 X 直发完整技术细节

### JXA 基础操作

macOS 上用 `osascript -l JavaScript` 驱动 Chrome。核心 API：

```javascript
const app = Application("Google Chrome");
const win = app.windows()[N];           // 窗口数组
win.tabs.push(app.Tab({url}));           // 新开标签（自动激活）
const idx = win.activeTabIndex();        // 活动标签 1-based
const tab = win.tabs()[idx - 1];         // 0-based 取标签
win.activeTabIndex = N;                  // 切换标签（1-based）
tab.execute({javascript: "..."});        // 在标签里执行 JS（返回字符串）
tab.close();                             // 关标签
```

注意：`delay(2)` 是函数调用不是语句；模板字符串里嵌套引号要转义。

### 定位窗口与标签

不要假设窗口/标签 index，先扫描：

```javascript
app.windows().forEach((w, wi) => {
  w.tabs().forEach((t, ti) => {
    const u = t.url() || "";
    if (u.includes("x.com")) /* 记录 wi/ti */;
  });
});
```

### 完整发布流程（五步）

1. **开 intent 标签**：`https://x.com/intent/post?text=<encodeURIComponent(全文)>`，URL 一步带入全文，无需模拟打字。记住新标签 1-based index 后立即切回用户视图。
2. **激活等渲染**：后台标签被 Chrome 节流，compose 不出表单。`win.activeTabIndex = myIdx` 激活后轮询（1s × 15 次）等 `[data-testid=tweetTextarea_0]` 出现。
3. **验证就绪**：textarea innerText = 全文；按钮 `[data-testid=tweetButton]` 的 `aria-disabled` = "false"（可能滞留 "true" 但实际可点，以点击后结果为准）。
4. **点击发布**：`btn.click()` 后轮询——成功信号：`[data-testid=toast]` 含 "Your post was sent"；URL 跳回 `x.com/home`。
5. **取链接验证**：时间线 `a[href*="/<handle>/status/"]` 取新帖 id；导航到详情页，`[data-testid=cellInnerDiv]` 含正文且作者正确。最后 close 自己的标签（先验 URL 匹配再关）。

### 坑位清单

| 坑 | 症状 | 处理 |
|---|---|---|
| 后台标签节流 | dialog 存在但 HTML 长度 ≈1201、无 tweetTextarea、按钮列表为空 | 短暂激活标签等初始化 |
| 按钮混淆 | `tweetButtonInline`（禁用）是常驻按钮 | 只点 `tweetButton` |
| 并行操作干扰 | activeTab 被切走、自己开的标签被关闭 | 每次操作前按 URL 重新定位；不缓存 index |
| 空对话框误判 | `dialog:true` 但输入框数量 = 0 | 用 HTML 长度和元素枚举双重确认 |
| 中文界面按钮名 | 发帖按钮不叫 "Post" | 按 data-testid 找，不按文本 |

### 已验证失败通道（别再走）

- **第三方 CLI 写入**：被平台风控拦截（误判非浏览器客户端），读取正常但发帖一律失败。
- **复制 Cookie + 临时隔离 profile**：技术上可行但违反「只用用户主 Chrome」安全原则，弃用。

## §2 视频产线状态回写映射

| 环节 | 命令 | 回写 发布状态.json |
|---|---|---|
| 配音 | `release-flow.mjs <包> tts` | `video.status=配音完成`、`video.voiceMs`（免费） |
| 渲染演练 | `... dryrun` | 不写状态（产物在缓存目录） |
| 真渲染 | `... render --yes` | `video.status=已渲染`、silentPath、renderInfo（**花钱**） |
| 混音 | `... mux` | `video.status=待确认/失败待处理`、finalPath（白片检测在此拦截） |
| 渲染崩溃 | release-flow 兜底 | `video.status=失败待处理`、lastError |
| 成片对账 | 对账脚本 `--apply` | `video.finalPath/source/finalSizeBytes`（幂等只增不改） |

前置条件：生图凭据存 macOS Keychain（记录位置不记录值）；`分镜.json` 是链路唯一人工环节（prompt 出提示词 → 模型产出 → 落盘）。

## §3 微信视频号发布页要点（实测）

- 工作台：`https://channels.weixin.qq.com/platform/post/create`（完整表单）；`post/video` 路由是空的，别用。
- 页面是 **wujie 微前端**：顶层 `document.querySelector("wujie-app").shadowRoot` 才能读到表单 DOM；刚导航完 wujie 未挂载会返回 null，要等。
- **自动上传不可行的原因**：wujie 加载时机不稳 + macOS 系统文件面板（NSOpenPanel）在该页面上反复被推到屏幕外坐标，键事件注入被系统以 `bounds_mismatch` 拒绝。
- 表单字段：视频描述（textarea）、短标题（选填，官方提示有流量加成）、位置（选「不显示位置」）、合集、链接；定时选项默认「不定时」。
- **「包含 AI 生成内容」必须勾选**：《人工智能生成合成内容标识办法》2025-09-01 施行，未标识被平台发现会取消推荐资格——勾选不影响正常流量分发。

## §4 发布状态.json 最小结构

```json
{
  "strategyContext": {"contentPillar": "", "funnelStage": "", "audienceSegment": "", "primaryCta": ""},
  "sourcePlatform": "idea|xiaohongshu|wechatOfficialAccount|x|douyin",
  "generatedAt": "ISO 时间",
  "approvalStatus": "待确认",
  "assetsStatus": "待生成|已就绪|失败待处理",
  "video": {
    "status": "待确认",
    "finalPath": "video/成片.mp4",
    "platforms": {"wechatChannels": {"status": "已发布", "url": "", "publishedAt": ""}}
  },
  "platforms": {
    "x": {"status": "已发布", "url": "", "publishedAt": "", "notes": ""}
  },
  "performance": {}
}
```

红线：`approvalStatus` 只由用户改；`已发布` 只在平台返回成功后写；脚本回写全部增量（只增不改）。

## §5 生图通道（视频与封面素材）

首选本地自建生图通道（凭据存 env 文件，600 权限，值永不进文档）。平台画幅映射：

| size | 比例 | 用途 |
|---|---|---|
| 1280x720 | 16:9 | X 横图 |
| 720x1280 | 9:16 | 抖音 |
| 1792x1024 | 3:2 | 公众号横图 |
| 1024x1792 | 2:3 | 小红书竖图 |
| 1024x1024 | 1:1 | 方图 |

写实风格提示词模板（追加在主体描述后，防止图片模型默认输出动漫风）：

> 真人实拍照片，超写实摄影，皮肤真实纹理与毛孔细节，CCD相机直出质感，闪光灯直射，锐利对焦，真实光影，电影级画质。禁止动漫、禁止插画、禁止绘画、禁止卡通风格。

**重要**：中文长段落、复杂表格和关键数据优先用排版工具（HTML/CSS 渲染）生成，不把大量中文文字交给图片模型直接绘制——文字必然出错。

生图后检查：文字可读性、主体完整性、品牌一致性、裁切安全区、事实一致性、无关元素。

## §6 平台风控与节奏

- X：发帖后有 1 小时编辑窗口；测试帖让用户决定删否。
- 视频号：单日 1–2 条；AI 标识必勾。
- 小红书：图文平台会检测脚本自动发布，正式发布走手动上传交付包。
- 通用：失败不自动重试；发布前 `approvalStatus` 必须是用户确认后的状态。
