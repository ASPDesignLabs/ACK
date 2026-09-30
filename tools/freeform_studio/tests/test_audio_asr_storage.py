import numpy as np
import pytest

from conftest import fake_whisper_model, make_live_webm, make_wav, needs_ffmpeg
from freeform_studio import audio
from freeform_studio.asr import AsrOptions, EngineError, FakeEngine, FasterWhisperEngine
from freeform_studio.storage import ChunkGap, InvalidTakeId, NoChunks, TakeStore


# ------------------------------------------------------------------ audio
def test_peaks_have_right_shape_and_values(tmp_path):
    wav = make_wav(tmp_path / "a.wav", 2.0, [(0.0, 2.0)], amp=0.5)
    peaks = audio.compute_peaks(wav)
    frames = 2 * 48000
    for spp, data in peaks.items():
        arr = np.frombuffer(data, dtype=np.int8)
        assert len(arr) == 2 * -(-frames // spp)  # ceil(frames/spp) pairs, min+max each
        assert arr[1::2].max() in range(60, 64) and arr[0::2].min() in range(-64, -60)  # 0.5 full scale ~ 63


def test_peaks_silence_is_zero(tmp_path):
    wav = make_wav(tmp_path / "s.wav", 1.0, [])
    assert set(np.frombuffer(audio.compute_peaks(wav)[512], dtype=np.int8)) <= {0, -1}


def test_voiced_regions_find_the_bursts(tmp_path):
    wav = make_wav(tmp_path / "b.wav", 6.0, [(0.5, 2.0), (3.0, 5.0)])
    db, hop = audio.rms_envelope(wav)
    regions = audio.voiced_regions(db, hop)
    assert len(regions) == 2
    assert abs(regions[0][0] - 0.5) < 0.05 and abs(regions[1][1] - 5.0) < 0.05


@needs_ffmpeg
def test_decode_handles_chrome_style_webm(tmp_path):
    wav = make_wav(tmp_path / "in.wav", 3.0, [(0.2, 2.5)], rate=44100)
    webm = make_live_webm(wav, tmp_path / "in.webm")
    out = tmp_path / "out.wav"
    audio.decode_to_wav(webm, out)
    frames, rate = audio.wav_info(out)
    assert rate == 48000 and abs(frames / rate - 3.0) < 0.1
    assert not list(tmp_path.glob("*.tmp*"))


@needs_ffmpeg
def test_decode_garbage_raises_a_readable_error(tmp_path):
    bad = tmp_path / "bad.webm"
    bad.write_bytes(b"this is not audio at all" * 20)
    with pytest.raises(audio.FfmpegError):
        audio.decode_to_wav(bad, tmp_path / "x.wav")
    assert not (tmp_path / "x.wav").exists()


# ------------------------------------------------------------------ fake engine
def test_fake_engine_is_deterministic_and_uses_reference_text(tmp_path):
    wav = make_wav(tmp_path / "f.wav", 8.0, [(0.5, 2.5), (3.5, 5.0), (6.0, 7.5)])
    ref = "the quick brown fox jumps over the lazy dog again and again today"
    opts = AsrOptions(reference_text=ref)
    a = FakeEngine().transcribe(wav, opts)
    b = FakeEngine().transcribe(wav, opts)
    strip = lambda r: [(w["w"], w["s"], w["e"]) for s in r["segments"] for w in s["words"]]
    assert strip(a) == strip(b)
    assert len(a["segments"]) == 3
    spoken = " ".join(w["w"].rstrip(".") for s in a["segments"] for w in s["words"])
    assert spoken.startswith("the quick brown fox") and len(spoken.split()) >= 11
    assert all(s["words"][-1]["w"].endswith(".") for s in a["segments"])


# ------------------------------------------------------------------ faster-whisper adapter (no model needed)
def test_faster_whisper_adapter_converts_and_passes_options(tmp_path):
    calls, built = [], []
    engine = FasterWhisperEngine("small.en", "cpu", "int8",
                                 model_factory=lambda name, **kw: (built.append((name, kw)), fake_whisper_model(calls))[1])
    assert not engine.loaded and built == []  # lazy
    progress = []
    res = engine.transcribe(tmp_path / "x.wav", AsrOptions(initial_prompt="Um, so.", hotwords="Kojima"), progress.append)
    assert engine.loaded and built == [("small.en", {"device": "cpu", "compute_type": "int8"})]
    kw = calls[0][1]
    assert kw["word_timestamps"] is True and kw["vad_filter"] is True
    assert kw["initial_prompt"] == "Um, so." and kw["hotwords"] == "Kojima"
    assert kw["condition_on_previous_text"] is False
    (seg,) = res["segments"]
    assert seg["text"] == "Hello world." and [w["w"] for w in seg["words"]] == ["Hello", "world."]  # blank word dropped
    assert seg["words"][0] == {"w": "Hello", "s": 0.123, "e": 0.5, "p": 0.988}
    assert progress and progress[-1] == 0.5 and res["duration"] == 2.0
    engine.unload()
    assert not engine.loaded


def test_faster_whisper_blank_hints_become_none(tmp_path):
    calls = []
    engine = FasterWhisperEngine("m", model_factory=lambda name, **kw: fake_whisper_model(calls))
    engine.transcribe(tmp_path / "x.wav", AsrOptions())
    assert calls[0][1]["initial_prompt"] is None and calls[0][1]["hotwords"] is None


# ------------------------------------------------------------------ storage
def test_take_ids_cannot_escape_the_folder(tmp_path):
    store = TakeStore(tmp_path)
    for bad in ("../x", "..", "t1", "", "t20260101-000000-zzzz", "t20260101-000000-abcd/../.."):
        with pytest.raises(InvalidTakeId):
            store.path(bad)


def test_chunks_out_of_order_duplicates_and_assembly(tmp_path):
    store = TakeStore(tmp_path)
    tid = store.create({})["id"]
    for n, data in [(2, b"CC"), (0, b"AA"), (1, b"xx"), (1, b"BB")]:  # 1 is sent twice; last write wins
        store.write_chunk(tid, n, data)
    assert store.received(tid) == [0, 1, 2]
    info = store.assemble(tid)
    assert (store.path(tid, "raw.webm")).read_bytes() == b"AABBCC" and info["bytes"] == 6 and info["missing"] == []


def test_gap_is_reported_and_salvage_keeps_the_prefix(tmp_path):
    store = TakeStore(tmp_path)
    tid = store.create({})["id"]
    for n in (0, 1, 3):
        store.write_chunk(tid, n, bytes([65 + n]))
    with pytest.raises(ChunkGap) as e:
        store.assemble(tid)
    assert e.value.missing == [2]
    info = store.assemble(tid, salvage=True)
    assert store.path(tid, "raw.webm").read_bytes() == b"AB"  # chunk 3 is dropped: it can't be placed after a hole
    assert info["missing"] == [2] and info["count"] == 2


def test_no_chunks_and_gap_at_zero(tmp_path):
    store = TakeStore(tmp_path)
    tid = store.create({})["id"]
    with pytest.raises(NoChunks):
        store.assemble(tid)
    store.write_chunk(tid, 1, b"x")
    with pytest.raises(NoChunks):
        store.assemble(tid, salvage=True)


def test_archive_and_prune(tmp_path):
    store = TakeStore(tmp_path)
    tid = store.create({})["id"]
    for i in range(5):
        store.write(tid, "edit.json", {"rev": i})
        store.archive(tid, "edit.json", "edit_history", f"rev{i:05d}")
    store.prune(tid, "edit_history", 3)
    assert len(list(store.path(tid, "edit_history").iterdir())) == 3


# ------------------------------------------------------------------ friendly model errors
def _failing(msg, exc=RuntimeError):
    def factory(name, **kw):
        raise exc(msg)
    return factory


def test_model_load_failures_become_short_readable_messages(tmp_path):
    net = FasterWhisperEngine("small.en", "cpu", "int8", model_factory=_failing("HTTP 403 Forbidden from proxy", ConnectionError))
    with pytest.raises(EngineError) as e:
        net.transcribe(tmp_path / "x.wav", AsrOptions())
    msg = str(e.value)
    assert "'small.en'" in msg and "downloads the model" in msg and "ConnectionError" in msg and len(msg) < 450
    assert not net.loaded

    gpu = FasterWhisperEngine("m", "cuda", "float16", model_factory=_failing("Library libcudnn_ops.so.9 is not found"))
    with pytest.raises(EngineError) as e:
        gpu.transcribe(tmp_path / "x.wav", AsrOptions())
    assert "--device cpu" in str(e.value) and "downloads" not in str(e.value)

    odd = FasterWhisperEngine("m", "cpu", model_factory=_failing("something unexpected\nwith a second line"))
    with pytest.raises(EngineError) as e:
        odd.transcribe(tmp_path / "x.wav", AsrOptions())
    assert "[RuntimeError: something unexpected]" in str(e.value) and "second line" not in str(e.value)
