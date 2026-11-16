---
name: tudouni-maitian-publisher
description: 将已验收的土豆泥成片交接转换为麦田发布助手工程，在ego浏览器逐平台上传并核验抖音、小红书草稿。用于成片、封面和文案的发布交接、插件安装与草稿验证；不负责写稿或制片。
---

# 土豆泥麦田发布交接

复用用户指定的麦田 Chrome 插件，在 ego lite 中运行。当前流程只上传并保存草稿；正式发布需要用户另行明确指令。不要把插件的“已填写”当成平台草稿已保存。

## 开始

- 先读项目当前发布规则、最终 `video/交接.json` 和既有草稿记录。只接收明确交付的成片，不把原片、参考片或测试视频纳入上传。
- 读取已安装的 ego-browser 技能，全程使用同一 TaskSpace，不操作用户 Chrome。插件源码、安装及适配见 [插件接入](references/plugin.md)。
- 新工作流使用本执行器；同一视频不再同时投递 Qoder。旧项目沿用已有接收端和草稿证据，先查重再决定迁移，不改历史记录。

## 准备工程

```bash
SKILL_DIR="${CODEX_HOME:-$HOME/.codex}/skills/tudouni-maitian-publisher"
python3 "$SKILL_DIR/scripts/prepare_publish.py" \
  --manifest "/发布包/video/交接.json" --platform douyin \
  --out-dir "/iCloud外工程/发布/本次抖音"
node "/麦田插件目录/tools/validate.mjs" "/iCloud外工程/发布/本次抖音"
```

小红书使用 `--platform xiaohongshu`，单独输出目录。依赖 Python 3.10+ 和 ffprobe。转换器核对发布授权、账号确认、成片 SHA256/大小及实际音轨、文案字段与封面比例；输出目录必须不存在。它不执行浏览器动作，也不会上传。

交接沿用既有字段：`package` 绝对路径、`video.file/sha256/fileSize`、`checks.technicalOk/hasAudio`、`platforms.<平台>.account.id/accountConfirmedByUser/title/body/covers`。`publishing` 必须是 `mode=draft-only, approved=false, draftUploadAuthorized=true, allowImmediate=false, allowSchedule=false`。

封面支持 `3x4/4x3` 或旧 `vertical/horizontal` 键，但检查真实比例：抖音需要 3:4、4:3，小红书需要 3:4。旧封面比例不符就另存适配图，不覆盖原图、不把 9:16 或 16:9 冒充目标比例。topics 只取交接中已审核的话题。包内 `handoff-check.json` 含本地账号核验信息，不上传 GitHub。

## ego 上传与核验

1. 先在对应平台页面现场核对账号与交接一致，并检查已有同视频/标题草稿；找到账户不符、已有草稿、未知投递结果、验证码或平台错误就停在该平台。不得以插件登录预检代替账号核对。
2. 打开麦田插件，选择本地草稿交接目录，并将同一目录的绝对路径填入“所选目录的本机路径”；首次目录授权交给用户。随后选择实际工程并执行校验。每次只选抖音或小红书一个平台，无排期。源码支持更多平台不等于本次授权。
3. 逐项核对最终视频、封面、标题、正文、话题和 AI 声明。插件只填写；根据平台实际按钮保存草稿并回读草稿管理页确认。没有可用保存路径时保留编辑页并报告“已填写，未核验草稿”，不点击发布。
4. 只有平台真实返回及草稿页证据支持时，回填原交接和发布状态中的平台草稿状态、核验时间、证据位置或草稿标识。分清工程已生成、插件已填写、草稿已保存和平台已核验。不把草稿写成“已发布”。
5. 失败不自动重试。未知结果先回到原页核对，避免重复上传；一个平台结束后才处理下一个。清理临时截图，保留正式交付素材。

正式发布、排期、增平台和账号更换超出本技能当前流程；得到明确指令后按项目规则另行处理，不能从缺少 schedule 推断立即发布。
