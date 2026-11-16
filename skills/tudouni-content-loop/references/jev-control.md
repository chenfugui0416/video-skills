# Jev 判断与 ego 执行

本项目的 Jev 指 TypeSafe 文本判断模型。它根据页面观测选择下一步，agent 负责调用 ego；网页中的 Gemini 或其他指定模型负责写作。Jev 不看图，不审核视频质量，也不决定稿件事实是否正确。

本 Skill 的 `scripts/jev-writer.mjs` 调用官方 `https://api.typesafe.ai/v1/systemone`，默认 `jev-latest`。本机使用用户本轮指定的私有配置 `~/.config/tudouni-content-loop/jev.json`（0600），只在脚本内读取；支持 `TYPESAFE_API_KEY` 或 `TUDOUNI_JEV_CONFIG`、`JEV_MODEL`。不输出配置正文，不把凭据传入网页、提示词或交付包，不需要恢复已移除的 ego-jev 库。用户给的 console.typesafe.ai/home 是管理控制台，不是模型API。

从当前页面观察以下字段，未知值为 null：`submitted`、`composer_ready`、`model_verified`、`generation_active`、`completion_visible`、`current_response_confirmed`、`response_json_complete`。`blocker` 只能为 null、region_unavailable、login_required、captcha、quota、service_error。提交状态结合本任务操作记录，不能仅看输入框是否空白。不得把整页DOM、私人会话或账号信息传给 Jev。

```bash
node ~/.codex/skills/tudouni-content-loop/scripts/jev-writer.mjs /项目/browser-state-v01.json
```

结果及执行：

| decision | agent 用 ego 做什么 |
|---|---|
| prepare | 根据新鲜快照定位编辑框，填写并回读最小提示词，再单次发送 |
| wait | 在原页观察正文增长与完成信号，不重发 |
| extract | 从当前回答DOM取全文，保存原始response和实际操作receipt，再运行accept |
| blocked | 保留现场；需要用户操作则handOff，报告具体原因 |
| unknown | 补充缺失观察；不能视为prepare或extract |

置信度低于0.85转unknown；地区/登录等明确障碍优先；回答未完成、归属未确认或模型未核对时不能提取。0.85是本地运行参数，不是成功率承诺。Jev返回值从不作为JavaScript、shell或固定坐标执行。

单次API最长20秒，出错只报告脱敏错误码，不自动重试或偷偷换模型。API故障时是否改为当前agent判断，按用户当次任务选择处理。官网不可用不等于Jev不可用；需要分别记录。Jev接入仅增加判断步骤，浏览器会话规则继续遵守[ego写作操作](ego-writer.md)。
