"""The game rules. No UI code lives here, so the whole game can be played from tests.

The UI calls an action (resolve_ticket, visit, buy, ...), then drains `log`
for narration, shows any queued scenes via next_scene()/choose(), shows the
day summary when `day_over` is set, and the ending screen when `ending` is set.
"""

from __future__ import annotations

import operator
import random
import textwrap
from collections import deque
from dataclasses import asdict, dataclass, field

from .loader import Choice, Content, Ending, Event, Page, as_list, parse_comparison, parse_time

OPS = {">=": operator.ge, "<=": operator.le, ">": operator.gt, "<": operator.lt, "==": operator.eq, "!=": operator.ne}


@dataclass
class Server:
    name: str
    health: int = 100

    @property
    def up(self):
        return self.health > 0


@dataclass
class Employee:
    name: str
    role: str = "helpdesk"


@dataclass
class OpenTicket:
    uid: int
    id: str
    day: int
    time: int


@dataclass
class GameState:
    name: str
    day: int
    time: int
    stats: dict[str, int]
    flags: set[str] = field(default_factory=set)
    seen: dict[str, int] = field(default_factory=dict)  # event id -> times shown
    tickets: list[OpenTicket] = field(default_factory=list)
    servers: list[Server] = field(default_factory=list)
    employees: list[Employee] = field(default_factory=list)
    bought: dict[str, int] = field(default_factory=dict)
    visits: dict[str, int] = field(default_factory=dict)
    next_uid: int = 1
    closed_today: int = 0
    day_start_stats: dict[str, int] = field(default_factory=dict)

    def to_dict(self):
        data = asdict(self)
        data["flags"] = sorted(self.flags)
        return data

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["flags"] = set(data.get("flags", []))
        data["tickets"] = [OpenTicket(**t) for t in data.get("tickets", [])]
        data["servers"] = [Server(**s) for s in data.get("servers", [])]
        data["employees"] = [Employee(**e) for e in data.get("employees", [])]
        return cls(**data)


@dataclass
class Meta:
    """Progress that survives between playthroughs."""
    runs: int = 0
    endings_seen: list[str] = field(default_factory=list)


@dataclass
class Scene:
    event: Event
    pages: list[Page]  # Rendered text
    choices: list[tuple[int, str]]  # (index into event.choices, rendered label); -1 = continue


@dataclass
class LogLine:
    kind: str  # narration | system | good | bad | header
    text: str


class _SafeDict(dict):
    def __missing__(self, key):
        return "{" + key + "}"


