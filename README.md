# 土豆泥 AI 视频工作流

为“土豆泥今天AI了吗”维护可复用的写作、音频驱动制片与草稿上传技能。

当前流程：相关热点/爆款研究 → ego 内 Gemini 第4代写口播 → Codex 审核与返工 → 全文豆包配音和真实对齐 → 分镜生图包 → 分层生图 → 代表画面与动效样片 → HyperFrames 全片、BGM 和字幕 → ego 麦田插件上传并核验草稿。

## 技能

| 技能 | 职责 |
| --- | --- |
| [tudouni-content-loop](skills/tudouni-content-loop/SKILL.md) | 选题证据、Gemini 写作交接、Codex 审核返工与冻结 |
| [tudouni-ai-video](skills/tudouni-ai-video/SKILL.md) | 既有 FUGui、豆包全文配音、真实时间轴、生图包与 HyperFrames 制片 |
| [tudouni-maitian-publisher](skills/tudouni-maitian-publisher/SKILL.md) | 复用既有成片交接，在 ego 内操作麦田插件、逐平台保存并核验草稿 |

将所需技能目录放入 `${CODEX_HOME:-$HOME/.codex}/skills/`。依赖按技能说明核实，不能通过复制本仓库假称浏览器、配音或平台已经可用。本仓库不包含凭据、个人账号、视频素材或完整第三方插件。

## 使用约定

- `原文.md` 是事实源；热门案例只供研究，不洗稿、不编造数据。Gemini 负责表达，Codex 对事实、原意、口播和画面兑现逐版审核，未通过不能进配音。
- Gemini 型号以当次 ego 页面菜单为准。2026-11-16 现场看到的写作选项是 `4 Hydrogen`；后续需重查，不把界面快照当官方能力结论。
- 配音仍用既有豆包音色，全文一次合成后真实对齐。仅改画面复用有效配音；正文变化重配音与对齐。原角色、视频风格和 HyperFrames 保留。
- 生图包明确角色参考、风格、提示词、资产来源与所需图层；先检查代表静帧和动效样片，再扩全片。技术检测不能替代听验或用户视觉认可。
- 浏览器只用 ego lite。麦田插件是[用户指定的独立项目](https://github.com/CzzzzzzJ/mdldm-maitian-publisher)，本仓库保存基线版本的适配补丁和转换器，保留上游 Apache-2.0 来源与许可。
- 当前抖音、小红书只上传并保存草稿，不发布、不排期。同一作品只选一个上传执行器，避免与既有 Qoder 交接重复上传。其他平台能力不构成授权。

## 验证

```bash
python3 skills/tudouni-content-loop/scripts/test_editorial.py
node --test skills/tudouni-content-loop/scripts/test_jev_writer.mjs
python3 skills/tudouni-maitian-publisher/scripts/test_prepare_publish.py
```

编辑器检查的是格式、哈希和审核证据；事实与模型页面观测由实际执行者核对。发布转换器只生成本地文件，不执行上传。实际运行记录放项目私有制作记录，不能把离线测试写成平台已核验。

旧版已在本地 Git 基线与离线 bundle 保留；根目录旧自动发布说明由当前技能入口取代，历史案例不作为当前默认流程。
