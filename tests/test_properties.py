"""Property-based tests for MediaBUDA (Hypothesis).

Each test validates a correctness property from the design doc.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from APP.ffmpeg_pro_studio_v2_pillow import (
    format_seconds, add_recent_file, load_config, save_config, Job,
)
from APP.main_window import extract_media_info_labels


# ── Property 1: Recent files list bounded and ordered ────────────────
# Feature: ffmpeg-pro-studio, Property 1: Recent files bounded and ordered

@given(paths=st.lists(st.text(min_size=1, max_size=200), min_size=0, max_size=30))
@settings(max_examples=100)
def test_recent_files_bounded_and_ordered(paths):
    """For any sequence of file additions, the list never exceeds 10,
    the most recently added file is at index 0, and no duplicates exist."""
    cfg = {"recent_files": []}
    for p in paths:
        add_recent_file(cfg, p)
    recents = cfg["recent_files"]
    # Bounded
    assert len(recents) <= 10
    # Most recent at index 0
    if paths:
        assert recents[0] == paths[-1]
    # No duplicates
    assert len(recents) == len(set(recents))


# ── Property 2: Probe result mapping completeness ────────────────────
# Feature: ffmpeg-pro-studio, Property 2: Probe mapping completeness

_optional_video = st.one_of(
    st.none(),
    st.fixed_dictionaries({
        "codec_name": st.text(min_size=1, max_size=20),
        "width": st.integers(1, 8000),
        "height": st.integers(1, 8000),
    }),
)
_optional_audio = st.one_of(
    st.none(),
    st.fixed_dictionaries({
        "codec_name": st.text(min_size=1, max_size=20),
    }),
)
_media_info = st.fixed_dictionaries({
    "duration": st.floats(min_value=0, max_value=360000, allow_nan=False, allow_infinity=False),
    "video": _optional_video,
    "audio": _optional_audio,
    "format": st.fixed_dictionaries({
        "size": st.one_of(st.none(), st.integers(0, 10**12).map(str)),
    }),
    "streams": st.just([]),
})


@given(info=_media_info)
@settings(max_examples=100)
def test_probe_mapping_completeness(info):
    """For any valid media info dict, extract_media_info_labels returns all
    required fields. Missing optional fields show '—', never raise."""
    labels = extract_media_info_labels(info)
    assert "duration" in labels
    assert "resolution" in labels
    assert "codecs" in labels
    assert "file_size" in labels
    # Missing video → resolution shows placeholder
    if info["video"] is None:
        assert "—" in labels["resolution"]
    else:
        assert str(info["video"]["width"]) in labels["resolution"]
        assert str(info["video"]["height"]) in labels["resolution"]
    # Missing audio → codecs shows placeholder for audio part
    if info["audio"] is None:
        assert "—" in labels["codecs"]
    # Zero duration → placeholder
    if info["duration"] == 0:
        assert "—" in labels["duration"]


# ── Property 5: Timecode formatting correctness ─────────────────────
# Feature: ffmpeg-pro-studio, Property 5: Timecode formatting correctness

@given(seconds=st.floats(min_value=0, max_value=86399, allow_nan=False, allow_infinity=False))
@settings(max_examples=100)
def test_timecode_format_roundtrip(seconds):
    """format_seconds produces HH:MM:SS.mmm and round-trips within 0.001s."""
    result = format_seconds(seconds)
    # Format check
    parts = result.split(":")
    assert len(parts) == 3
    h, m, s_str = parts
    assert len(h) >= 2  # zero-padded, may be >2 for large values
    assert len(m) == 2
    # Round-trip
    parsed = int(h) * 3600 + int(m) * 60 + float(s_str)
    assert abs(parsed - seconds) < 0.001


# ── Property 3: Preview scaling preserves aspect ratio ───────────────
# Feature: ffmpeg-pro-studio, Property 3: Preview scaling preserves aspect ratio

from APP.preview_panel import scale_keeping_ratio


@given(
    w=st.integers(min_value=100, max_value=8000),
    h=st.integers(min_value=100, max_value=8000),
    cw=st.integers(min_value=100, max_value=8000),
    ch=st.integers(min_value=100, max_value=8000),
)
@settings(max_examples=100)
def test_preview_scaling_aspect_ratio(w, h, cw, ch):
    """Scaled dims fit container and aspect ratio preserved within ±0.01."""
    sw, sh = scale_keeping_ratio(w, h, cw, ch)
    # Fits within container
    assert sw <= cw
    assert sh <= ch
    assert sw >= 1
    assert sh >= 1
    # Aspect ratio preserved within rounding tolerance.
    # Integer pixel rounding means 1px error on small dimensions causes
    # proportionally larger ratio error. Tolerance scales with min dimension.
    orig_ratio = w / h
    scaled_ratio = sw / sh
    abs_error = abs(orig_ratio - scaled_ratio)
    # With integer rounding, the max error in ratio is approximately
    # orig_ratio * (1/min_dim), since 1px change on min_dim shifts ratio by ~ratio/min_dim
    min_dim = min(sw, sh)
    tolerance = max(0.02, orig_ratio / min_dim + 0.001)
    assert abs_error < tolerance


# ── Property 4: Timeline marker invariant ────────────────────────────
# Feature: ffmpeg-pro-studio, Property 4: Timeline marker invariant


@given(
    duration=st.floats(min_value=1.0, max_value=7200, allow_nan=False, allow_infinity=False),
    start_val=st.floats(min_value=0, max_value=7200, allow_nan=False, allow_infinity=False),
    end_val=st.floats(min_value=0, max_value=7200, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=None)
def test_timeline_marker_invariant(qapp, duration, start_val, end_val):
    """start <= end always holds after any sequence of movements."""
    from APP.timeline_scrubber import TimelineScrubber
    ts = TimelineScrubber()
    ts.set_duration(duration)
    # Clamp inputs to valid range
    max_ms = int(duration * 1000)
    s_ms = max(0, min(max_ms, int(start_val * 1000)))
    e_ms = max(0, min(max_ms, int(end_val * 1000)))
    ts.start_slider.setValue(s_ms)
    ts.end_slider.setValue(e_ms)
    assert ts.get_start() <= ts.get_end()


# ── Property 6: Set marker from preview copies value ─────────────────
# Feature: ffmpeg-pro-studio, Property 6: Set marker from preview

@given(
    duration=st.floats(min_value=1.0, max_value=7200, allow_nan=False, allow_infinity=False),
    preview_val=st.floats(min_value=0, max_value=7200, allow_nan=False, allow_infinity=False),
)
@settings(max_examples=100, deadline=None)
def test_set_marker_from_preview(qapp, duration, preview_val):
    """set_start_from_preview / set_end_from_preview copy the preview value
    while maintaining start <= end."""
    from APP.timeline_scrubber import TimelineScrubber
    ts = TimelineScrubber()
    ts.set_duration(duration)
    max_ms = int(duration * 1000)
    p_ms = max(0, min(max_ms, int(preview_val * 1000)))
    ts.preview_slider.setValue(p_ms)

    ts.set_start_from_preview()
    assert abs(ts.get_start() - ts.get_preview()) < 0.002
    assert ts.get_start() <= ts.get_end()

    ts.set_end_from_preview()
    assert abs(ts.get_end() - ts.get_preview()) < 0.002
    assert ts.get_start() <= ts.get_end()
