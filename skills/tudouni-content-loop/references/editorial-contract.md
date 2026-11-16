# 编辑交接字段

packet 使用 UTF-8 JSON。源文件 source_path 为本地绝对路径；source_sha256 是该文件原始字节的 SHA256。脚本验证源文件当前哈希后才导出或接收。

必需字段：

```json
{
  "task_id": "TD-example-20261008",
  "revision": 1,
  "source_path": "/绝对路径/原文.md",
  "source_sha256": "源文件SHA256",
  "writer": {"provider": "gemini_web", "requested_model": "本次明确要求的菜单模型标签"},
  "brief": {
    "topic": "本条题目",
    "audience": "当前已选受众",
    "goal": "观众学会的一项任务",
    "mode": "polish",
    "draft": "原稿或充分的观点提纲",
    "facts": [{"id": "F01", "statement": "可说的事实", "boundary": "必须保留的条件", "evidence": "可公开来源说明"}],
    "required_fact_ids": ["F01"],
    "locked_quotes": [],
    "style": "自然、直接；不添加经历和收益",
    "visual_evidence": "能展示的证据和示意边界",
    "min_chars": 80,
    "max_chars": 300,
    "primary_cta": "本条唯一行动引导；无需口播则明确说明"
  }
}
```

示例字数不是默认限制；按任务填写。provider=`local` 表示当前模型写稿；其他 provider 需要网页操作 receipt。只有 brief、任务编号与响应契约进入外发提示词，本地路径和账号资料不外发。brief 中也不得填入本地敏感路径或私人资料。

写作者返回一个完整 JSON 对象：task_id、revision、completion、script、used_fact_ids、unresolved、change_notes。complete 需要非空正文和空 unresolved；needs_input 返回具体缺口，不能进入制片。允许整个回答只有一层 JSON 代码围栏，不允许围栏外另有一稿或说明；JSON 重复键、截断、未知字段、错任务和错版本均拒绝。

## 网页 receipt

由实际操作 agent 记录，不由写作模型声称：

```json
{
  "task_id": "TD-example-20261008",
  "revision": 1,
  "provider": "gemini_web",
  "requested_model": "本次目标",
  "observed_model": "页面模型菜单实际标签",
  "model_verified": true,
  "conversation_url": "https://gemini.google.com/app/实际会话",
  "submitted_at": "带时区的ISO时间",
  "completed_at": "带时区的ISO时间",
  "response_complete": true
}
```

不存账户名称、邮箱、Cookie 或 Token。requested_model 必须与 packet 一致；model_verified 只在实际菜单与生成后状态支持时记 true。脚本只核对记录完整一致，不能独立证明网页观测真实。

## 审核与冻结

accept 生成 candidate.txt 和 accepted.json。审核者读取它们以及原文，写 review：

```json
{
  "task_id": "TD-example-20261008",
  "revision": 1,
  "packet_sha256": "accepted中的值",
  "script_sha256": "accepted中的值",
  "checks": {"facts": "pass", "intent": "pass", "speakable": "pass", "visual_support": "pass"},
  "evidence_notes": ["具体核对过的事实与画面依据"],
  "selection": {"allowed_to_produce": true, "basis": "当前用户已授权制作试片；或此前已选定该稿"}
}
```

不自动把检查项设为 pass；对具体问题回到写作者修订。正文哈希为 `sha256(text.strip().encode('utf-8'))`，与现有土豆泥校验器一致。

freeze 输出 script.txt、handoff.json。handoff 引用源文件、packet、accepted 记录、原始 response、receipt、review 和冻结稿的路径及哈希；verify 重新核对相关内容及审核结论。文件被改动时不自动重新签发审核。

所有输出写入新版本路径；目录或文件已存在即报错。需要修订就增加 revision 与目录名，不覆盖旧版本。工具的字符与格式检查不代替人工语义、事实和逐字听验。
