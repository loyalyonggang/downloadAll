# downloadAll

## 这是什么

`downloadAll` 是一个安装到本地 AI Agent 的在线视频下载 Skill，不是网页、手机 App 或浏览器插件。

安装后，可以直接对 Codex、Claude Code、Cursor 等 Agent 说“下载这个 + 视频链接”，让 Agent 下载视频、提取 MP3、保存字幕或查看媒体信息。普通网站由 `yt-dlp` 解析，微信视频号使用内置适配器。

支持 YouTube、B站、X/Twitter、抖音、TikTok、小红书、Instagram、Facebook、Vimeo、Twitch、Reddit、微博、AcFun，以及其他可由 `yt-dlp` 识别的 HTTPS 页面。

## 怎么使用

### 30 秒开始

需要一台能运行本地 Agent 和终端的电脑。当前安装器需要 Node.js 22.20 或更高版本，本项目脚本需要 Python 3.10 或更高版本。

先打开终端检查版本：

```bash
node --version
python3 --version
```

如果提示找不到命令，请先安装 [Node.js](https://nodejs.org/) 或 [Python](https://www.python.org/downloads/)。不要下载本仓库 ZIP。

#### 1. 安装到 Agent

Codex：

```bash
npx skills add \
  loyalyonggang/downloadAll \
  -g -a codex
```

Claude Code：

```bash
npx skills add \
  loyalyonggang/downloadAll \
  -g -a claude-code
```

Cursor：

```bash
npx skills add \
  loyalyonggang/downloadAll \
  -g -a cursor
```

只运行与你使用的 Agent 对应的一条命令。`-g` 表示安装到当前用户，所有项目都可以使用。

#### 2. 确认安装成功

以 Codex 为例：

```bash
npx skills ls -g -a codex
```

看到 `download-all` 后，重新打开一个 Agent 对话并发送：

```text
请使用 download-all 检查下载环境是否准备完成
```

Agent 会检查 `yt-dlp`、`ffmpeg` 和 `ffprobe`。只有显示“下载环境已准备完成”才算完成；缺少依赖时会给出下一条可执行命令。

#### 3. 开始下载

```text
下载这个：https://example.com/video
把这个 B 站视频下载成 1080p：https://www.bilibili.com/video/...
把这个 YouTube 视频提取成 MP3：https://youtu.be/...
下载这个视频的中英文字幕：https://youtube.com/watch?v=...
查看这个视频的信息：https://vimeo.com/...
```

默认保存到 `~/Downloads`。公开解析失败、确实需要浏览器 Cookie 时，Agent 会先说明原因并征得同意。

### 手动安装下载依赖

通常让 Agent 根据自检结果处理即可。如果需要手动安装：

macOS：

```bash
brew install yt-dlp ffmpeg
```

Ubuntu / Debian：

```bash
sudo apt update && sudo apt install ffmpeg
python3 -m pip install --user --upgrade yt-dlp
```

当前完整回归环境是 macOS Apple Silicon。Linux 和 Windows 尚未完成同等验证，尤其是微信视频号流程。

### 命令行使用

不通过 Agent 时，也可以在仓库目录运行：

```bash
python3 scripts/download.py doctor
python3 scripts/download.py download 'https://example.com/video'
python3 scripts/download.py download URL --quality 1080p
python3 scripts/download.py audio URL
python3 scripts/download.py subtitles URL --langs 'zh.*,en.*'
python3 scripts/download.py info URL
```

### 微信视频号

微信视频号属于高级功能。首次使用先执行只读检查：

```bash
python3 scripts/download.py setup-wechat
```

它只显示当前状态和下一步，不会自动信任证书、修改系统代理或操作微信客户端。涉及安装本地后端、证书或代理变更时，必须分别取得用户授权。

## 特点优势

- **一句话下载**：只需“下载这个 + URL”，无需记忆下载命令。
- **首次自检明确**：一次列出所有缺失依赖，并给出下一步。
- **多平台统一入口**：普通网站走 `yt-dlp`，微信视频号自动切换内置适配器。
- **严格画质限制**：指定 1080p、720p 或 480p 后，不会静默下载更高画质。
- **隐私优先**：默认公开解析；需要浏览器 Cookie 时先征得同意并由用户指定浏览器。
- **安全更新**：正常下载不预先修改环境；仅在解析故障时检查版本，升级前征得同意。
- **结果验真**：下载完成后使用 `ffprobe` 检查媒体流、时长、分辨率和文件大小。
- **保护已有文件**：禁止播放列表意外扩张、禁止覆盖、同一任务重复下载加锁。
- **访问边界清晰**：不绕过 DRM、付费墙、会员权限、地区限制或安全验证。

请只下载你有权访问和保存的内容，并遵守目标平台条款与当地法律。许可证及依法必须保留的版权声明见 [LICENSE](LICENSE)。
