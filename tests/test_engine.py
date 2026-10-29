import random
from collections import Counter

from awato import storage
from awato.engine import Engine, Meta


def play_randomly(engine, rng, max_steps=5000):
    """Make random legal moves until the game ends."""
    for _ in range(max_steps):
        if engine.ending:
            return engine.ending.id
        scene = engine.next_scene()
        if scene:
            engine.choose(scene, rng.choice(scene.choices)[0])
        elif engine.day_over:
            engine.next_day()
        else:
            s = engine.state
            roll = rng.random()
            if roll < 0.4 and s.tickets:
                ticket = rng.choice(s.tickets)
                _, _, choices = engine.ticket_view(ticket.uid)
                engine.resolve_ticket(ticket.uid, rng.choice(choices)[0])
            elif roll < 0.55:
                engine.repair_server(rng.randrange(len(s.servers)))
            elif roll < 0.65 and (places := engine.menu("explore") + engine.menu("cio")):
                engine.visit(rng.choice(places).id)
            elif roll < 0.72 and (items := engine.shop_items()):
                engine.buy(rng.choice(items).id)
            elif roll < 0.78:
                engine.assign(rng.randrange(len(s.employees)), rng.choice(["helpdesk", "servers", "break"]))
            else:
                engine.wait(30)
    raise AssertionError("game did not end")


def test_new_game_starts_monday_morning(engine):
    s = engine.state
    assert (s.day, engine.format_time(), engine.weekday) == (1, "9:00 AM", "Monday")
    assert [t.id for t in s.tickets] == ["not_working"]
    assert s.stats["funds"] == 1000
    lines = [line.text for line in engine.drain_log()]
    assert lines[:2] == ["Day 1: Monday", "The current time is 9:00 AM"]
    assert engine.next_scene().event.id == "monday_morning"


def test_quick_fix_uses_an_original_solution(engine, content):
    uid = engine.state.tickets[0].uid
    engine.drain_log()
    engine.resolve_ticket(uid, 1)
    lines = [line.text for line in engine.drain_log()]
    assert lines[0] in content.quick_fix_texts
    assert engine.state.tickets == [] or all(t.uid != uid for t in engine.state.tickets)
    assert engine.format_time() == "9:15 AM"


def test_every_quick_fix_text_can_appear(content):
    seen = set()
    for seed in range(200):
        e = Engine(content, rng=random.Random(seed))
        e.new_game("x")
        e.drain_log()
        e.resolve_ticket(e.state.tickets[0].uid, 1)
        seen.add(e.drain_log()[0].text)
    assert seen == set(content.quick_fix_texts)


def test_ignoring_a_ticket_keeps_it_open(engine):
    uid = engine.state.tickets[0].uid
    engine.resolve_ticket(uid, 2)
    assert any(t.uid == uid for t in engine.state.tickets)


def test_auto_event_fires_after_noon(engine):
    engine.next_scene()
    engine.wait(150)
    assert "monday_lunch" not in engine.queue
    engine.wait(30)
    assert "monday_lunch" in engine.queue


def test_day_ends_at_five_and_moves_to_next_day(engine):
    engine.queue.clear()
    engine.go_home()
    assert engine.day_over and engine.format_time() == "5:00 PM"
    assert "monday_evening" in engine.queue
    engine.queue.clear()
    engine.next_day()
    assert (engine.state.day, engine.format_time(), engine.day_over) == (2, "9:00 AM", False)


def test_actions_do_nothing_after_day_ends(engine):
    engine.go_home()
    before = engine.state.time
    engine.wait(30)
    assert engine.state.time == before


def test_always_ending_triggers_immediately(engine):
    engine.apply({"stats": {"suspicion": 100}})
    engine._check()
    assert engine.ending.id == "wiped_again"
    assert engine.meta.endings_seen == ["wiped_again"]


