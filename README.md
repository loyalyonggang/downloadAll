# downloadAll

## 这是什么

`downloadAll` 是一个面向 AI Agent 的在线视频下载与媒体提取工具。提供视频链接后，可以下载视频、提取 MP3、下载字幕或查看媒体信息。

支持 YouTube、B站、X/Twitter、抖音、TikTok、小红书、Instagram、Facebook、Vimeo、Twitch、Reddit、微博、AcFun，以及其他可由 `yt-dlp` 识别的 HTTPS 页面。微信视频号使用内置适配器处理。

## 怎么使用

### 1. 安装依赖

需要 Python 3.10+、`yt-dlp`、`ffmpeg` 和 `ffprobe`。

macOS：

```bash
brew install yt-dlp ffmpeg
```

Ubuntu / Debian：

```bash
sudo apt update
sudo apt install ffmpeg
python3 -m pip install --user --upgrade yt-dlp
```

### 2. 安装 Skill

```bash
npx skills add loyalyonggang/downloadAll
```

### 3. 直接对 Agent 说

```text
下载这个：https://example.com/video
把这个 B 站视频下载成 1080p：https://www.bilibili.com/video/...
把这个 YouTube 视频提取成 MP3：https://youtu.be/...
下载这个视频的中英文字幕：https://youtube.com/watch?v=...
查看这个视频的信息：https://vimeo.com/...
```

默认保存到 `~/Downloads`。也可以通过 `--dir` 或 `DOWNLOAD_ALL_DOWNLOAD_OUTPUT` 指定目录。

命令行示例：

```bash
python3 scripts/download.py download 'https://example.com/video'
python3 scripts/download.py download URL --quality 1080p
python3 scripts/download.py audio URL
python3 scripts/download.py subtitles URL --langs 'zh.*,en.*'
python3 scripts/download.py info URL
```

微信视频号首次使用时，先执行只读检查：

```bash
python3 scripts/download.py setup-wechat
```

它会显示当前准备状态和下一步，不会自动信任证书、修改系统代理或操作微信客户端。

## 特点优势

- **一句话下载**：只需“下载这个 + URL”，无需记忆命令。
- **多平台统一入口**：普通网站走 `yt-dlp`，微信视频号自动切换内置适配器。
- **严格画质限制**：指定 1080p、720p 或 480p 后，不会静默下载更高画质。
- **隐私优先**：默认公开解析；需要浏览器 Cookie 时先征得同意并由用户指定浏览器。
- **安全更新**：正常下载不预先修改环境；仅在解析故障时检查版本，升级前征得同意。
- **结果验真**：下载完成后使用 `ffprobe` 检查媒体流、时长、分辨率和文件大小。
- **保护已有文件**：禁止播放列表意外扩张、禁止覆盖、同一任务重复下载加锁。
- **明确失败恢复**：错误结果包含阶段和下一步操作，不把未验证文件报告为成功。
- **访问边界清晰**：不绕过 DRM、付费墙、会员权限、地区限制或安全验证。

请只下载你有权访问和保存的内容，并遵守目标平台条款与当地法律。许可证及依法必须保留的版权声明见 [LICENSE](LICENSE)。
