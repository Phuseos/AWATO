"""Background music. Optional: if pygame or an audio device is missing, the game runs silently."""

from __future__ import annotations

import array
import os
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

SAMPLE_RATE = 44100
CHANNELS = 2
# MP3 encoders pad both ends with silence, which is heard as a hiccup every loop.
# Trim up to this much quiet audio from each end; real rests in the music are longer.
MAX_TRIM_SECONDS = 0.15
SILENCE_THRESHOLD = 64  # Out of 32767


def _trim_silence(samples: array.array) -> array.array:
    limit = int(MAX_TRIM_SECONDS * SAMPLE_RATE) * CHANNELS

    def quiet_run(indices):
        count = 0
        for i in indices:
            if abs(samples[i]) > SILENCE_THRESHOLD or count >= limit:
                break
            count += 1
        return count - count % CHANNELS  # Never split a stereo frame

    start = quiet_run(range(len(samples)))
    end = len(samples) - quiet_run(range(len(samples) - 1, -1, -1))
    return samples[start:end] if end > start else samples


class Music:
    def __init__(self, path: Path | None, volume=0.5, enabled=True):
        self.volume = volume
        self.muted = not enabled
        self.sound = None
        self.channel = None
        self.error = None
        if path is None:
            return
        try:
            import pygame

            pygame.mixer.init(frequency=SAMPLE_RATE, size=-16, channels=CHANNELS)
            decoded = pygame.mixer.Sound(str(path))
            samples = _trim_silence(array.array("h", decoded.get_raw()))
            self.sound = pygame.mixer.Sound(buffer=samples.tobytes())
        except Exception as e:  # No pygame, no audio device, unreadable file: play on without music
            self.error = str(e) or type(e).__name__

    @property
    def available(self):
        return self.sound is not None

    def start(self):
        if self.available and self.channel is None:
            self.channel = self.sound.play(loops=-1)
            self._apply_volume()

    def toggle_mute(self):
        self.muted = not self.muted
        self._apply_volume()
        return self.muted

    def _apply_volume(self):
        if self.channel is not None:
            self.channel.set_volume(0 if self.muted else self.volume)

    def stop(self):
        if self.available:
            import pygame

            self.sound.stop()
            self.channel = None
            pygame.mixer.quit()
