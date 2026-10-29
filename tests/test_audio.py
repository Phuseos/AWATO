import array

import pytest

from awato import audio
from awato.audio import Music


@pytest.fixture(autouse=True)
def silent_audio_device(monkeypatch):
    monkeypatch.setenv("SDL_AUDIODRIVER", "dummy")


def test_trim_silence_keeps_stereo_frames_and_music():
    samples = array.array("h", [0, 0, 1, -1, 500, -500, 300, 300, 0, 0])
    trimmed = audio._trim_silence(samples)
    assert list(trimmed) == [500, -500, 300, 300]


def test_trim_never_cuts_more_than_the_limit():
    limit = int(audio.MAX_TRIM_SECONDS * audio.SAMPLE_RATE) * audio.CHANNELS
    samples = array.array("h", [0] * (limit * 2) + [1000, 1000])
    assert len(audio._trim_silence(samples)) == limit + 2


def test_theme_loads_trims_and_mutes(content):
    pytest.importorskip("pygame")
    music = Music(content.music_path, volume=0.4)
    try:
        assert music.available, music.error
        music.start()
        assert music.channel is not None
        assert music.toggle_mute() is True
        assert music.toggle_mute() is False
    finally:
        music.stop()


def test_bad_file_means_no_music_instead_of_a_crash(tmp_path):
    broken = tmp_path / "broken.mp3"
    broken.write_bytes(b"not an mp3")
    music = Music(broken)
    assert not music.available and music.error
    music.start()
    music.toggle_mute()
    music.stop()


def test_no_path_is_silent():
    music = Music(None)
    assert not music.available and music.error is None
