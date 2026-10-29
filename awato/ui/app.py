"""The Textual app: owns the engine and runs the flow between screens."""

from __future__ import annotations

import random

from textual.app import App
from textual.binding import Binding

from .. import storage
from ..audio import Music
from ..engine import Engine
from ..loader import Content
from .screens import DaySummaryScreen, DialogueScreen, EndingScreen, IntroScreen, OfficeScreen, TitleScreen
from .theme import MEMPHIS, MEMPHIS_NIGHT


class AwatoApp(App):
    CSS_PATH = "awato.tcss"
    TITLE = "A Week At The Office"
    BINDINGS = [
        Binding("m", "toggle_music", "Music"),
        Binding("ctrl+t", "toggle_theme", "Day/night theme", show=False),
    ]

    def __init__(self, content: Content, seed=None, save=True, music=True):
        super().__init__()
        self.content = content
        self.seed = seed
        self.save = save  # Tests turn saving off
        self.meta = storage.load_meta() if save else storage.Meta()
        self.settings = storage.load_settings() if save else {}
        self.music_enabled = music
        self.music: Music | None = None
        self.engine: Engine | None = None
        self.title = content.title

    def on_mount(self):
        self.register_theme(MEMPHIS)
        self.register_theme(MEMPHIS_NIGHT)
        self.theme = "memphis"
        self.music = Music(self.content.music_path if self.music_enabled else None, self.content.music_volume,
                           enabled=not self.settings.get("music_muted", False))
        self.music.start()
        self.push_screen(TitleScreen())

    def on_unmount(self):
        if self.music:
            self.music.stop()

    def is_app_key(self, key):
        """Keys the screens must leave alone so the app-wide bindings work everywhere."""
        return any(key in b.key.split(",") for b in self.BINDINGS)

    def action_toggle_music(self):
        if not self.music.available:
            reason = f": {self.music.error}" if self.music.error else ""
            self.notify(f"Music isn't available{reason}", severity="warning")
            return
        muted = self.music.toggle_mute()
        self.notify("Music off" if muted else "Music on", timeout=1.5)
        self.settings["music_muted"] = muted
        if self.save:
            storage.save_settings(self.settings)

    def action_toggle_theme(self):
        self.theme = "memphis-night" if self.theme == "memphis" else "memphis"

    # ---- flow ----

    def _new_engine(self):
        engine = Engine(self.content, rng=random.Random(self.seed), meta=self.meta)
        if self.save:
            engine.on_day_start = storage.save_game
        return engine

    def has_save(self):
        return self.save and storage.load_game() is not None

    def start_new_game(self, name):
        self.engine = self._new_engine()
        self.engine.new_game(name)
        self.switch_screen(IntroScreen())

    def continue_game(self):
        self.engine = self._new_engine()
        try:
            self.engine.load_state(storage.load_game())
        except (KeyError, TypeError, ValueError):
            storage.delete_save()
            self.notify("That save doesn't fit the current content any more, so it was removed.", severity="error")
            return
        self.enter_office()

    def enter_office(self):
        # OfficeScreen.on_mount calls advance(), so queued scenes attach to the office, not the outgoing screen
        self.switch_screen(OfficeScreen())

    def to_title(self):
        self.engine = None
        self.switch_screen(TitleScreen())

    def act(self, action, *args):
        """Run an engine action from the office, then show whatever it produced."""
        if self.engine.busy:
            return
        action(*args)
        self.advance()

    def advance(self):
        """Show queued scenes, then the day summary, then the ending, one screen at a time."""
        engine = self.engine
        office = self.screen if isinstance(self.screen, OfficeScreen) else None
        if office:
            office.write_log(engine.drain_log())
            office.refresh_all()

        if engine.ending:
            if self.save:
                storage.delete_save()
                storage.save_meta(self.meta)
            self.switch_screen(EndingScreen())
            return

        scene = engine.next_scene()
        if scene:
            def chosen(index):
                engine.choose(scene, index)
                self.advance()
            self.push_screen(DialogueScreen(scene, self.content.typewriter_cps, self.content.t("wrong_option")), chosen)
            return

        if engine.day_over:
            def go_home(_):
                engine.next_day()
                self.advance()
            self.push_screen(DaySummaryScreen(engine), go_home)
