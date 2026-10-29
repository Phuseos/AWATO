#!/bin/sh
# A Week At The Office, launcher for Linux.
# The game is packed into this file after the script. The first run unpacks it
# into ~/.cache/awato; later runs start straight from there.
set -eu

VERSION="@VERSION@"
BUILD="@BUILD@"
PAYLOAD_LINE=@PAYLOAD_LINE@

CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/awato"
TARGET="$CACHE/$VERSION-$BUILD"
GAME="$TARGET/awato/awato"

if [ ! -x "$GAME" ]; then
    echo "Unpacking A Week At The Office $VERSION..." >&2
    mkdir -p "$CACHE"
    # Remove older versions of the game, nothing else
    find "$CACHE" -mindepth 1 -maxdepth 1 -type d -name '*-*' ! -name "$VERSION-$BUILD" -exec rm -rf {} +
    TMP="$CACHE/.unpacking-$$"
    rm -rf "$TMP"
    mkdir -p "$TMP"
    tail -n +"$PAYLOAD_LINE" "$0" | tar -xzf - -C "$TMP"
    rm -rf "$TARGET"
    mv "$TMP" "$TARGET"
fi

# Started from a file manager: there is no terminal yet, so open one.
if [ ! -t 1 ] && [ $# -eq 0 ] && [ -z "${AWATO_IN_TERMINAL:-}" ] \
        && { [ -n "${DISPLAY:-}" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; }; then
    export AWATO_IN_TERMINAL=1
    for term in x-terminal-emulator gnome-terminal ptyxis konsole xfce4-terminal alacritty kitty wezterm foot xterm; do
        command -v "$term" >/dev/null 2>&1 || continue
        case "$term" in
            gnome-terminal) exec gnome-terminal --geometry=140x42 -- "$GAME" ;;
            ptyxis)         exec ptyxis -- "$GAME" ;;
            xfce4-terminal) exec xfce4-terminal --geometry=140x42 -x "$GAME" ;;
            wezterm)        exec wezterm start -- "$GAME" ;;
            kitty|foot)     exec "$term" "$GAME" ;;
            xterm)          exec xterm -geometry 140x42 -e "$GAME" ;;
            *)              exec "$term" -e "$GAME" ;;
        esac
    done
    echo "No terminal found. Open a terminal and run: $0" >&2
    exit 1
fi

exec "$GAME" "$@"
exit 0
