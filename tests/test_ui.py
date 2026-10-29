import asyncio

from awato.ui.app import AwatoApp
from awato.ui.screens import DaySummaryScreen, DialogueScreen, EndingScreen, IntroScreen, MenuScreen, NameScreen, OfficeScreen, TitleScreen


def run(content, script, size=(140, 42), save=False):
    content.typewriter_cps = 0
    app = AwatoApp(content, seed=1, save=save, music=False)

    async def go():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            await script(app, pilot)

    asyncio.run(go())


async def to_office(pilot):
    await pilot.press("n", *"Phus", "enter", "y", "1")
    await pilot.pause()


def test_name_validation(content):
    async def script(app, pilot):
        await pilot.press("n", "x", "enter")
        await pilot.pause()
        assert isinstance(app.screen, NameScreen)
        assert "Names that short" in str(app.screen.query_one("#name-notice").render())
        await pilot.press("backspace", *"Phus", "enter", "n")
        await pilot.pause()
        assert "Please state your name clearly" in str(app.screen.query_one("#name-notice").render())
        await pilot.press(*"Phus", "enter", "enter")
        await pilot.pause()
        assert isinstance(app.screen, IntroScreen)
        assert app.engine.state.name == "Phus"
    run(content, script)


def test_enter_pages_through_dialogue_without_choosing(content):
    async def script(app, pilot):
        await to_office(pilot)
        assert isinstance(app.screen, DialogueScreen)
        assert app.screen.page == 0
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, DialogueScreen) and app.screen.page == 1
        trust = app.engine.stat("trust")
        await pilot.press("2")
        await pilot.pause()
        assert isinstance(app.screen, OfficeScreen)
        assert app.engine.stat("trust") == trust - 5
    run(content, script)


def test_ticket_menu_and_unknown_keys(content):
    async def script(app, pilot):
        await to_office(pilot)
        await pilot.press("enter", "1")
        await pilot.pause()
        await pilot.press("z")
        await pilot.pause()
        log = "\n".join(str(line.text) for line in app.screen.query_one("#log").lines)
        assert "upset the people in HR" in log
        await pilot.press("1")
        await pilot.pause()
        assert isinstance(app.screen, MenuScreen)
        await pilot.press("z")
        await pilot.pause()
        assert "You bash your fist on the keyboard, typing 'z'" in str(app.screen.query_one(".notice").render())
        await pilot.press("2")
        await pilot.pause()
        assert isinstance(app.screen, OfficeScreen)
        assert app.engine.state.closed_today == 1
    run(content, script)


def test_full_day_reaches_summary_then_tuesday(content):
    async def script(app, pilot):
        await to_office(pilot)
        await pilot.press("enter", "1", "8")
        for _ in range(20):
            await pilot.pause()
            if isinstance(app.screen, DaySummaryScreen):
                break
            await pilot.press("enter")
        assert isinstance(app.screen, DaySummaryScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert app.engine.state.day == 2
    run(content, script)


def test_game_over_shows_ending_and_returns_to_title(content):
    async def script(app, pilot):
        await to_office(pilot)
        await pilot.press("enter", "1")
        await pilot.pause()
        app.engine.apply({"stats": {"suspicion": 100}})
        app.act(app.engine.wait, 30)
        await pilot.pause()
        assert isinstance(app.screen, EndingScreen)
        await pilot.press("enter")
        await pilot.pause()
        assert isinstance(app.screen, TitleScreen)
    run(content, script)


def test_narrow_terminal_does_not_crash(content):
    async def script(app, pilot):
        await to_office(pilot)
        await pilot.press("enter", "1")
        await pilot.pause()
        assert app.screen.has_class("narrow")
    run(content, script, size=(100, 32))


def test_continue_from_save(content):
    async def first(app, pilot):
        await to_office(pilot)
        await pilot.press("enter", "1", "8")
        for _ in range(20):
            await pilot.pause()
            if isinstance(app.screen, DaySummaryScreen):
                break
            await pilot.press("enter")
        await pilot.press("enter")  # Go home: Tuesday starts and autosaves
        await pilot.pause()

    async def second(app, pilot):
        assert app.has_save()
        await pilot.press("c")
        await pilot.pause()
        await pilot.pause()
        assert isinstance(app.screen, (OfficeScreen, DialogueScreen))
        assert app.engine.state.day == 2 and app.engine.state.name == "Phus"

    run(content, first, save=True)
    run(content, second, save=True)


def test_m_key_toggles_music_but_still_types_in_names(content):
    async def script(app, pilot):
        await pilot.press("n", *"Tom", "enter")
        await pilot.pause()
        assert app.screen.pending == "Tom"
        await pilot.press("y", "1")
        await pilot.pause()
        await pilot.press("enter", "1", "m")
        await pilot.pause()
        log = "\n".join(str(line.text) for line in app.screen.query_one("#log").lines)
        assert "upset the people in HR" not in log
    run(content, script)
