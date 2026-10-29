# A Week At The Office

You're the new IT manager at GeneriCorp (inc). Keep the servers up, the tickets down and the CIO happy, for one week.

A narrative management game for the terminal, built with [Textual](https://textual.textualize.io/).

## Play

Download the game from the [releases](../../releases):

- **Windows:** `AWATO.exe`, double-click it. Windows may warn about an unknown publisher (the game isn't code-signed); choose *More info → Run anyway*.
- **Linux:** `AWATO.sh`, run `sh AWATO.sh` in a terminal, or `chmod +x AWATO.sh` once and double-click it. The first start unpacks the game into `~/.cache/awato`.

A terminal of at least 120×40 looks best.

### From source

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/awato
```

Keys in the office: `1` tickets, `2` team, `3` CIO, `4` explore, `5` servers, `6` coffee break, `8` go home, `9` quit. `M` mutes the music (remembered next time), `Ctrl+T` switches between the day and night themes. The game autosaves at the start of each day.

Options: `--seed N` for a reproducible run, `--content DIR` to load another content folder, `--no-music` to start silent.

## Write

All text and story logic is in [content/](content/). See [WRITING.md](WRITING.md), and run `.venv/bin/awato --check` after editing.

## Develop

```sh
.venv/bin/pytest
```

### Builds

`python scripts/build.py` builds `dist/AWATO.exe` on Windows or `dist/AWATO.sh` on Linux (needs `pip install -e '.[build]'`). `dist/AWATO.sh --self-test` checks a build without a terminal or speakers.

GitHub Actions ([.github/workflows/build.yml](.github/workflows/build.yml)) tests and builds both on every push; the files are under *Artifacts* on the run's page. To publish a release, bump `__version__` in `awato/__init__.py` and push a tag:

```sh
git tag v0.3.0 && git push origin v0.3.0
```

| Path | |
|---|---|
| `awato/loader.py` | Reads and validates `content/` |
| `awato/engine.py` | Game rules, no UI; the tests play whole games through it |
| `awato/audio.py` | Background music via pygame-ce; the game runs silently if audio isn't available |
| `awato/storage.py` | Save game and cross-playthrough progress (JSON in `~/.local/share/awato`) |
| `awato/ui/` | Textual screens and the Corporate Memphis theme (`awato.tcss`, `theme.py`) |
| `scripts/` | Build script, PyInstaller entry point and the Linux launcher template |
