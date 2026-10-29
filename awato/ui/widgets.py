"""Small reusable widgets and renderers."""

from __future__ import annotations

import random

from rich.text import Text
from textual.widget import Widget

from .theme import ACCENTS, CORAL, MINT, SUN, VIOLET

SHAPES = "●○▲△■□◆◇+×∿"


class Confetti(Widget):
    """Scattered flat shapes, the Corporate Memphis background pattern."""

    DEFAULT_CSS = "Confetti { width: 100%; height: 100%; }"

    def __init__(self, seed=7, density=0.035, **kwargs):
        super().__init__(**kwargs)
        self.seed = seed
        self.density = density

    def render(self):
        rng = random.Random(self.seed)
        width, height = self.size
        text = Text(no_wrap=True, overflow="crop")
        for y in range(height):
            for _ in range(width):
                if rng.random() < self.density:
                    text.append(rng.choice(SHAPES), style=f"bold {rng.choice(ACCENTS)}")
                else:
                    text.append(" ")
            if y < height - 1:
                text.append("\n")
        return text


def bar(value, low, high, colour, width=16):
    """A flat progress bar as rich Text."""
    span = (high - low) or 1
    filled = round(width * (value - low) / span)
    filled = max(0, min(width, filled))
    text = Text()
    text.append("█" * filled, style=colour)
    text.append("█" * (width - filled), style=f"dim {colour}")
    return text


def health_colour(health):
    if health <= 0:
        return CORAL
    if health < 40:
        return SUN
    return MINT


def money(value):
    return f"{value:,}"


def kind_style(kind):
    return {
        "header": f"bold {VIOLET}",
        "system": "dim",
        "good": MINT,
        "bad": f"bold {CORAL}",
    }.get(kind, "")
