#!/usr/bin/env python3
"""Standalone WeChat Channels adapter bundled with downloadAll.

The adapter never controls WeChat or changes system proxy settings. It can use an
already connected local backend, or a fixed online resolver when the caller has
explicitly allowed sharing the public share URL.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parent
WX_ROOT = ROOT / "wechat"


def run_component(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"component timed out after {timeout}s") from exc


def parse_json(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError("component returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("component returned a non-object JSON value")
    return payload


def preflight(url: str, timeout: int = 30) -> dict[str, Any]:
    completed = run_component(
        [sys.executable, str(WX_ROOT / "preflight.py"), "--url", url], timeout
    )
    payload = parse_json(completed.stdout)
    if completed.returncode not in (0, 2):
        raise RuntimeError("WeChat preflight failed")
    return payload


def local_settings() -> dict[str, Any]:
    home = Path(os.environ.get("DOWNLOAD_ALL_WX_VIDEO_HOME", Path.home() / ".local/share/downloadAll-wechat"))
    path = home / "local-settings.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def normalize_local_files(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    files = []
    for event in events:
        if event.get("event") != "saved" or not event.get("path"):
            continue
        files.append({
            "path": str(Path(str(event["path"])).expanduser().resolve()),
            "bytes": event.get("bytes"),
            "video_codec": event.get("codec"),
            "width": event.get("width"),
            "height": event.get("height"),
            "duration_seconds": event.get("duration_seconds"),
            "spec": event.get("spec"),
            "verification": "full-decode",
        })
    return files


def try_local(url: str, output: Path, wait_page: int, timeout: int, single: bool) -> dict[str, Any]:
    settings = local_settings()
    backend = settings.get("backend")
    config = settings.get("config")
    ffmpeg = settings.get("ffmpeg") or shutil.which("ffmpeg")
    if not all((backend, config, ffmpeg)):
        return {"ok": False, "stage": "local_configuration", "error": "local backend settings are incomplete"}
    command = [
        sys.executable, str(WX_ROOT / "download_media.py"), "--url", url,
        "--output", str(output), "--wait-page", str(max(0, wait_page)),
        "--backend", str(backend), "--config", str(config), "--ffmpeg", str(ffmpeg),
    ]
    if single:
        command.append("--single")
    completed = run_component(command, timeout)
    events = []
    for line in completed.stdout.splitlines():
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    files = normalize_local_files(events)
    if completed.returncode == 0 and files:
        return {
            "ok": True, "command": "video", "platform": "WeChat Channels",
            "adapter": "embedded-wechat-local", "files": files,
            "manual_action_used": any(e.get("event") == "manual_action_needed" for e in events),
            "ui_automation_used": False,
        }
    manual = next((e for e in events if e.get("event") == "manual_action_needed"), None)
    if manual:
        return {
            "ok": False, "stage": "manual_action_required", "platform": "WeChat Channels",
            "manual_action": manual.get("action"), "ui_automation_used": False,
            "error": "the local backend is ready but no WeChat page connection is available",
        }
    return {
        "ok": False, "stage": "local_download", "platform": "WeChat Channels",
        "error": "the connected local backend did not return verified media",
        "ui_automation_used": False,
    }


def try_online(url: str, output: Path, timeout: int, single: bool) -> dict[str, Any]:
    command = [
        sys.executable, str(WX_ROOT / "download_online.py"), "--url", url,
        "--output-dir", str(output), "--timeout", str(min(timeout, 300)),
    ]
    if single:
        command += ["--one-version", "best"]
    completed = run_component(command, timeout)
    payload = parse_json(completed.stdout)
    if completed.returncode == 0 and payload.get("ok"):
        files = []
        for item in payload.get("files") or []:
            if not isinstance(item, dict) or not item.get("path"):
                continue
            files.append({
                "path": str(Path(str(item["path"])).expanduser().resolve()),
                "bytes": item.get("bytes"), "video_codec": item.get("codec"),
                "width": item.get("width"), "height": item.get("height"),
                "duration_seconds": item.get("duration_seconds"),
                "kind": item.get("kind"), "verification": item.get("verification"),
            })
        result = {
            "ok": bool(files), "command": "video", "platform": "WeChat Channels",
            "title": payload.get("title"), "adapter": "embedded-wechat-online",
            "resolver": payload.get("worker"), "files": files,
            "share_url_sent_to_resolver": True, "ui_automation_used": False,
            "fallbacks": payload.get("fallbacks") or [],
        }
        if not files:
            result.update(stage="online_download", error="resolver succeeded but no verified media file was produced")
        return result
    return {
        "ok": False, "stage": "online_resolver", "platform": "WeChat Channels",
        "error": "fixed online resolvers could not return verified media",
        "share_url_sent_to_resolver": True, "ui_automation_used": False,
        "fallbacks": payload.get("fallbacks") or [],
    }


def download(url: str, output: Path, online: str, wait_page: int, timeout: int, single: bool) -> dict[str, Any]:
    check = preflight(url)
    if not check.get("ok"):
        return {"ok": False, "stage": "validate", "error": check.get("error"), "ui_automation_used": False}
    output.mkdir(parents=True, exist_ok=True)
    local_failure = None
    if check.get("local_api_2022_listening"):
        local = try_local(url, output, wait_page, timeout, single)
        if local.get("ok") or local.get("stage") == "manual_action_required":
            return local
        local_failure = local
    if online == "allowed":
        result = try_online(url, output, timeout, single)
        if local_failure:
            result["local_fallback"] = local_failure
        return result
    if check.get("local_api_2022_listening"):
        return local_failure or {"ok": False, "stage": "local_download", "error": "local download failed"}
    return {
        "ok": False, "stage": "wechat_setup_required", "platform": "WeChat Channels",
        "error": "尚未连接可用的视频号本地后端。",
        "user_message": "视频号需要先完成一次本地环境准备，当前没有修改证书或系统代理。",
        "next_action": "先运行 python3 scripts/download.py setup-wechat 查看下一步；也可以征得同意后使用 --wechat-online allowed。",
        "setup_steps": [
            "运行 setup-wechat 只读检查本地准备状态。",
            "选择本地模式时，安装、证书信任和系统代理修改分别说明并授权。",
            "选择在线模式时，仅在用户同意发送本次公开分享 URL 后重试。",
        ],
        "online_resolver_available": True,
        "online_resolver_requires_explicit_share_url_consent": True,
        "ui_automation_used": False,
        "preflight": check,
    }


def setup_status() -> dict[str, Any]:
    check = preflight("https://weixin.qq.com/sph/setup-check")
    settings = local_settings()
    settings_path = Path(
        os.environ.get("DOWNLOAD_ALL_WX_VIDEO_HOME", Path.home() / ".local/share/downloadAll-wechat")
    ).expanduser().resolve() / "local-settings.json"
    missing_settings = [name for name in ("backend", "config", "ffmpeg") if not settings.get(name)]
    backend_candidates = check.get("backend_candidates") or []
    api_ready = bool(check.get("local_api_2022_listening"))
    ready = api_ready and not missing_settings
    result: dict[str, Any] = {
        "ok": True,
        "command": "setup-wechat",
        "platform": check.get("platform"),
        "ready": ready,
        "checks": {
            "backend_candidates": backend_candidates,
            "local_api_2022_listening": api_ready,
            "local_proxy_2023_listening": bool(check.get("local_proxy_2023_listening")),
            "settings_path": str(settings_path),
            "missing_settings": missing_settings,
        },
        "safety": {
            "changed_certificate_trust": False,
            "changed_system_proxy": False,
            "operated_wechat_ui": False,
        },
    }
    if ready:
        result.update(
            stage="ready",
            user_message="视频号本地下载环境已准备好。",
            next_action="重新运行原视频号下载命令；缺少页面连接时，按提示手动打开并播放一次。",
            setup_steps=[],
        )
    elif not backend_candidates:
        result.update(
            stage="license_review_required",
            user_message="尚未安装锁定版本的视频号本地后端。安装器只下载并校验文件，不会信任证书或修改系统代理。",
            next_action="审阅上游许可证后，运行 python3 scripts/wechat/install_backend.py --accept-upstream-license。",
            setup_steps=[
                "审阅 ltaoo/wx_channels_download v260714 的许可证与 Commons Clause。",
                "确认后运行内置安装器；它会校验 SHA-256，并安装到用户级目录。",
                "再次运行 python3 scripts/download.py setup-wechat 检查下一步。",
            ],
        )
    elif not api_ready:
        result.update(
            stage="backend_start_required",
            user_message="本地后端文件已找到，但本地 API 尚未启动。",
            next_action="按 references/wechat-video.md 准备独立 CA 和本地后端；证书信任与系统代理修改必须分别征得同意。",
            setup_steps=[
                "确认将使用本机独立生成的 CA，而不是共享根证书。",
                "在修改系统代理前保存 HTTP、HTTPS、SOCKS 和网络服务快照。",
                "启动后端后再次运行 setup-wechat，确认本地 API 已监听。",
            ],
        )
    else:
        result.update(
            stage="local_configuration_required",
            user_message="本地 API 已启动，但下载设置尚未完整。",
            next_action=f"补全 {settings_path} 中的 backend、config、ffmpeg 路径，然后重新运行 setup-wechat。",
            setup_steps=[
                "填写当前锁定后端的可执行文件路径。",
                "填写后端配置文件路径和 ffmpeg 路径。",
                "重新运行 setup-wechat，直到 ready 为 true。",
            ],
        )
    return result


def doctor(url: str | None = None) -> dict[str, Any]:
    components = ["preflight.py", "download_media.py", "download_online.py", "install_backend.py", "release-lock.json"]
    missing = [name for name in components if not (WX_ROOT / name).is_file()]
    result: dict[str, Any] = {
        "ok": not missing, "adapter": "embedded-wechat", "components": components,
        "missing": missing, "ui_automation": "forbidden",
    }
    if url:
        result["preflight"] = preflight(url)
        result["ok"] = result["ok"] and bool(result["preflight"].get("ok"))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bundled WeChat Channels adapter for downloadAll")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("doctor")
    check.add_argument("--url")
    commands.add_parser("setup")
    item = commands.add_parser("download")
    item.add_argument("url")
    item.add_argument("--dir", dest="output_dir")
    item.add_argument("--online", choices=("never", "allowed"), default="never")
    item.add_argument("--wait-page", type=int, default=0)
    item.add_argument("--timeout", type=int, default=1200)
    item.add_argument("--single", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "doctor":
        result = doctor(args.url)
    elif args.command == "setup":
        result = setup_status()
    else:
        output = Path(args.output_dir or Path.home() / "Downloads").expanduser().resolve()
        result = download(args.url, output, args.online, args.wait_page, args.timeout, args.single)
    print(json.dumps(result, ensure_ascii=False))
    if not result.get("ok"):
        raise SystemExit(4)


if __name__ == "__main__":
    main()