class Engine:
    def __init__(self, content: Content, rng: random.Random | None = None, meta: Meta | None = None):
        self.c = content
        self.rng = rng or random.Random()
        self.meta = meta or Meta()
        self.state: GameState | None = None
        self.queue: deque[str] = deque()
        self.log: list[LogLine] = []
        self.day_over = False
        self.ending: Ending | None = None
        self.on_day_start = None  # Hook for autosave, called with the engine

    # ---- setup ----

    def new_game(self, name):
        c = self.c
        self.state = GameState(
            name=name,
            day=1,
            time=c.day_start,
            stats={s.id: s.start for s in c.stats.values()},
            servers=[Server(n) for n in c.servers["start"]],
            employees=[Employee(e["name"], e["role"]) for e in c.team["start"]],
        )
        for ticket_id in c.ticket_rules["start"]:
            self._add_ticket(ticket_id, quiet=True)
        self.start_day()

    def load_state(self, data):
        state = GameState.from_dict(data)
        # The content may have changed since the save was made
        state.stats = {stat.id: state.stats.get(stat.id, stat.start) for stat in self.c.stats.values()}
        state.tickets = [t for t in state.tickets if t.id in self.c.tickets]
        for emp in state.employees:
            if emp.role not in self.c.roles:
                emp.role = "helpdesk"
        self.state = state
        self.start_day()

    def start_day(self):
        s = self.state
        self.queue.clear()
        self.day_over = False
        s.time = self.c.day_start
        s.closed_today = 0
        s.day_start_stats = dict(s.stats)
        if self.on_day_start:
            self.on_day_start(self)
        self.say(self.c.t("day_header"), "header")
        self.say(self.c.t("time_now"), "system")
        self._queue_events("day_start")
        self._check()

    # ---- helpers ----

    @property
    def weekday(self):
        days = self.c.weekdays
        return days[(self.state.day - 1) % len(days)]

    @property
    def last_day(self):
        return len(self.c.weekdays)

    def format_time(self, minutes=None):
        minutes = self.state.time if minutes is None else minutes
        h, m = divmod(minutes, 60)
        if self.c.clock_24h:
            return f"{h:02d}:{m:02d}"
        suffix = "AM" if h < 12 else "PM"
        return f"{(h - 1) % 12 + 1}:{m:02d} {suffix}"

    def render(self, text, **extra):
        s = self.state
        ctx = {"name": s.name if s else "", "day": s.day if s else 1, "weekday": self.weekday if s else "",
               "time": self.format_time() if s else ""}
        if s:
            ctx.update(s.stats)
        ctx.update(extra)
        try:
            return text.format_map(_SafeDict(ctx))
        except (ValueError, IndexError):
            return text

    def say(self, text, kind="narration", **extra):
        if text:
            self.log.append(LogLine(kind, self.render(text, **extra)))

    def drain_log(self):
        lines, self.log = self.log, []
        return lines

    def stat(self, stat_id):
        return self.state.stats.get(stat_id, 0)

    def change_stat(self, stat_id, delta=None, value=None):
        definition = self.c.stats[stat_id]
        new = value if value is not None else self.stat(stat_id) + delta
        if definition.min is not None:
            new = max(definition.min, new)
        if definition.max is not None:
            new = min(definition.max, new)
        self.state.stats[stat_id] = int(new)

    @property
    def servers_down(self):
        return sum(not srv.up for srv in self.state.servers)

    @property
    def busy(self):
        """True while something has to be shown before the player can act again."""
        return bool(self.queue) or self.day_over or self.ending is not None

    # ---- conditions ----

    def check(self, cond) -> bool:
        if not cond:
            return True
        return all(self._check_one(key, value) for key, value in cond.items())

    def _compare(self, actual, spec):
        op, number = parse_comparison(spec)
        return OPS[op](actual, number)

    def _check_one(self, key, value):
        s = self.state
        if key == "day":
            return s.day in as_list(value)
        if key == "after":
            return s.time >= parse_time(value)
        if key == "before":
            return s.time < parse_time(value)
        if key == "flags":
            return all(f in s.flags for f in as_list(value))
        if key == "any_flags":
            return any(f in s.flags for f in as_list(value))
        if key == "not_flags":
            return not any(f in s.flags for f in as_list(value))
        if key == "stats":
            return all(self._compare(self.stat(k), v) for k, v in value.items())
        if key == "seen":
            return all(s.seen.get(e) for e in as_list(value))
        if key == "not_seen":
            return not any(s.seen.get(e) for e in as_list(value))
        if key == "open_tickets":
            return self._compare(len(s.tickets), value)
        if key == "servers_down":
            return self._compare(self.servers_down, value)
        if key == "employees":
            return self._compare(len(s.employees), value)
        if key == "chance":
            return self.rng.random() < value
        if key == "all":
            return all(self.check(sub) for sub in value)
        if key == "any":
            return any(self.check(sub) for sub in value)
        if key == "not":
            return not self.check(value)
        if key == "endings_seen":
            return all(e in self.meta.endings_seen for e in as_list(value))
        if key == "runs":
            return self._compare(self.meta.runs, value)
        raise KeyError(key)

    # ---- effects ----

    def apply(self, effects):
        if not effects:
            return
        s = self.state
        for stat_id, delta in (effects.get("stats") or {}).items():
            self.change_stat(stat_id, delta=delta)
        for stat_id, value in (effects.get("set_stats") or {}).items():
            self.change_stat(stat_id, value=value)
        s.flags.update(as_list(effects.get("set")))
        s.flags.difference_update(as_list(effects.get("clear")))
        for ticket_id in as_list(effects.get("add_ticket")):
            self._add_ticket(ticket_id)
        for ticket_id in as_list(effects.get("remove_ticket")):
            s.tickets = [t for t in s.tickets if t.id != ticket_id]
        if "hire" in effects:
            self._hire(effects["hire"])
        if "add_server" in effects:
            self._add_servers(effects["add_server"])
        if effects.get("repair_servers"):
            for srv in s.servers:
                srv.health = min(100, srv.health + effects["repair_servers"])
        if effects.get("damage_server"):
            up = [srv for srv in s.servers if srv.up]
            if up:
                self._damage(self.rng.choice(up), effects["damage_server"])
        if "log" in effects:
            self.say(effects["log"])
        for event_id in as_list(effects.get("event")):
            self._enqueue(event_id)
        if effects.get("ending"):
            self._finish(self.c.endings[effects["ending"]])
        if effects.get("time"):
            self.pass_time(effects["time"])

    def _add_ticket(self, ticket_id, quiet=False):
        s = self.state
        s.tickets.append(OpenTicket(s.next_uid, ticket_id, s.day, s.time))
        s.next_uid += 1
        if not quiet:
            ticket = self.c.tickets[ticket_id]
            self.say(self.c.t("ticket_arrived"), "system", ticket=self._ticket_title(ticket.id))

    def _ticket_title(self, ticket_id):
        ticket = self.c.tickets[ticket_id]
        return ticket.sender or textwrap.shorten(self.render(ticket.text), 60, placeholder="…")

    def _next_name(self, pool, existing, fallback):
        for name in pool:
            if name not in existing:
                return name
        n = len(existing) + 1
        while f"{fallback} {n}" in existing:
            n += 1
        return f"{fallback} {n}"

    def _hire(self, value):
        s = self.state
        names = []
        if isinstance(value, int):
            for _ in range(value):
                names.append(self._next_name(self.c.team["names"], {e.name for e in s.employees} | set(names), "Employee"))
        else:
            names = [str(n) for n in as_list(value)]
        for name in names:
            s.employees.append(Employee(name, "helpdesk"))
            self.say(self.c.t("employee_hired"), "good", employee=name)

    def _add_servers(self, value):
        s = self.state
        if isinstance(value, int):
            names = []
            for _ in range(value):
                names.append(self._next_name(self.c.servers["names"], {srv.name for srv in s.servers} | set(names), "SRV"))
        else:
            names = [str(n) for n in as_list(value)]
        for name in names:
            s.servers.append(Server(name))
            self.say(self.c.t("server_added"), "good", server=name)

    def _damage(self, server, amount):
        was_up = server.up
        server.health = max(0, server.health - amount)
        if was_up and not server.up:
            self.say(self.c.t("server_down"), "bad", server=server.name)

    # ---- time ----

    def pass_time(self, minutes):
        s = self.state
        if self.day_over or self.ending:
            return
        target = min(s.time + minutes, self.c.day_end)
        while s.time < target and not self.ending:
            next_hour = (s.time // 60 + 1) * 60
            s.time = min(next_hour, target)
            if s.time % 60 == 0:
                self._hourly_tick()
        if s.time >= self.c.day_end and not self.ending:
            self._end_day()

    def _hourly_tick(self):
        s, c = self.state, self.c

        lo, hi = c.servers["decay_per_hour"]
        for srv in s.servers:
            if srv.up:
                self._damage(srv, self.rng.randint(lo, hi))
        for _ in range(self.servers_down):
            self.apply(c.servers["down_penalty"])

        for emp in s.employees:
            if emp.role == "helpdesk":
                delegable = [t for t in s.tickets if c.tickets[t.id].delegable]
                if delegable and self.rng.random() < c.team["helpdesk_chance"]:
                    ticket = delegable[0]
                    s.tickets.remove(ticket)
                    s.closed_today += 1
                    self.say(c.t("employee_closed_ticket"), "good", employee=emp.name, ticket=self._ticket_title(ticket.id))
            elif emp.role == "servers" and s.servers:
                srv = min(s.servers, key=lambda x: x.health)
                if srv.health < 100:
                    was_down = not srv.up
                    srv.health = min(100, srv.health + c.team["server_repair_per_hour"])
                    if was_down and srv.up:
                        self.say(c.t("server_back_up"), "good", server=srv.name)
            elif emp.role == "break":
                self.apply(c.team["break_effects"])

        lo, hi = c.ticket_rules["per_hour"]
        arrivals = self.rng.randint(lo, hi) + self.servers_down * c.ticket_rules["per_down_server"]
        for _ in range(arrivals):
            ticket_id = self._random_ticket()
            if ticket_id:
                self._add_ticket(ticket_id)

    def _random_ticket(self):
        pool = [t for t in self.c.tickets.values() if t.weight > 0 and self.check(t.when)]
        if not pool:
            return None
        return self.rng.choices(pool, weights=[t.weight for t in pool])[0].id

    def _end_day(self):
        self.day_over = True
        self.say(self.c.t("day_over"), "header")
        self._queue_events("day_end")

    def next_day(self):
        """Call after the day summary has been shown."""
        s = self.state
        for _ in s.tickets:
            self.apply(self.c.ticket_rules["overnight_penalty"])
        self.day_over = False
        if self._check_endings():
            return
        if s.day >= self.last_day:
            self._final_ending()
            return
        s.day += 1
        self.start_day()

    # ---- events ----

    def _enqueue(self, event_id):
        if event_id not in self.queue:
            self.queue.append(event_id)

    def _eligible(self, event):
        return (event.repeat or not self.state.seen.get(event.id)) and event.id not in self.queue and self.check(event.when)

    def _queue_events(self, trigger):
        matching = [e for e in self.c.events.values() if e.trigger == trigger and self._eligible(e)]
        for event in sorted(matching, key=lambda e: -e.priority):
            self._enqueue(event.id)

    def _check(self):
        """Run after every action: auto events and game-over endings."""
        if self._check_endings():
            return
        if not self.day_over:
            self._queue_events("auto")

    def _check_endings(self):
        """Game-over endings ('check: always'). Returns True if the game has ended."""
        if not self.ending:
            for ending in self.c.endings.values():
                if ending.check == "always" and self.check(ending.when):
                    self._finish(ending)
                    break
        return self.ending is not None

    def next_scene(self) -> Scene | None:
        if self.ending:
            return None
        while self.queue:
            event = self.c.events[self.queue.popleft()]
            self.state.seen[event.id] = self.state.seen.get(event.id, 0) + 1
            pages = [Page(p.speaker, self.render(p.text)) for p in event.pages]
            choices = [(i, self.render(ch.text)) for i, ch in enumerate(event.choices) if self.check(ch.when)]
            if not choices:
                choices = [(-1, self.c.t("continue"))]
            return Scene(event, pages, choices)
        return None

    def choose(self, scene: Scene, index: int):
        self.apply(scene.event.effects)
        if index >= 0:
            choice = scene.event.choices[index]
            self.say(choice.result)
            self.apply(choice.effects)
        self._check()

    # ---- endings ----

    def _final_ending(self):
        for ending in self.c.endings.values():
            if ending.check == "final" and self.check(ending.when):
                self._finish(ending)
                return

    def _finish(self, ending):
        if self.ending:
            return
        self.ending = ending
        self.queue.clear()
        self.meta.runs += 1
        if ending.id not in self.meta.endings_seen:
            self.meta.endings_seen.append(ending.id)

    def ending_pages(self):
        return [Page(p.speaker, self.render(p.text)) for p in self.ending.pages]

    # ---- player actions ----

    def ticket_view(self, uid):
        """(ticket, rendered text, [(index, label)]) for an open ticket."""
        open_ticket = next(t for t in self.state.tickets if t.uid == uid)
        ticket = self.c.tickets[open_ticket.id]
        choices = ticket.choices if ticket.choices is not None else self.c.default_ticket_choices
        visible = [(i, self.render(ch.text)) for i, ch in enumerate(choices) if self.check(ch.when)]
        return ticket, self.render(ticket.text), visible

    def resolve_ticket(self, uid, index):
        s = self.state
        open_ticket = next(t for t in s.tickets if t.uid == uid)
        ticket = self.c.tickets[open_ticket.id]
        choice: Choice = (ticket.choices if ticket.choices is not None else self.c.default_ticket_choices)[index]
        quick_fix = self.rng.choice(self.c.quick_fix_texts) if self.c.quick_fix_texts else ""
        title = self._ticket_title(ticket.id)
        if choice.result:
            self.say(choice.result, quick_fix=quick_fix, ticket=title)
        if choice.close:
            s.tickets.remove(open_ticket)
            s.closed_today += 1
            self.say(self.c.t("ticket_closed"), "system", ticket=title)
        self.apply(choice.effects)
        self._check()

    def repair_server(self, index):
        srv = self.state.servers[index]
        srv.health = min(100, srv.health + self.c.servers["repair_amount"])
        self.say(self.c.t("server_repaired"), "good", server=srv.name, minutes=self.c.servers["repair_minutes"])
        self.pass_time(self.c.servers["repair_minutes"])
        self._check()

    def assign(self, index, role):
        emp = self.state.employees[index]
        emp.role = role
        self.say(self.c.t("employee_assigned"), "system", employee=emp.name, role=self.c.roles[role])
        self._check()

    def menu(self, which):
        """Locations visible in a menu ('explore' or 'cio')."""
        return [loc for loc in self.c.locations.values() if loc.menu == which and self.check(loc.when)]

    def shop_items(self):
        s = self.state
        return [item for item in self.c.shop.values()
                if self.check(item.when) and (item.limit is None or s.bought.get(item.id, 0) < item.limit)]

    def can_afford(self, item):
        money = self.c.money_stat
        return money is None or self.stat(money) >= item.price

    def buy(self, item_id):
        item = self.c.shop[item_id]
        s = self.state
        if not self.can_afford(item):
            self.say(self.c.t("cannot_afford"), "bad", item=self.render(item.name), price=item.price)
            return
        if self.c.money_stat:
            self.change_stat(self.c.money_stat, delta=-item.price)
        s.bought[item.id] = s.bought.get(item.id, 0) + 1
        self.say(self.c.t("purchased"), "good", item=self.render(item.name), price=item.price)
        self.apply(item.effects)
        self._check()

    def visit(self, location_id):
        loc = self.c.locations[location_id]
        s = self.state
        s.visits[loc.id] = s.visits.get(loc.id, 0) + 1
        event = next((self.c.events[e] for e in loc.events if self._eligible(self.c.events[e])), None)
        if event:
            self._enqueue(event.id)
        else:
            self.say(loc.empty or self.c.t("nothing_here"), location=self.render(loc.name))
        self.apply(loc.effects)
        self.pass_time(loc.time)
        self._check()

    def wait(self, minutes):
        self.say(self.c.t("wait"), "system", minutes=minutes)
        self.pass_time(minutes)
        self._check()

    def go_home(self):
        """Skip to the end of the day. Time still passes, so the office keeps going without you."""
        self.pass_time(self.c.day_end - self.state.time)
        self._check()

    def day_summary(self):
        s = self.state
        changes = []
        for stat in self.c.stats.values():
            if stat.hidden:
                continue
            delta = s.stats[stat.id] - s.day_start_stats.get(stat.id, stat.start)
            changes.append((stat.label, s.stats[stat.id], delta))
        return {
            "closed": s.closed_today,
            "open": len(s.tickets),
            "servers_down": self.servers_down,
            "stats": changes,
        }
