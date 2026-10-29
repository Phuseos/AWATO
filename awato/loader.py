"""Loads the YAML files in content/ into typed objects and validates them.

Validation collects every problem instead of stopping at the first one, so
`python -m awato --check` can show a writer the whole list at once.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parent.parent / "content"

TRIGGERS = ("day_start", "auto", "day_end", "manual")
ROLES = ("helpdesk", "servers", "break")
MENUS = ("explore", "cio")
ENDING_CHECKS = ("always", "final")

CONDITION_KEYS = {
    "day", "after", "before", "flags", "any_flags", "not_flags", "stats", "seen", "not_seen",
    "open_tickets", "servers_down", "employees", "chance", "any", "all", "not",
    "endings_seen", "runs",
}
EFFECT_KEYS = {
    "stats", "set_stats", "set", "clear", "time", "add_ticket", "remove_ticket", "event",
    "ending", "hire", "add_server", "repair_servers", "damage_server", "log",
}
COMPARISON_OPS = (">=", "<=", "!=", "==", ">", "<")

# Placeholders every text can use, on top of one per stat id
BASE_PLACEHOLDERS = {"name", "day", "weekday", "time"}
# Extra placeholders that only exist in specific texts
CONTEXT_PLACEHOLDERS = {"quick_fix", "ticket", "server", "employee", "role", "item", "price", "location", "minutes", "count", "input"}


class ContentError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(str(p) for p in problems if p.level == "error"))


@dataclass
class Problem:
    level: str  # error | warning | info
    where: str
    message: str

    def __str__(self):
        return f"[{self.level}] {self.where}: {self.message}" if self.where else f"[{self.level}] {self.message}"


@dataclass
class StatDef:
    id: str
    label: str
    start: int = 0
    min: int | None = None
    max: int | None = None
    bar: bool = False
    hidden: bool = False
    money: bool = False


@dataclass
class Page:
    speaker: str | None
    text: str


@dataclass
class Choice:
    text: str
    when: dict | None = None
    effects: dict = field(default_factory=dict)
    result: str | None = None
    close: bool = True  # Only used by ticket choices


@dataclass
class Event:
    id: str
    source: str
    trigger: str = "manual"
    when: dict | None = None
    priority: int = 0
    repeat: bool = False
    pages: list[Page] = field(default_factory=list)
    choices: list[Choice] = field(default_factory=list)
    effects: dict = field(default_factory=dict)


@dataclass
class Ticket:
    id: str
    text: str
    sender: str | None = None
    weight: int = 1
    when: dict | None = None
    urgent: bool = False
    delegable: bool = True
    choices: list[Choice] | None = None  # None means use the default choices


@dataclass
class Location:
    id: str
    name: str
    menu: str = "explore"
    description: str | None = None
    when: dict | None = None
    time: int = 30
    effects: dict = field(default_factory=dict)
    events: list[str] = field(default_factory=list)
    empty: str | None = None


@dataclass
class ShopItem:
    id: str
    name: str
    price: int
    description: str | None = None
    limit: int | None = None
    when: dict | None = None
    effects: dict = field(default_factory=dict)


@dataclass
class Ending:
    id: str
    title: str
    check: str = "final"
    when: dict | None = None
    pages: list[Page] = field(default_factory=list)


@dataclass
class Content:
    title: str
    weekdays: list[str]
    day_start: int  # Minutes since midnight
    day_end: int
    clock_24h: bool
    typewriter_cps: int
    music_path: Path | None
    music_volume: float
    stats: dict[str, StatDef]
    servers: dict
    team: dict
    ticket_rules: dict
    roles: dict[str, str]
    text: dict
    events: dict[str, Event]
    tickets: dict[str, Ticket]
    default_ticket_choices: list[Choice]
    quick_fix_texts: list[str]
    locations: dict[str, Location]
    shop: dict[str, ShopItem]
    endings: dict[str, Ending]
    problems: list[Problem] = field(default_factory=list)

    @property
    def money_stat(self):
        return next((s.id for s in self.stats.values() if s.money), None)

    def t(self, key):
        """A UI string from text.yaml. Missing keys show up as the key itself."""
        value = self.text.get(key, key)
        return "\n\n".join(value) if isinstance(value, list) else value


def parse_time(value):
    """'9:00' / '17:30' -> minutes since midnight. Raises ValueError."""
    hours, minutes = str(value).split(":")
    hours, minutes = int(hours), int(minutes)
    if not (0 <= hours < 24 and 0 <= minutes < 60):
        raise ValueError(value)
    return hours * 60 + minutes


def parse_comparison(spec):
    """'>= 50' -> ('>=', 50). A bare number means 'at least'."""
    if isinstance(spec, bool):
        raise ValueError(spec)
    if isinstance(spec, (int, float)):
        return ">=", spec
    text = str(spec).strip()
    for op in COMPARISON_OPS:
        if text.startswith(op):
            return op, float(text[len(op):].strip())
    raise ValueError(spec)


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


class _Loader:
    def __init__(self, root: Path):
        self.root = root
        self.problems: list[Problem] = []
        self.flags_set: dict[str, str] = {}
        self.flags_checked: dict[str, str] = {}
        self.event_refs: dict[str, str] = {}
        self.ticket_refs: dict[str, str] = {}
        self.ending_refs: dict[str, str] = {}
        self.texts: list[tuple[str, str, set]] = []  # (where, text, extra placeholders)
        self.stat_ids: set[str] = set()

    def error(self, where, msg):
        self.problems.append(Problem("error", where, msg))

    def warn(self, where, msg):
        self.problems.append(Problem("warning", where, msg))

    # ---- files ----

    def read(self, rel, required=True):
        path = self.root / rel
        if not path.exists():
            if required:
                self.error(rel, "file is missing")
            return {}
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as e:
            self.error(rel, f"YAML syntax error: {e}")
            return {}
        if data is None:
            return {}
        if not isinstance(data, dict):
            self.error(rel, "the top level must be a mapping of 'key: value' entries")
            return {}
        return data

    def check_keys(self, where, data, allowed):
        if not isinstance(data, dict):
            self.error(where, f"expected a mapping, got {type(data).__name__}")
            return False
        for key in data:
            if key not in allowed:
                self.error(where, f"unknown key '{key}' (allowed: {', '.join(sorted(allowed))})")
        return True

    def get_int(self, where, data, key, default):
        value = data.get(key, default)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
            self.error(where, f"'{key}' must be a whole number")
            return default
        return value

    def text(self, where, value, extra=frozenset(), required=True):
        if value is None:
            if required:
                self.error(where, "text is missing")
            return ""
        if isinstance(value, list) and all(isinstance(v, str) for v in value):
            value = "\n\n".join(value)
        if not isinstance(value, (str, int, float)):
            self.error(where, "text must be a string")
            return ""
        value = str(value)
        self.texts.append((where, value, set(extra)))
        return value

    # ---- conditions & effects ----

    def condition(self, where, cond):
        if cond is None:
            return None
        if not self.check_keys(where, cond, CONDITION_KEYS):
            return None
        for key, value in cond.items():
            w = f"{where} › {key}"
            if key == "day":
                for d in as_list(value):
                    if not isinstance(d, int) or isinstance(d, bool):
                        self.error(w, "days are numbers, e.g. 1 for the first day")
            elif key in ("after", "before"):
                try:
                    parse_time(value)
                except ValueError:
                    self.error(w, f"'{value}' is not a time like '13:30'")
            elif key in ("flags", "any_flags", "not_flags"):
                for flag in as_list(value):
                    self.flags_checked.setdefault(str(flag), w)
            elif key == "stats":
                if self.check_keys(w, value, self.stat_ids):
                    for stat, spec in value.items():
                        try:
                            parse_comparison(spec)
                        except ValueError:
                            self.error(f"{w} › {stat}", f"'{spec}' is not a comparison like '>= 50'")
            elif key in ("seen", "not_seen"):
                for event_id in as_list(value):
                    self.event_refs.setdefault(str(event_id), w)
            elif key in ("open_tickets", "servers_down", "employees", "runs"):
                try:
                    parse_comparison(value)
                except ValueError:
                    self.error(w, f"'{value}' is not a comparison like '>= 2'")
            elif key == "chance":
                if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                    self.error(w, "chance must be a number between 0 and 1, e.g. 0.25")
            elif key in ("any", "all"):
                if not isinstance(value, list):
                    self.error(w, "expected a list of conditions")
                else:
                    for i, sub in enumerate(value):
                        self.condition(f"{w}[{i + 1}]", sub)
            elif key == "not":
                self.condition(w, value)
            elif key == "endings_seen":
                for ending_id in as_list(value):
                    self.ending_refs.setdefault(str(ending_id), w)
        return cond

    def effects(self, where, eff):
        if eff is None:
            return {}
        if not self.check_keys(where, eff, EFFECT_KEYS):
            return {}
        for key, value in eff.items():
            w = f"{where} › {key}"
            if key in ("stats", "set_stats"):
                if self.check_keys(w, value, self.stat_ids):
                    for stat, amount in value.items():
                        if isinstance(amount, bool) or not isinstance(amount, (int, float)):
                            self.error(f"{w} › {stat}", "must be a number")
            elif key == "set":
                for flag in as_list(value):
                    self.flags_set.setdefault(str(flag), w)
            elif key == "clear":
                for flag in as_list(value):
                    self.flags_checked.setdefault(str(flag), w)
            elif key in ("time", "repair_servers", "damage_server"):
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    self.error(w, "must be a positive whole number")
            elif key in ("add_ticket", "remove_ticket"):
                for ticket_id in as_list(value):
                    self.ticket_refs.setdefault(str(ticket_id), w)
            elif key == "event":
                for event_id in as_list(value):
                    self.event_refs.setdefault(str(event_id), w)
            elif key == "ending":
                self.ending_refs.setdefault(str(value), w)
            elif key in ("hire", "add_server"):
                if isinstance(value, bool) or not isinstance(value, (int, str, list)):
                    self.error(w, "use a number, a name, or a list of names")
            elif key == "log":
                self.text(w, value)
        return eff

    def pages(self, where, value):
        pages = []
        for i, page in enumerate(as_list(value)):
            w = f"{where} › pages[{i + 1}]"
            if isinstance(page, str):
                pages.append(Page(None, self.text(w, page)))
            elif self.check_keys(w, page, {"speaker", "text"}):
                pages.append(Page(page.get("speaker"), self.text(w, page.get("text"))))
        return pages

    def choices(self, where, value, ticket=False):
        allowed = {"text", "when", "effects", "result"} | ({"close"} if ticket else set())
        extra = {"quick_fix", "ticket"} if ticket else set()
        out = []
        if value is not None and not isinstance(value, list):
            self.error(where, "choices must be a list")
            return out
        for i, raw in enumerate(value or []):
            w = f"{where} › choices[{i + 1}]"
            if not self.check_keys(w, raw, allowed):
                continue
            out.append(Choice(
                text=self.text(w, raw.get("text"), extra),
                when=self.condition(f"{w} › when", raw.get("when")),
                effects=self.effects(f"{w} › effects", raw.get("effects")),
                result=self.text(f"{w} › result", raw.get("result"), extra, required=False) or None,
                close=bool(raw.get("close", True)),
            ))
        return out

    # ---- sections ----

    def load(self):
        config = self.read("config.yaml")
        text = self.read("text.yaml")
        tickets_file = self.read("tickets.yaml")
        locations_file = self.read("locations.yaml", required=False)
        shop_file = self.read("shop.yaml", required=False)
        endings_file = self.read("endings.yaml")

        self.check_keys("config.yaml", config, {
            "title", "weekdays", "day_start", "day_end", "clock", "typewriter_cps", "music", "stats", "servers", "team", "tickets",
        })
        stats = self.load_stats(config.get("stats") or {})
        self.stat_ids = set(stats)

        try:
            day_start = parse_time(config.get("day_start", "9:00"))
            day_end = parse_time(config.get("day_end", "17:00"))
            if day_end <= day_start:
                self.error("config.yaml › day_end", "must be later than day_start")
        except ValueError:
            self.error("config.yaml", "day_start / day_end must be times like '9:00'")
            day_start, day_end = 540, 1020

        weekdays = config.get("weekdays") or ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        servers = self.load_servers(config.get("servers") or {})
        team = self.load_team(config.get("team") or {})
        ticket_rules = self.load_ticket_rules(config.get("tickets") or {})
        music_path, music_volume = self.load_music(config.get("music") or {})

        for key, value in text.items():
            self.text(f"text.yaml › {key}", value, CONTEXT_PLACEHOLDERS)
        roles = {role: str(text.get(f"role_{role}", role)) for role in ROLES}

        events = self.load_events()
        tickets, default_choices, quick_fix = self.load_tickets(tickets_file)
        locations = self.load_locations(locations_file)
        shop = self.load_shop(shop_file)
        endings = self.load_endings(endings_file)

        for ticket_id in ticket_rules.get("start", []):
            self.ticket_refs.setdefault(str(ticket_id), "config.yaml › tickets › start")

        content = Content(
            title=str(config.get("title", "A Week At The Office")),
            weekdays=[str(d) for d in weekdays],
            day_start=day_start,
            day_end=day_end,
            clock_24h=str(config.get("clock", "12h")) == "24h",
            typewriter_cps=self.get_int("config.yaml", config, "typewriter_cps", 60) or 0,
            music_path=music_path,
            music_volume=music_volume,
            stats=stats,
            servers=servers,
            team=team,
            ticket_rules=ticket_rules,
            roles=roles,
            text=text,
            events=events,
            tickets=tickets,
            default_ticket_choices=default_choices,
            quick_fix_texts=quick_fix,
            locations=locations,
            shop=shop,
            endings=endings,
        )
        self.cross_check(content)
        content.problems = self.problems
        return content

    def load_stats(self, raw):
        stats = {}
        if not isinstance(raw, dict) or not raw:
            self.error("config.yaml › stats", "define at least one stat")
            return stats
        for stat_id, spec in raw.items():
            w = f"config.yaml › stats › {stat_id}"
            if not self.check_keys(w, spec, {"label", "start", "min", "max", "bar", "hidden", "money"}):
                continue
            stats[stat_id] = StatDef(
                id=stat_id,
                label=str(spec.get("label", stat_id)),
                start=self.get_int(w, spec, "start", 0),
                min=self.get_int(w, spec, "min", None),
                max=self.get_int(w, spec, "max", None),
                bar=bool(spec.get("bar", False)),
                hidden=bool(spec.get("hidden", False)),
                money=bool(spec.get("money", False)),
            )
            if stats[stat_id].bar and (stats[stat_id].min is None or stats[stat_id].max is None):
                self.error(w, "a stat with 'bar: true' needs both 'min' and 'max'")
        if sum(s.money for s in stats.values()) > 1:
            self.error("config.yaml › stats", "only one stat can have 'money: true'")
        return stats

    def load_music(self, raw):
        w = "config.yaml › music"
        self.check_keys(w, raw, {"theme", "volume"})
        path = None
        if raw.get("theme"):
            path = self.root / str(raw["theme"])
            if not path.is_file():
                self.warn(f"{w} › theme", f"'{raw['theme']}' not found, the game will be silent")
                path = None
        volume = raw.get("volume", 0.5)
        if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not 0 <= volume <= 1:
            self.error(f"{w} › volume", "must be a number between 0 and 1")
            volume = 0.5
        return path, float(volume)

    def load_servers(self, raw):
        w = "config.yaml › servers"
        self.check_keys(w, raw, {"start", "decay_per_hour", "repair_minutes", "repair_amount", "down_penalty", "names"})
        decay = raw.get("decay_per_hour", [0, 8])
        if not (isinstance(decay, list) and len(decay) == 2 and all(isinstance(d, int) for d in decay)):
            self.error(f"{w} › decay_per_hour", "must be a [min, max] pair of numbers")
            decay = [0, 8]
        return {
            "start": [str(n) for n in as_list(raw.get("start", ["SRV-01"]))],
            "names": [str(n) for n in as_list(raw.get("names", []))],
            "decay_per_hour": decay,
            "repair_minutes": self.get_int(w, raw, "repair_minutes", 60),
            "repair_amount": self.get_int(w, raw, "repair_amount", 50),
            "down_penalty": self.effects(f"{w} › down_penalty", raw.get("down_penalty")),
        }

    def load_team(self, raw):
        w = "config.yaml › team"
        self.check_keys(w, raw, {"start", "names", "helpdesk_chance", "server_repair_per_hour", "break_effects"})
        start = []
        for i, member in enumerate(as_list(raw.get("start"))):
            mw = f"{w} › start[{i + 1}]"
            if isinstance(member, str):
                member = {"name": member}
            if self.check_keys(mw, member, {"name", "role"}):
                role = member.get("role", "helpdesk")
                if role not in ROLES:
                    self.error(mw, f"role must be one of: {', '.join(ROLES)}")
                start.append({"name": str(member.get("name", "Employee")), "role": role})
        chance = raw.get("helpdesk_chance", 0.5)
        if not isinstance(chance, (int, float)) or not 0 <= chance <= 1:
            self.error(f"{w} › helpdesk_chance", "must be between 0 and 1")
            chance = 0.5
        return {
            "start": start,
            "names": [str(n) for n in as_list(raw.get("names", []))],
            "helpdesk_chance": chance,
            "server_repair_per_hour": self.get_int(w, raw, "server_repair_per_hour", 15),
            "break_effects": self.effects(f"{w} › break_effects", raw.get("break_effects")),
        }

    def load_ticket_rules(self, raw):
        w = "config.yaml › tickets"
        self.check_keys(w, raw, {"start", "per_hour", "per_down_server", "overnight_penalty"})
        per_hour = raw.get("per_hour", [0, 1])
        if not (isinstance(per_hour, list) and len(per_hour) == 2 and all(isinstance(d, int) for d in per_hour)):
            self.error(f"{w} › per_hour", "must be a [min, max] pair of numbers")
            per_hour = [0, 1]
        return {
            "start": [str(t) for t in as_list(raw.get("start"))],
            "per_hour": per_hour,
            "per_down_server": self.get_int(w, raw, "per_down_server", 1),
            "overnight_penalty": self.effects(f"{w} › overnight_penalty", raw.get("overnight_penalty")),
        }

    def load_events(self):
        events = {}
        folder = self.root / "events"
        files = sorted(folder.glob("*.yaml")) if folder.is_dir() else []
        if not files:
            self.warn("events/", "no event files found")
        for path in files:
            rel = f"events/{path.name}"
            for event_id, raw in self.read(rel).items():
                w = f"{rel} › {event_id}"
                if event_id in events:
                    self.error(w, f"duplicate event id (also in {events[event_id].source})")
                    continue
                if not self.check_keys(w, raw, {"trigger", "when", "priority", "repeat", "pages", "choices", "effects"}):
                    continue
                trigger = raw.get("trigger", "manual")
                if trigger not in TRIGGERS:
                    self.error(w, f"trigger must be one of: {', '.join(TRIGGERS)}")
                pages = self.pages(w, raw.get("pages"))
                if not pages:
                    self.error(w, "an event needs at least one page of text")
                events[event_id] = Event(
                    id=event_id,
                    source=rel,
                    trigger=trigger,
                    when=self.condition(f"{w} › when", raw.get("when")),
                    priority=self.get_int(w, raw, "priority", 0),
                    repeat=bool(raw.get("repeat", False)),
                    pages=pages,
                    choices=self.choices(w, raw.get("choices")),
                    effects=self.effects(f"{w} › effects", raw.get("effects")),
                )
        return events

    def load_tickets(self, raw):
        self.check_keys("tickets.yaml", raw, {"quick_fix_texts", "default_choices", "tickets"})
        quick_fix = [self.text(f"tickets.yaml › quick_fix_texts[{i + 1}]", t) for i, t in enumerate(as_list(raw.get("quick_fix_texts")))]
        defaults = self.choices("tickets.yaml › default_choices", raw.get("default_choices"), ticket=True)
        if not defaults:
            self.error("tickets.yaml › default_choices", "define at least one default choice")
        tickets = {}
        for ticket_id, spec in (raw.get("tickets") or {}).items():
            w = f"tickets.yaml › tickets › {ticket_id}"
            if not self.check_keys(w, spec, {"text", "from", "weight", "when", "urgent", "delegable", "choices"}):
                continue
            tickets[ticket_id] = Ticket(
                id=ticket_id,
                text=self.text(w, spec.get("text")),
                sender=spec.get("from"),
                weight=self.get_int(w, spec, "weight", 1),
                when=self.condition(f"{w} › when", spec.get("when")),
                urgent=bool(spec.get("urgent", False)),
                delegable=bool(spec.get("delegable", True)),
                choices=self.choices(w, spec["choices"], ticket=True) if "choices" in spec else None,
            )
        if any("{quick_fix}" in (c.result or "") for c in defaults) and not quick_fix:
            self.error("tickets.yaml › quick_fix_texts", "a choice uses {quick_fix} but there are no quick_fix_texts")
        return tickets, defaults, quick_fix

    def load_locations(self, raw):
        locations = {}
        for loc_id, spec in raw.items():
            w = f"locations.yaml › {loc_id}"
            if not self.check_keys(w, spec, {"name", "menu", "description", "when", "time", "effects", "events", "empty"}):
                continue
            menu = spec.get("menu", "explore")
            if menu not in MENUS:
                self.error(w, f"menu must be one of: {', '.join(MENUS)}")
            for event_id in as_list(spec.get("events")):
                self.event_refs.setdefault(str(event_id), w)
            locations[loc_id] = Location(
                id=loc_id,
                name=self.text(f"{w} › name", spec.get("name")),
                menu=menu,
                description=self.text(f"{w} › description", spec.get("description"), required=False) or None,
                when=self.condition(f"{w} › when", spec.get("when")),
                time=self.get_int(w, spec, "time", 30),
                effects=self.effects(f"{w} › effects", spec.get("effects")),
                events=[str(e) for e in as_list(spec.get("events"))],
                empty=self.text(f"{w} › empty", spec.get("empty"), required=False) or None,
            )
        return locations

    def load_shop(self, raw):
        shop = {}
        for item_id, spec in raw.items():
            w = f"shop.yaml › {item_id}"
            if not self.check_keys(w, spec, {"name", "price", "description", "limit", "when", "effects"}):
                continue
            shop[item_id] = ShopItem(
                id=item_id,
                name=self.text(f"{w} › name", spec.get("name")),
                price=self.get_int(w, spec, "price", 0),
                description=self.text(f"{w} › description", spec.get("description"), required=False) or None,
                limit=self.get_int(w, spec, "limit", None),
                when=self.condition(f"{w} › when", spec.get("when")),
                effects=self.effects(f"{w} › effects", spec.get("effects")),
            )
        return shop

    def load_endings(self, raw):
        endings = {}
        for ending_id, spec in raw.items():
            w = f"endings.yaml › {ending_id}"
            if not self.check_keys(w, spec, {"title", "check", "when", "pages"}):
                continue
            check = spec.get("check", "final")
            if check not in ENDING_CHECKS:
                self.error(w, f"check must be one of: {', '.join(ENDING_CHECKS)}")
            if check == "always" and not spec.get("when"):
                self.error(w, "a 'check: always' ending needs a 'when', or it would end the game immediately")
            endings[ending_id] = Ending(
                id=ending_id,
                title=self.text(f"{w} › title", spec.get("title")),
                check=check,
                when=self.condition(f"{w} › when", spec.get("when")),
                pages=self.pages(w, spec.get("pages")),
            )
        finals = [e for e in endings.values() if e.check == "final"]
        if not finals or finals[-1].when:
            self.error("endings.yaml", "the last 'final' ending must have no 'when', so the week always ends somewhere")
        return endings

    # ---- cross references ----

    def cross_check(self, c: Content):
        for event_id, where in self.event_refs.items():
            if event_id not in c.events:
                self.error(where, f"unknown event '{event_id}'")
        for ticket_id, where in self.ticket_refs.items():
            if ticket_id not in c.tickets:
                self.error(where, f"unknown ticket '{ticket_id}'")
        for ending_id, where in self.ending_refs.items():
            if ending_id not in c.endings:
                self.error(where, f"unknown ending '{ending_id}'")

        for flag, where in self.flags_checked.items():
            if flag not in self.flags_set:
                self.warn(where, f"flag '{flag}' is checked but nothing ever sets it")
        for flag, where in self.flags_set.items():
            if flag not in self.flags_checked:
                self.problems.append(Problem("info", where, f"flag '{flag}' is set but never checked"))

        for event in c.events.values():
            if event.trigger == "manual" and event.id not in self.event_refs:
                self.warn(f"{event.source} › {event.id}", "manual event that nothing triggers (no effect 'event:' or location points to it)")
            if event.trigger == "auto" and event.when and "chance" in event.when:
                self.problems.append(Problem("info", f"{event.source} › {event.id}", "auto events re-roll 'chance' after every action"))

        placeholders = BASE_PLACEHOLDERS | self.stat_ids
        formatter = string.Formatter()
        todos = 0
        for where, value, extra in self.texts:
            if "TODO" in value:
                todos += 1
            try:
                fields = {f for _, f, _, _ in formatter.parse(value) if f}
            except ValueError:
                self.error(where, "unbalanced { or } in text (write {{ or }} for a literal brace)")
                continue
            for name in fields - placeholders - extra:
                self.warn(where, f"unknown placeholder {{{name}}}")
        if todos:
            self.problems.append(Problem("info", "", f"{todos} text(s) still contain TODO"))


def load_content(root: Path | str = DEFAULT_CONTENT_DIR, strict=True) -> Content:
    """Load content/. With strict=True, raises ContentError if there are errors."""
    loader = _Loader(Path(root))
    content = loader.load()
    if strict and any(p.level == "error" for p in content.problems):
        raise ContentError(content.problems)
    return content
