"""Real-file integration tests for MediaBUDA."""
import os, sys, json, tempfile
from dataclasses import asdict
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from APP.ffmpeg_pro_studio_v2_pillow import FFmpegBackend, Job, format_seconds
from APP.export_settings import validate_export_settings
from APP.worker_thread import compute_progress
from APP.main_window import extract_media_info_labels

VIDEO = r"C:\Users\tashi.TASHI-LENOVO\Videos\2026-04-01_06-02-05_export.mp4"
nf = pytest.mark.skipif(not os.path.exists(VIDEO), reason="no video")

@pytest.fixture(scope="module")
def be():
    b = FFmpegBackend(); b.check_tools(); return b

@pytest.fixture(scope="module")
def info(be):
    return be.probe(VIDEO)

@nf
class TestProbe:
    def test_duration(self, info):
        assert info["duration"] > 0
    def test_video(self, info):
        assert info["video"] is not None

@nf
class TestPreview:
    def test_frame(self, be):
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            p = f.name
        try:
            be.run_simple(be.build_preview_frame_cmd(VIDEO, 1.0, p))
            assert os.path.getsize(p) > 1000
        finally:
            os.unlink(p)

@nf
class TestTrim:
    def test_reencode(self, be, info, tmp_path):
        j = Job(VIDEO, str(tmp_path), "Between", 0, 3.0, info["duration"], True,
                "libx264", "aac", "23", "ultrafast", "128k", "", "mp4", "t")
        o = be.build_output_path(j)
        be.run_simple(be.build_trim_cmd(j, o))
        assert os.path.getsize(o) > 5000

@nf
class TestAudio:
    def test_mp3(self, be, tmp_path):
        o = os.path.join(str(tmp_path), "a.mp3")
        be.run_simple([be.ffmpeg, "-y", "-hide_banner", "-i", VIDEO,
                       "-ss", "0", "-t", "3", "-vn",
                       "-c:a", "libmp3lame", "-b:a", "128k", o])
        assert os.path.getsize(o) > 3000

@nf
class TestResize:
    def test_720p(self, be, tmp_path):
        o = os.path.join(str(tmp_path), "r.mp4")
        be.run_simple([be.ffmpeg, "-y", "-hide_banner",
                       "-ss", "0", "-t", "3", "-i", VIDEO,
                       "-vf", "scale=1280:720",
                       "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
                       "-c:a", "aac", "-b:a", "128k", o])
        assert be.probe(o)["video"]["width"] == 1280

class TestValidation:
    def test_ok(self):
        assert validate_export_settings("libx264", "aac", "mp4") is None
    def test_bad(self):
        assert validate_export_settings("libx264", "aac", "webm") is not None

class TestProgress:
    def test_half(self):
        assert abs(compute_progress(50_000_000, 100) - 50.0) < 0.1

class TestJobRT:
    def test_json(self):
        j = Job(VIDEO, "C:/t", "Between", 1, 5, 100, True,
                "libx264", "aac", "18", "medium", "192k", "", "mp4", "x")
        assert Job(**json.loads(json.dumps(asdict(j)))).input_path == VIDEO
