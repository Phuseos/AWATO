# Writing for AWATO

All story, dialogue and game text lives in `content/` as YAML. You never need to touch Python.

After every edit, run the checker. It lists mistakes with the file and the path to the broken bit:

```sh
.venv/bin/python -m awato --check
```

- **error**: the game won't start until it's fixed (typo in a key, unknown event, bad time, ...)
- **warning**: probably a mistake (a flag that's checked but never set, an unknown `{placeholder}`)
- **info**: worth knowing (flags set but never used, how many `TODO`s are left)

## Files

| File | What's in it |
|---|---|
| `config.yaml` | Days, clock, stats, starting servers, team and tickets, balancing numbers |
| `text.yaml` | Every interface text: name prompt, intro letter, HR messages, log messages |
| `events/*.yaml` | Story scenes. One file per day is just a convention; any `.yaml` in this folder is loaded |
| `tickets.yaml` | Support tickets, the quick-fix texts and the default ticket choices |
| `locations.yaml` | Places for **Explore** and conversations for **Talk to the CIO** |
| `shop.yaml` | What the CIO sells |
| `endings.yaml` | Endings and when they happen |

## Text

- Plain text, shown exactly as written (no markup).
- A list of strings becomes separate paragraphs.
- Placeholders: `{name}`, `{day}`, `{weekday}`, `{time}` and every stat id (`{funds}`, `{trust}`, ...). Write `{{` / `}}` for a literal brace.
- Quote text that contains `:` or starts with a special character: `text: "Note: it's haunted"`.

## Events

```yaml
monday_morning:              # Unique id, used to refer to the event
  trigger: day_start         # day_start | auto | day_end | manual (default)
  when: {day: 1}             # Condition, see below
  priority: 10               # Higher plays first when several trigger at once
  repeat: false              # true = can play more than once
  pages:
    - speaker: Phus Roda     # Optional; shows a coloured name tag
      text: "First page."
    - "A page without a speaker."
  effects: {...}             # Applied when the scene is finished, before the choice's effects
  choices:                   # Optional; without choices there's a Continue button
    - text: "What the button says"
      when: {flags: met_bea} # Choice only shows when this is true
      result: "Shown in the office log afterwards."
      effects: {stats: {trust: 5}, set: was_nice}
```

Triggers:
- `day_start`: when a day begins
- `auto`: as soon as its `when` becomes true, checked after every player action (use `after: "12:00"` for timed scenes)
- `day_end`: when the clock reaches the end of the day
- `manual`: only when something else plays it (an effect `event: id`, or a location)

Each event plays once unless it has `repeat: true`.

## Conditions (`when:`)

All keys must be true. Combine with `any`, `all` and `not` for anything trickier.

```yaml
when:
  day: 3                      # Or a list: [3, 4]
  after: "13:00"              # Clock is at or past 13:00
  before: "15:00"
  flags: [a, b]               # All set
  any_flags: [a, b]           # At least one set
  not_flags: c                # None set
  stats: {trust: ">= 50", suspicion: "< 80"}   # A bare number means "at least"
  seen: some_event            # Has played
  not_seen: other_event
  open_tickets: ">= 3"
  servers_down: ">= 1"
  employees: "< 3"
  chance: 0.25                # 25%, rolled every time it's checked
  endings_seen: wiped_again   # Reached in an earlier playthrough (New Game+)
  runs: ">= 1"                # Number of finished playthroughs
  any:
    - {flags: a}
    - {stats: {funds: "> 5000"}}
  not: {flags: d}
```

Comparisons: `>=`, `<=`, `>`, `<`, `==`, `!=`.

## Effects (`effects:`)

```yaml
effects:
  stats: {trust: 5, suspicion: -10}   # Add or subtract (clamped to min/max)
  set_stats: {morale: 50}             # Set to an exact value
  set: [flag_a, flag_b]               # Flags are just names; no need to declare them
  clear: flag_c
  time: 30                            # Minutes pass (servers decay, tickets arrive, ...)
  add_ticket: haunted                 # Put a ticket in the inbox
  remove_ticket: haunted
  event: next_scene                   # Play another event right after
  ending: fired                       # End the game now
  hire: 1                             # Or a name: "Bea", or a list of names
  add_server: 1                       # Or a name, or a list
  repair_servers: 30                  # All servers gain health
  damage_server: 50                   # A random working server loses health
  log: "A line for the office log."
```

## Tickets

```yaml
tickets:
  haunted:
    text: "My computer is haunted! Please send an exorsist!"
    from: Accounting            # Optional; shown in the inbox instead of the text
    weight: 1                   # How often it turns up at random; 0 = only via add_ticket
    when: {day: [2, 3]}         # Only arrives when true
    urgent: true                # Red dot in the inbox
    delegable: false            # Employees can't close it on their own
    choices:                    # Optional; otherwise default_choices are used
      - text: "Investigate"
        result: "..."
        effects: {time: 30}
      - text: "Leave it"
        close: false            # Ticket stays open
```

In a ticket choice's `result`, `{quick_fix}` is a random line from `quick_fix_texts` and `{ticket}` is the ticket's title.

## Locations and CIO conversations

```yaml
old_desk:
  name: "The old manager's desk"
  menu: explore          # explore (default) or cio
  description: "..."     # Optional, shown under the name
  when: {flags: has_key} # Only listed when true
  time: 30               # Minutes it costs, even if nothing happens
  effects: {...}         # Applied on every visit
  events: [desk_1, desk_2]   # Plays the first one that can still play
  empty: "Nothing left here."
```

## Shop

```yaml
coffee_machine:
  name: Coffee machine
  description: "..."
  price: 300            # Paid from the stat with money: true
  limit: 1              # How many times it can be bought
  when: {day: 2}
  effects: {stats: {morale: 15}}
```

## Endings

```yaml
wiped_again:
  title: Wiped again
  check: always          # always = checked after every action; final (default) = after the last day
  when: {stats: {suspicion: ">= 100"}}
  pages:
    - "..."
```

Endings are checked from top to bottom; the first match wins. The last `final` ending must have no `when`, so the week always ends somewhere. Endings the player has found are remembered between playthroughs (`endings_seen`, `runs`).

## Stats

Stats are defined in `config.yaml` and can be anything:

```yaml
stats:
  trust: {label: CIO trust, start: 50, min: 0, max: 100, bar: true}
  funds: {label: "Your funds", start: 1000, money: true}
  secret: {label: Secret, start: 0, hidden: true}   # Not shown, still usable in conditions
```
