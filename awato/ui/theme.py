"""Corporate Memphis palette: flat, saturated pastels on a warm cream ground."""

from textual.theme import Theme

VIOLET = "#6C4CF1"
CORAL = "#FF7A59"
MINT = "#17BFA0"
SUN = "#FFC23D"
SKY = "#4DA8FF"
PINK = "#FF8FC7"
INK = "#2D2A4A"
CREAM = "#FFF6EC"

# Cycled through for stats, confetti and anything else that wants "a colour"
ACCENTS = [VIOLET, CORAL, MINT, SUN, SKY, PINK]

MEMPHIS = Theme(
    name="memphis",
    primary=VIOLET,
    secondary=CORAL,
    accent=MINT,
    warning=SUN,
    error="#F2546B",
    success=MINT,
    foreground=INK,
    background=CREAM,
    surface="#FFFFFF",
    panel="#EFE6FF",
    dark=False,
)

MEMPHIS_NIGHT = Theme(
    name="memphis-night",
    primary="#8B70FF",
    secondary=CORAL,
    accent=MINT,
    warning=SUN,
    error="#FF6B81",
    success=MINT,
    foreground=CREAM,
    background="#1F1B3D",
    surface="#2A2550",
    panel="#353066",
    dark=True,
)
