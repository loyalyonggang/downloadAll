# Workflow

## 路由与依赖检查

`scripts/download.py` 是所有平台的统一入口。它识别 `weixin.qq.com/sph/*` 后直接调用内置视频号适配器；其他 URL 才进入 yt-dlp 流程。

普通任务直接下载，不先修改本机环境。只有站点解析失败且可能由 extractor 过期导致时，先运行只读检查：

```bash
python3 scripts/download.py doctor
```

`doctor` 只比较 GitHub 官方 latest stable release，不修改环境。检测到更新时，先向用户说明当前安装来源；用户同意后才运行 `doctor --upgrade`，根据现有来源使用 Homebrew、pip、pipx、uv 或 `yt-dlp -U`。网络检查失败或包管理器拒绝更新时，保留已安装版本并报告失败阶段。

## 下载

```bash
python3 scripts/download.py download URL --quality best --dir ~/Downloads
```

进程输出下载进度到 stderr，最终 JSON 输出到 stdout。完成条件是 JSON 中 `ok` 为 true，且每个文件通过 ffprobe 的流、时长和大小检查。

## 故障恢复

1. `validate`：检查 HTTPS URL，不改动环境。
2. `wechat_setup_required`：视频号本地后端未连接；先运行 `python3 scripts/download.py setup-wechat` 获取唯一下一步，或在用户同意发送分享 URL 后使用 `--wechat-online allowed`。
3. `manual_action_required`：只让用户手动重新打开并播放一次，再用 `--wait-page 90` 继续；Agent 不操作微信。
4. `dependency`：安装缺失依赖后重试。
5. `cookie_consent_required`：公开解析失败但尚未读取 Cookie；询问用户是否同意使用建议浏览器，明确同意后再指定浏览器重试一次。
6. `metadata`：先只读检查 yt-dlp 版本；需要升级时说明安装来源并征得同意。
7. `download`：检查网络、磁盘空间和站点可用性；同一媒体的并发任务会被锁拒绝。
8. `verify`：文件未通过 ffprobe，不宣告成功。
