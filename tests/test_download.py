#!/usr/bin/env python3
"""Unit tests for downloadAll."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_INTERFACE = "internal-module"

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "download.py"
SPEC = importlib.util.spec_from_file_location("download_all_download", MODULE_PATH)
assert SPEC and SPEC.loader
download = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(download)


class DownloadSkillTests(unittest.TestCase):
    def test_accepts_supported_public_https_urls(self) -> None:
        for url in ("https://x.com/a/status/1", "https://www.bilibili.com/video/BV1x", "https://youtu.be/abcdefghijk"):
            self.assertEqual(download.normalize_url(url), url)

    def test_rejects_non_https_and_private_targets(self) -> None:
        for url in ("http://x.com/a/status/1", "https://localhost/a", "https://127.0.0.1/video", "https://user:pass@x.com/a"):
            with self.assertRaises(download.SkillError):
                download.normalize_url(url)

    def test_accepts_wechat_for_embedded_adapter(self) -> None:
        url = "https://weixin.qq.com/sph/abc"
        self.assertEqual(download.normalize_url(url), url)
        self.assertTrue(download.is_wechat_channels_url(url))
        self.assertEqual(download.platform_name(url), "WeChat Channels")

    def test_rejects_wechat_without_share_token(self) -> None:
        with self.assertRaises(download.SkillError) as caught:
            download.normalize_url("https://weixin.qq.com/sph/")
        self.assertEqual(caught.exception.stage, "validate")

    def test_platform_detection(self) -> None:
        self.assertEqual(download.platform_name("https://m.youtube.com/watch?v=x"), "YouTube")
        self.assertEqual(download.platform_name("https://www.bilibili.com/video/x"), "Bilibili")
        self.assertEqual(download.platform_name("https://x.com/a/status/1"), "X")
        self.assertEqual(download.platform_name("https://example.com/video"), "yt-dlp generic extractor")

    def test_quality_presets_never_fall_back_above_the_requested_cap(self) -> None:
        for quality, height in (("1080p", 1080), ("720p", 720), ("480p", 480)):
            selector = download.QUALITY_FORMATS[quality]
            self.assertNotIn("/bv*+ba/b", selector)
            for alternative in selector.split("/"):
                self.assertIn(f"height<={height}", alternative)

    def test_auto_cookie_is_public_first(self) -> None:
        with patch.object(download, "load_metadata_once", return_value={"id": "x"}) as loader:
            payload, browser, warnings = download.load_metadata("https://x.com/a/status/1", "auto")
        self.assertEqual(payload["id"], "x")
        self.assertIsNone(browser)
        self.assertEqual(warnings, [])
        loader.assert_called_once_with("https://x.com/a/status/1", None, 90)

    def test_auto_cookie_requires_consent_after_public_failure(self) -> None:
        with patch.object(download, "detect_cookie_browser", return_value="chrome"), patch.object(
            download, "load_metadata_once", side_effect=download.SkillError("metadata", "blocked")
        ) as loader:
            with self.assertRaises(download.SkillError) as caught:
                download.load_metadata("https://x.com/a/status/1", "auto")
        self.assertEqual(caught.exception.stage, "cookie_consent_required")
        self.assertIn("--cookies-from-browser chrome", caught.exception.next_action)
        loader.assert_called_once_with("https://x.com/a/status/1", None, 90)

    def test_explicit_cookie_browser_is_used_after_consent(self) -> None:
        with patch.object(download, "load_metadata_once", return_value={"id": "x"}) as loader:
            payload, browser, warnings = download.load_metadata("https://x.com/a/status/1", "chrome")
        self.assertEqual(payload["id"], "x")
        self.assertEqual(browser, "chrome")
        self.assertEqual(warnings, [])
        loader.assert_called_once_with("https://x.com/a/status/1", "chrome", 90)

    def test_cookie_default_is_consent_first(self) -> None:
        args = download.build_parser().parse_args(["download", "https://example.com/video"])
        self.assertEqual(args.cookies_from_browser, "ask")

    def test_matching_files_excludes_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            final = root / "Title [id].mp4"
            fragment = root / "Title [id].f399.mp4"
            partial = root / "Title [id].mp4.part"
            for path in (final, fragment, partial):
                path.write_bytes(b"fixture")
            self.assertEqual(download.matching_files(root, "id", download.VIDEO_OUTPUT_SUFFIXES), [final])

    def test_cleanup_only_removes_new_fragments(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / "Title [id].f140.m4a"
            new = root / "Title [id].f251.m4a"
            old.write_bytes(b"old"); new.write_bytes(b"new")
            removed = download.cleanup_new_format_fragments(root, "id", {old.resolve()})
            self.assertEqual(removed, [str(new.resolve())])
            self.assertTrue(old.exists()); self.assertFalse(new.exists())

    @patch.object(download, "optional_tool_version", return_value="available")
    @patch.object(download, "detect_ytdlp_manager", return_value=("self-update", ["yt-dlp", "-U"]))
    @patch.object(download, "latest_ytdlp_version", return_value="2026.09.18")
    @patch.object(download, "executable_version", return_value="2026.09.18")
    @patch.object(download, "require_tool", return_value="/tmp/yt-dlp")
    def test_doctor_reports_current_version(self, *_mocks) -> None:
        result = download.doctor(False, 30)
        self.assertTrue(result["ready"])
        self.assertEqual(result["missing_dependencies"], [])
        self.assertFalse(result["yt_dlp"]["outdated"])
        self.assertFalse(result["yt_dlp"]["upgraded"])

    @patch.object(download, "optional_tool_version", return_value="available")
    @patch.object(download, "require_tool", side_effect=download.SkillError("dependency", "missing"))
    @patch.object(download, "latest_ytdlp_version")
    def test_doctor_reports_missing_ytdlp_without_update_check(self, latest, *_mocks) -> None:
        result = download.doctor(False, 30)
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["missing_dependencies"], ["yt-dlp"])
        self.assertIn("yt-dlp", result["next_action"])
        self.assertFalse(result["yt_dlp"]["installed"])
        latest.assert_not_called()

    @patch.object(download, "optional_tool_version", side_effect=lambda name: None if name == "ffmpeg" else "available")
    @patch.object(download, "detect_ytdlp_manager", return_value=("self-update", ["yt-dlp", "-U"]))
    @patch.object(download, "latest_ytdlp_version", return_value="2026.09.18")
    @patch.object(download, "executable_version", return_value="2026.09.18")
    @patch.object(download, "require_tool", return_value="/tmp/yt-dlp")
    def test_doctor_is_not_ready_when_ffmpeg_is_missing(self, *_mocks) -> None:
        result = download.doctor(False, 30)
        self.assertFalse(result["ok"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["missing_dependencies"], ["ffmpeg"])
        self.assertIn("ffmpeg", result["next_action"])

    @patch.object(download, "optional_tool_version", return_value="available")
    @patch.object(download, "detect_ytdlp_manager", return_value=("self-update", ["yt-dlp", "-U"]))
    @patch.object(download, "latest_ytdlp_version", side_effect=download.SkillError("update-check", "offline"))
    @patch.object(download, "executable_version", return_value="2026.09.18")
    @patch.object(download, "require_tool", return_value="/tmp/yt-dlp")
    def test_doctor_keeps_local_readiness_when_update_check_is_offline(self, *_mocks) -> None:
        result = download.doctor(False, 30)
        self.assertTrue(result["ok"])
        self.assertTrue(result["ready"])
        self.assertIsNone(result["yt_dlp"]["latest_stable_version"])
        self.assertTrue(result["warnings"])

    def test_cli_help_has_required_commands(self) -> None:
        parser = download.build_parser()
        help_text = parser.format_help()
        for command in ("doctor", "info", "download", "audio", "subtitles", "setup-wechat"):
            self.assertIn(command, help_text)

    def test_wechat_adapter_result_is_forwarded(self) -> None:
        payload = {"ok": True, "platform": "WeChat Channels", "files": [{"path": "/tmp/video.mp4"}]}
        completed = download.subprocess.CompletedProcess([], 0, json.dumps(payload), "")
        with patch.object(download.subprocess, "run", return_value=completed):
            result = download.run_wechat_adapter(
                "https://weixin.qq.com/sph/abc", Path("/tmp"), 30, "never", 0, False
            )
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
