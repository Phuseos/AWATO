"""All screens. Screens only display state and forward player input to the engine via the app."""

from __future__ import annotations

from rich.text import Text
from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Button, Footer, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

import zlib

from ..engine import LogLine
from .theme import ACCENTS, CORAL, MINT, SKY, SUN, VIOLET
from .widgets import Confetti, bar, health_colour, kind_style, money


def pill(text, colour, classes=""):
    return Static(Text(text), classes=f"pill {classes}".strip()).set_styles(f"background: {colour};")


def numbered(i, label):
    return Text.assemble((f"{i}", "bold underline"), "\u00a0\u00a0", label)


# ---------------------------------------------------------------- title & setup


class TitleScreen(Screen):
    BINDINGS = [Binding("n", "new", "New game"), Binding("c", "continue", "Continue"), Binding("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        app = self.app
        yield Confetti(seed=11, classes="backdrop")
        with Vertical(id="title-card", classes="card"):
            yield Static(Text("GeneriCorp (inc)", style="bold"), classes="kicker")
            yield Static(Text(app.content.title), id="game-title")
            yield Static(Text(app.content.t("welcome")), classes="muted")
            with Vertical(id="title-buttons"):
                yield Button(Text("New game"), id="new", classes="violet")
                if app.has_save():
                    yield Button(Text("Continue"), id="continue", classes="mint")
                yield Button(Text("Quit"), id="quit", classes="coral")
            total = len(app.content.endings)
            if app.meta.runs:
                yield Static(Text(f"Endings found: {len(app.meta.endings_seen)}/{total}"), classes="muted center")
        yield Footer()

    @on(Button.Pressed, "#new")
    def action_new(self):
        self.app.switch_screen(NameScreen())

    @on(Button.Pressed, "#continue")
    def action_continue(self):
        if self.app.has_save():
            self.app.continue_game()

    @on(Button.Pressed, "#quit")
    def action_quit(self):
        self.app.exit()


class NameScreen(Screen):
    def compose(self) -> ComposeResult:
        c = self.app.content
        yield Confetti(seed=23, density=0.02, classes="backdrop")
        with Vertical(id="name-card", classes="card"):
            yield pill("Onboarding", CORAL)
            yield Static(Text(c.t("name_question")), classes="question")
            yield Input(id="name-input", placeholder="Your name")
            yield Static(id="name-notice", classes="notice")
            with Horizontal(id="confirm-buttons"):
                yield Button(Text("Yes"), id="yes", classes="mint")
                yield Button(Text("No"), id="no", classes="coral")

    def on_mount(self):
        self.pending = None
        self.query_one("#confirm-buttons").display = False
        self.query_one("#name-input").focus()

    def notice(self, text, style=""):
        self.query_one("#name-notice", Static).update(Text(text, style=style))

    @on(Input.Submitted, "#name-input")
    def submitted(self, event: Input.Submitted):
        c = self.app.content
        name = event.value
        if len(name) <= 1:
            # Make sure the name is at least 2 or more characters long
            self.notice(c.t("name_too_short"), f"bold {CORAL}")
            return
        self.pending = name
        self.notice(c.t("name_confirm").format_map({"name": name}))
        event.input.disabled = True
        self.query_one("#confirm-buttons").display = True
        self.query_one("#yes").focus()

    @on(Button.Pressed, "#yes")
    def confirmed(self):
        self.app.start_new_game(self.pending)

    @on(Button.Pressed, "#no")
    def rejected(self):
        self.pending = None
        self.query_one("#confirm-buttons").display = False
        name_input = self.query_one("#name-input", Input)
        name_input.disabled = False
        name_input.value = ""
        name_input.focus()
        self.notice(self.app.content.t("name_retry"), f"bold {CORAL}")

    def on_key(self, event):
        if self.pending is None:
            return
        if event.key in ("y", "enter"):
            event.stop()
            event.prevent_default()
            self.confirmed()
        elif event.key == "n":
            event.stop()
            event.prevent_default()
            self.rejected()


class IntroScreen(Screen):
    """Asks whether to skip the intro, then shows the CIO's welcome letter."""

    def compose(self) -> ComposeResult:
        c = self.app.content
        name = self.app.engine.state.name
        yield Confetti(seed=31, density=0.02, classes="backdrop")
        with Vertical(id="intro-card", classes="card"):
            yield pill("Welcome aboard", MINT)
            yield Static(Text(c.t("name_accepted").format_map({"name": name}), style="bold"), classes="question")
            with Vertical(id="intro-ask"):
                yield Static(Text(c.t("intro_question")))
                with Horizontal(classes="button-row"):
                    yield Button(numbered(1, "Skip"), id="skip", classes="violet")
                    yield Button(numbered(2, "Read it"), id="read", classes="sun")
                yield Static(id="intro-notice", classes="notice")
            with VerticalScroll(id="letter"):
                for paragraph in c.text.get("intro_letter", []):
                    yield Static(Text(paragraph), classes="paragraph")
                yield Static(Text(c.t("press_any_key"), style=f"bold {VIOLET}"))

    def on_mount(self):
        self.reading = False
        self.query_one("#letter").display = False

    @on(Button.Pressed, "#skip")
    def skip(self):
        self.app.enter_office()

    @on(Button.Pressed, "#read")
    def read(self):
        self.reading = True
        self.query_one("#intro-ask").display = False
        letter = self.query_one("#letter")
        letter.display = True
        letter.focus()

    def on_key(self, event):
        if self.app.is_app_key(event.key):
            return
        event.stop()
        event.prevent_default()
        if self.reading:
            if event.key not in ("up", "down", "pageup", "pagedown", "home", "end"):
                self.app.enter_office()
        elif event.key == "1":
            self.skip()
        elif event.key == "2":
            self.read()
        elif event.is_printable:
            self.query_one("#intro-notice", Static).update(Text(self.app.content.t("intro_invalid"), style=CORAL))


# ---------------------------------------------------------------- the office


class OfficeScreen(Screen):
    BINDINGS = [
        Binding("1", "tickets", "Tickets"),
        Binding("2", "team", "Team"),
        Binding("3", "cio", "CIO"),
        Binding("4", "explore", "Explore"),
        Binding("5", "servers", "Servers"),
        Binding("6", "coffee", "Coffee"),
        Binding("8", "go_home", "Go home"),
        Binding("9", "quit_to_title", "Quit"),
    ]
    ACTIONS = [
        ("tickets", "1", "Tickets", "coral"),
        ("team", "2", "Team", "mint"),
        ("cio", "3", "CIO", "violet"),
        ("explore", "4", "Explore", "sky"),
        ("servers", "5", "Servers", "sun"),
        ("coffee", "6", "Coffee", "pink"),
        ("go_home", "8", "Go home", "ink"),
    ]

    def compose(self) -> ComposeResult:
        with Horizontal(id="topbar"):
            yield Static(Text.assemble(("GeneriCorp (inc)", "bold"), "  ·  IT Department"), id="brand")
            yield Static(id="day-pill", classes="pill")
            yield Static(id="time-pill", classes="pill")
        with Horizontal(id="body"):
            with Vertical(id="left"):
                with Vertical(classes="card", id="inbox-card"):
                    yield Static(id="inbox-title", classes="card-title coral-bg")
                    yield OptionList(id="inbox")
                with Vertical(classes="card", id="servers-card"):
                    yield Static(Text("Servers"), classes="card-title sun-bg")
                    yield OptionList(id="servers")
            with Vertical(classes="card", id="center"):
                yield Static(Text("Office log"), classes="card-title violet-bg")
                yield RichLog(id="log", wrap=True, markup=False, auto_scroll=True, min_width=20)
            with Vertical(id="right"):
                with Vertical(classes="card", id="stats-card"):
                    yield Static(id="you-title", classes="card-title sky-bg")
                    yield Static(id="stats")
                with Vertical(classes="card", id="team-card"):
                    yield Static(Text("Team"), classes="card-title mint-bg")
                    yield OptionList(id="team")
        with Horizontal(id="actions"):
            for action, key, label, colour in self.ACTIONS:
                yield Button(numbered(key, label), id=f"act-{action}", classes=colour, action=f"screen.{action}")
        yield Footer()

    def on_mount(self):
        self.refresh_all()
        self.query_one("#inbox").focus()
        self.call_after_refresh(self.app.advance)

    def on_resize(self, event):
        self.set_class(event.size.width < 120, "narrow")

    @property
    def engine(self):
        return self.app.engine

    # -- rendering --

    def refresh_all(self):
        e, c = self.engine, self.app.content
        s = e.state

        self.query_one("#day-pill", Static).update(Text(f"Day {s.day} · {e.weekday}"))
        self.query_one("#time-pill", Static).update(Text(e.format_time()))
        self.query_one("#inbox-title", Static).update(Text(f"Inbox ({len(s.tickets)})"))
        self.query_one("#you-title", Static).update(Text(s.name))

        inbox = self.query_one("#inbox", OptionList)
        options = []
        for t in s.tickets:
            ticket = c.tickets[t.id]
            dot = CORAL if ticket.urgent else VIOLET
            options.append(Option(Text.assemble(("● ", dot), e.render(ticket.sender or ticket.text)), id=f"t{t.uid}"))
        self._fill(inbox, options)

        servers = self.query_one("#servers", OptionList)
        self._fill(servers, [
            Option(Text.assemble(
                (f"{srv.name:<8}", "bold"), bar(srv.health, 0, 100, health_colour(srv.health), 10),
                (" UP " if srv.up else " DOWN ", f"bold {health_colour(srv.health)}"),
            ), id=f"s{i}")
            for i, srv in enumerate(s.servers)
        ])

        team = self.query_one("#team", OptionList)
        self._fill(team, [
            Option(Text.assemble((emp.name, "bold"), "\n  ", (c.roles[emp.role], "dim")), id=f"e{i}")
            for i, emp in enumerate(s.employees)
        ])

        stats = Text()
        visible = [d for d in c.stats.values() if not d.hidden]
        for i, d in enumerate(visible):
            colour = ACCENTS[i % len(ACCENTS)]
            value = s.stats[d.id]
            stats.append(f"{d.label}\n", style="bold")
            if d.bar:
                stats.append_text(bar(value, d.min, d.max, colour))
                stats.append(f" {value}\n")
            else:
                stats.append(money(value) if d.money else str(value), style=f"bold {colour}")
                stats.append("\n")
            if i < len(visible) - 1:
                stats.append("\n")
        self.query_one("#stats", Static).update(stats)

    def _fill(self, option_list: OptionList, options):
        highlighted = option_list.highlighted
        option_list.clear_options()
        option_list.add_options(options)
        if options:
            option_list.highlighted = min(highlighted or 0, len(options) - 1)

    def write_log(self, lines):
        log = self.query_one("#log", RichLog)
        for line in lines:
            if line.kind == "header":
                log.write(Text(""))
            log.write(Text(line.text, style=kind_style(line.kind)))

    def on_key(self, event):
        bound = {b.key for b in self.BINDINGS}
        if event.is_printable and event.character and event.key not in bound and event.character.strip() \
                and not self.app.is_app_key(event.key):
            self.write_log([_line("bad", self.app.content.t("unknown_command"))])

    # -- actions --

    def action_tickets(self):
        inbox = self.query_one("#inbox", OptionList)
        if not self.engine.state.tickets:
            self.write_log([_line("narration", self.app.content.t("nothing_to_do"))])
            return
        index = inbox.highlighted or 0
        self.open_ticket(self.engine.state.tickets[index].uid)

    @on(OptionList.OptionSelected, "#inbox")
    def ticket_selected(self, event):
        self.open_ticket(int(event.option.id[1:]))

    def open_ticket(self, uid):
        c = self.app.content
        ticket, text, choices = self.engine.ticket_view(uid)
        title = ticket.sender or ("Urgent ticket" if ticket.urgent else "Ticket")
        self.app.push_screen(
            MenuScreen(title, [(str(i), label, True) for i, label in choices],
                       body="The open ticket reads: " + text, accent=CORAL if ticket.urgent else VIOLET,
                       invalid=c.t("bash_keyboard"), cancel=False),
            lambda choice: self.app.act(self.engine.resolve_ticket, uid, int(choice)),
        )

    def action_team(self):
        team = self.query_one("#team", OptionList)
        if self.engine.state.employees:
            self.assign(team.highlighted or 0)

    @on(OptionList.OptionSelected, "#team")
    def team_selected(self, event):
        self.assign(int(event.option.id[1:]))

    def assign(self, index):
        c = self.app.content
        emp = self.engine.state.employees[index]
        options = [(role, label, role != emp.role) for role, label in c.roles.items()]
        self.app.push_screen(
            MenuScreen(f"Orders for {emp.name}", options, accent=MINT, invalid=c.t("wrong_option")),
            lambda role: role and self.app.act(self.engine.assign, index, role),
        )

    def action_cio(self):
        e, c = self.engine, self.app.content
        options = [(f"loc:{loc.id}", e.render(loc.name), True) for loc in e.menu("cio")]
        for item in e.shop_items():
            label = Text.assemble(e.render(item.name), (f"  {money(item.price)}", f"bold {VIOLET}"))
            if item.description:
                label.append(f"\n{e.render(item.description)}", style="dim")
            options.append((f"buy:{item.id}", label, e.can_afford(item)))
        self.app.push_screen(
            MenuScreen("Phus Roda, CIO", options, accent=VIOLET, invalid=c.t("wrong_option")),
            self._menu_result,
        )

    def action_explore(self):
        e, c = self.engine, self.app.content
        options = []
        for loc in e.menu("explore"):
            label = Text.assemble(e.render(loc.name), (f"  {loc.time} min", "dim"))
            if loc.description:
                label.append(f"\n{e.render(loc.description)}", style="dim")
            options.append((f"loc:{loc.id}", label, True))
        if not options:
            self.write_log([_line("narration", c.t("nothing_to_do"))])
            return
        self.app.push_screen(MenuScreen("Explore", options, accent=SKY, invalid=c.t("wrong_option")), self._menu_result)

    def _menu_result(self, result):
        if not result:
            return
        kind, _, target = result.partition(":")
        if kind == "loc":
            self.app.act(self.engine.visit, target)
        elif kind == "buy":
            self.app.act(self.engine.buy, target)

    def action_servers(self):
        servers = self.query_one("#servers", OptionList)
        if self.engine.state.servers:
            self.repair(servers.highlighted or 0)

    @on(OptionList.OptionSelected, "#servers")
    def server_selected(self, event):
        self.repair(int(event.option.id[1:]))

    def repair(self, index):
        c = self.app.content
        srv = self.engine.state.servers[index]
        minutes = c.servers["repair_minutes"]
        self.app.push_screen(
            MenuScreen(srv.name, [("repair", f"Patch it up ({minutes} min)", srv.health < 100)],
                       body=f"Health: {srv.health}/100", accent=SUN, invalid=c.t("wrong_option")),
            lambda r: r and self.app.act(self.engine.repair_server, index),
        )

    def action_coffee(self):
        self.app.act(self.engine.wait, 30)

    def action_go_home(self):
        self.app.act(self.engine.go_home)

    def action_quit_to_title(self):
        c = self.app.content
        self.app.push_screen(
            MenuScreen("Quit", [("quit", "Quit to title", True), ("stay", "Keep working", True)],
                       body=c.t("quit_confirm"), accent=CORAL, invalid=c.t("wrong_option")),
            lambda r: r == "quit" and self.app.to_title(),
        )


def _line(kind, text):
    return LogLine(kind, text)


# ---------------------------------------------------------------- modals


class MenuScreen(ModalScreen):
    """A list of numbered options. Dismisses with the chosen option id, or None on Escape."""

    def __init__(self, title, options, body=None, accent=VIOLET, invalid="", cancel=True):
        super().__init__()
        self.menu_title = title
        self.options = options  # [(id, label, enabled)]
        self.body = body
        self.accent = accent
        self.invalid = invalid
        self.cancel = cancel

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog card"):
            yield pill(self.menu_title, self.accent)
            if self.body:
                yield Static(Text(self.body), classes="body")
            with Vertical(classes="choices"):
                for i, (_, label, enabled) in enumerate(self.options):
                    yield Button(numbered(i + 1, label), id=f"opt-{i}", disabled=not enabled, classes="choice")
            yield Static(classes="notice")
            if self.cancel:
                yield Static(Text("Esc to go back", style="dim"), classes="hint")

    def on_mount(self):
        enabled = [b for b in self.query(Button) if not b.disabled]
        if enabled:
            enabled[0].focus()

    @on(Button.Pressed)
    def pressed(self, event):
        self.dismiss(self.options[int(event.button.id.split("-")[1])][0])

    def on_key(self, event):
        if event.key == "escape" and self.cancel:
            event.stop()
            event.prevent_default()
            self.dismiss(None)
        elif event.character and event.character.isdigit() and event.character != "0":
            event.stop()
            event.prevent_default()
            index = int(event.character) - 1
            if index < len(self.options) and self.options[index][2]:
                self.dismiss(self.options[index][0])
            else:
                self._invalid(event.character)
        elif event.is_printable and event.character and event.character.strip() and not self.app.is_app_key(event.key):
            event.stop()
            event.prevent_default()
            self._invalid(event.character)

    def _invalid(self, typed):
        self.query_one(".notice", Static).update(Text(self.invalid.replace("{input}", typed), style=CORAL))


class DialogueScreen(ModalScreen):
    """Plays a scene page by page with a typewriter effect, then offers its choices."""

    AUTO_FOCUS = ""  # Off; otherwise the hidden first choice gets focus and Enter picks it
    BINDINGS = [Binding("enter,space", "advance", "Next", show=False)]

    def __init__(self, scene, cps, invalid):
        super().__init__()
        self.scene = scene
        self.cps = cps
        self.invalid = invalid
        self.page = 0
        self.shown = 0
        self.timer = None

    def compose(self) -> ComposeResult:
        with Vertical(classes="dialog card", id="dialogue"):
            yield Static(classes="pill", id="speaker")
            yield Static(id="page-text", classes="body")
            yield Static(id="pager", classes="hint")
            with Vertical(classes="choices", id="choices"):
                for n, (_, label) in enumerate(self.scene.choices):
                    yield Button(numbered(n + 1, label), id=f"choice-{n}", classes="choice")
            yield Static(classes="notice")

    def on_mount(self):
        self.show_page(0)

    @property
    def last_page(self):
        return self.page >= len(self.scene.pages) - 1

    @property
    def typing(self):
        return self.shown < len(self.scene.pages[self.page].text)

    def show_page(self, index):
        self.page = index
        page = self.scene.pages[index]
        speaker = self.query_one("#speaker", Static)
        speaker.display = bool(page.speaker)
        if page.speaker:
            speaker.update(Text(page.speaker))
            speaker.styles.background = ACCENTS[zlib.crc32(page.speaker.encode()) % len(ACCENTS)]
        self.query_one("#choices").display = False
        self.set_focus(None)
        self.shown = 0 if self.cps else len(page.text)
        if self.timer:
            self.timer.stop()
        if self.cps:
            self.timer = self.set_interval(1 / 30, self._type)
        self._render_page()

    def _type(self):
        self.shown = min(len(self.scene.pages[self.page].text), self.shown + max(1, self.cps // 30))
        self._render_page()

    def _render_page(self):
        text = self.scene.pages[self.page].text
        self.query_one("#page-text", Static).update(Text(text[:self.shown]))
        if not self.typing:
            if self.timer:
                self.timer.stop()
                self.timer = None
            if self.last_page:
                choices = self.query_one("#choices")
                if not choices.display:
                    choices.display = True
                    self.query_one("#choice-0", Button).focus()
        total = len(self.scene.pages)
        hint = "" if self.last_page and not self.typing else "Enter ▸"
        counter = f"{self.page + 1}/{total}   " if total > 1 else ""
        self.query_one("#pager", Static).update(Text(counter + hint, style="dim"))

    def action_advance(self):
        if self.typing:
            self.shown = len(self.scene.pages[self.page].text)
            self._render_page()
        elif not self.last_page:
            self.show_page(self.page + 1)
        elif len(self.scene.choices) == 1:
            self.dismiss(self.scene.choices[0][0])
        else:
            focused = self.focused
            if isinstance(focused, Button):
                focused.press()

    @on(Button.Pressed)
    def pressed(self, event):
        self.dismiss(self.scene.choices[int(event.button.id.split("-")[1])][0])

    def on_key(self, event):
        if not (self.last_page and not self.typing):
            return
        if event.character and event.character.isdigit() and event.character != "0":
            event.stop()
            event.prevent_default()
            index = int(event.character) - 1
            if index < len(self.scene.choices):
                self.dismiss(self.scene.choices[index][0])
            else:
                self._invalid(event.character)
        elif event.is_printable and event.character and event.character.strip() and not self.app.is_app_key(event.key):
            event.stop()
            event.prevent_default()
            self._invalid(event.character)

    def _invalid(self, typed):
        self.query_one(".notice", Static).update(Text(self.invalid.replace("{input}", typed), style=CORAL))


class DaySummaryScreen(ModalScreen):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def compose(self) -> ComposeResult:
        e, c = self.engine, self.engine.c
        summary = e.day_summary()
        final = e.state.day >= e.last_day
        lines = Text()
        lines.append(f"Tickets closed today: {summary['closed']}\n")
        lines.append(f"Tickets still open:   {summary['open']}\n", style=CORAL if summary["open"] else "")
        lines.append(e.render(c.t("employees"), count=len(e.state.employees)) + "\n")
        lines.append(e.render(c.t("servers_available"), count=len(e.state.servers) - summary["servers_down"]) + "\n\n")
        for label, value, delta in summary["stats"]:
            colour = MINT if delta > 0 else CORAL if delta < 0 else "dim"
            lines.append(f"{label:<14}{money(value):>7}  ")
            lines.append(f"{delta:+d}\n" if delta else "·\n", style=colour)
        with Vertical(classes="dialog card", id="summary"):
            yield pill(f"End of {e.weekday}", SUN)
            yield Static(lines, classes="body")
            yield Button(Text("See how your week went" if final else "Go home"), id="home", classes="violet")

    def on_mount(self):
        self.query_one("#home").focus()

    @on(Button.Pressed, "#home")
    def home(self):
        self.dismiss(None)


class EndingScreen(Screen):
    BINDINGS = [Binding("enter", "title", "Main menu"), Binding("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        e = self.app.engine
        meta = self.app.meta
        yield Confetti(seed=zlib.crc32(e.ending.id.encode()), classes="backdrop")
        with Vertical(id="ending-card", classes="card"):
            yield pill("The End", CORAL)
            yield Static(Text(e.render(e.ending.title)), id="game-title")
            with VerticalScroll(id="ending-text"):
                for page in e.ending_pages():
                    if page.speaker:
                        yield Static(Text(page.speaker, style=f"bold {VIOLET}"))
                    yield Static(Text(page.text), classes="paragraph")
            yield Static(Text(f"Endings found: {len(meta.endings_seen)}/{len(e.c.endings)}", style="dim"), classes="center")
            with Horizontal(classes="button-row"):
                yield Button(Text("Main menu"), id="title", classes="violet")
                yield Button(Text("Quit"), id="quit", classes="coral")
        yield Footer()

    @on(Button.Pressed, "#title")
    def action_title(self):
        self.app.to_title()

    @on(Button.Pressed, "#quit")
    def action_quit(self):
        self.app.exit()