def test_final_ending_falls_through_to_fallback(engine):
    engine.state.day = engine.last_day
    engine.state.stats["trust"] = 10
    engine.next_day()
    assert engine.ending.id == "survived"


def test_final_ending_picks_first_match(engine):
    engine.state.day = engine.last_day
    engine.state.stats.update(trust=90, memories=5)
    engine.state.flags.add("found_the_truth")
    engine.next_day()
    assert engine.ending.id == "remembered"


def test_conditions(engine):
    engine.state.flags.add("a")
    assert engine.check({"flags": "a", "not_flags": "b", "day": [1, 2]})
    assert engine.check({"any": [{"flags": "b"}, {"stats": {"funds": ">= 1000"}}]})
    assert not engine.check({"not": {"flags": "a"}})
    assert engine.check({"open_tickets": "== 1", "servers_down": 0, "employees": ">= 1"})
    assert engine.check({"after": "9:00", "before": "10:00"})


def test_stats_are_clamped(engine):
    engine.apply({"stats": {"morale": 500, "suspicion": -50}})
    assert engine.stat("morale") == 100 and engine.stat("suspicion") == 0


def test_location_plays_event_once_then_empty_text(engine):
    engine.queue.clear()
    engine.visit("old_desk")
    assert list(engine.queue) == ["desk_first_look"]
    engine.choose(engine.next_scene(), 0)
    assert "found_basement_key" in engine.state.flags
    assert "basement" in [loc.id for loc in engine.menu("explore")]
    engine.drain_log()
    engine.visit("old_desk")
    assert not engine.queue
    assert engine.drain_log()[0].text == "TODO: nothing left here"


def test_shop(engine):
    engine.buy("server")
    assert engine.stat("funds") == 200 and len(engine.state.servers) == 2
    engine.buy("server")
    assert len(engine.state.servers) == 2
    assert "can't afford" in engine.drain_log()[-1].text


def test_hire_and_assign(engine):
    engine.state.stats["funds"] = 5000
    engine.buy("hire")
    assert [e.name for e in engine.state.employees] == ["Employee 1", "Employee 2"]
    engine.assign(1, "servers")
    assert engine.state.employees[1].role == "servers"


def test_servers_decay_and_go_down(engine):
    srv = engine.state.servers[0]
    srv.health = 1
    engine.c.servers["decay_per_hour"] = [5, 5]
    engine.queue.clear()
    engine.wait(60)
    assert not srv.up and engine.servers_down == 1
    engine.repair_server(0)
    assert srv.up


def test_save_and_load_round_trip(engine, content):
    engine.state.flags.add("something")
    engine.wait(60)
    storage.save_game(engine)
    other = Engine(content, rng=random.Random(2))
    other.load_state(storage.load_game())
    assert other.state.flags == engine.state.flags
    assert other.state.stats == engine.state.stats
    assert other.format_time() == "9:00 AM"  # Saves restart the day


def test_old_save_survives_content_changes(engine, content):
    data = engine.state.to_dict()
    data["stats"]["removed_stat"] = 3
    del data["stats"]["morale"]
    data["tickets"].append({"uid": 99, "id": "deleted_ticket", "day": 1, "time": 540})
    other = Engine(content, rng=random.Random(2))
    other.load_state(data)
    assert other.stat("morale") == content.stats["morale"].start
    assert "removed_stat" not in other.state.stats
    assert all(t.id != "deleted_ticket" for t in other.state.tickets)


def test_meta_round_trip():
    storage.save_meta(Meta(runs=3, endings_seen=["fired"]))
    assert storage.load_meta() == Meta(runs=3, endings_seen=["fired"])


def test_random_playthroughs_always_end(content):
    endings = Counter()
    for seed in range(150):
        e = Engine(content, rng=random.Random(seed))
        e.new_game("Bot")
        endings[play_randomly(e, random.Random(seed))] += 1
    assert set(endings) <= set(content.endings)
    assert len(endings) >= 3, endings
