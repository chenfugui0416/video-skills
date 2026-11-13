# 配音、对齐与验收

## 本机入口

- 工作流：`<WORKSPACE>/工作流/豆包配音对齐/run-voice.sh`；实现为同目录 `voice_align.py`。环境和模型复现见该目录 README 与锁定依赖，不重装可用环境。
- 私密凭据：`<PRIVATE_CONFIG>/doubao-tts.json`（0600），或 `DOUBAO_TTS_API_KEY`。只记录位置/变量名，正文不得写入 Skill、Obsidian、文案、截图或日志。

新项目一条命令执行全文合成与对齐：

```bash
"<WORKSPACE>/工作流/豆包配音对齐/run-voice.sh" run \
  --script "/绝对路径/定稿.txt" \
  --voice "zh_male_huolixiaoge_uranus_bigtts" --speed 1.0 \
  --out-dir "/绝对路径/工程/audio"
```

一次全文 POST，流式音频块属于同一次合成，不能误写为多次请求。默认音量，原始 44100Hz 单声道 16bit WAV。失败不自动重复付费调用；保留已有文件与摘要。超出单次接口范围时报告限制，让用户调整文案或选方案，仍不能自行分句合成。

WAV 完成但对齐失败，先核对文稿/音频哈希，保留失败候选，恢复第二步，不再 TTS：

```bash
"<WORKSPACE>/工作流/豆包配音对齐/run-voice.sh" align \
  --script "/绝对路径/定稿.txt" --out-dir "/绝对路径/工程/audio"
```

可用 `--phrases` 指定逐字覆盖原稿的 5–15 字短语数组，只指定分组，不给时间。默认 Whisper large-v3、语言 zh；缺依赖就安装并检查，不能占位继续。

## 时间与文字

- 原稿强制对齐，不把识别错字当新文案。短语逐字覆盖定稿，包括英文、数字、标点，仅忽略排版空白。
- `vo-acoustic.json` 保留真实发音/静音；`vo-align.json` 另存 `speech_start_ms/speech_end_ms` 与连续编辑起止。
- 连续轨首段 0；相邻切点取下一短语真实起音；静音归前段、尾静音归末段。前段结束=后段开始，末尾=WAV 采样数换算并四舍五入到毫秒的时长。静音覆盖不能宣称连续发音。
- `audio/vo-align.txt` 逐行严格 `[1249ms-3580ms] 原文短语`，并打印。格式示例不定义起始偏移。
- 异常先重对齐一次；局部失败可用真实局部声学重算在完整词边界接回，保留来源。禁止均分、插值或凭听感猜毫秒。
- 单列音频总时长、段数、最后一段结束；末段时间与音频必须相等。结构通过不自动设置 `alignment.verified=true`，整段逐字听验另记。

## timeline.json

schema_version=1，含 duration_ms、fps、script_path/audio_path、两者 SHA256、alignment、phrases、shots。短语项有 id/text/start_ms/end_ms 及可选实际发音边界；镜头有 id/roll/purpose/start_ms/end_ms/phrase_ids/events。事件项有 at_ms/phrase_id/change，信息起点取所引用短语的起点。镜头连续覆盖全文，每个短语按原序只用一次，不能跨镜切短语。

## 成片验收

1. 输入工具检查原稿、哈希、一次请求、WAV 规格、短语长度、连续性和语义边界。
2. HyperFrames 检查 runtime、layout、motion、contrast，静态 lint 不能替代。
3. ffprobe 验证实际 MP4 分辨率、帧率、音轨与时长；ffmpeg 全片解码。封装可有小于一帧的量化差，源时间轴末尾仍等于源 WAV。
4. 查看实际编码帧：人物、中文、关键结果、转场前中后。纹理不盖字，字幕不出安全区。
5. 峰值、削波、源音频对应等技术指标与人工逐字试听分开。没有试听能力如实说明，保持 false。

交付范围按本次授权。已导出可标 rendered；人物未获接受和整段未复听分别保留候选/待听验，不宣称正式发布或完全验收。
