import enum
from dataclasses import dataclass

from pydantic_extra_types.color import Color


@dataclass
class ColorPair:
    light: str
    dark: str


class Palette(ColorPair, enum.Enum):
    """An application color palette that implements an RGBW with light/dark
    color pairs. Colors are based on the Rubin media kit definition of primary
    and accent colors.
    """

    RED = ("#fa6868", "#cf4040")
    ORANGE = ("#ffc036", "#e08d35")
    YELLOW = ("#fff3a1", "#ffb71b")
    GREEN = ("#55da59", "#019305")
    BLUE = ("#00babc", "#058b8c")
    INDIGO = ("#0099d5", "#005684")
    VIOLET = ("#cd84ec", "#652291")
    BLACK = ("#313333", "#1f2121")
    WHITE = ("#f5f5f5", "#dce0e3")
    GREY = ("#6a6e6e", "#6a6e6e")


@dataclass
class StatusDecorator:
    """Dataclass defining attributes for a generic status decorator object that
    may have an associated emoji and color.
    """

    emoji: str
    hex: str
    color: Color = Color("transparent")

    def __post_init__(self) -> None:
        self.color = Color(self.hex)


class StatusDecorators(StatusDecorator, enum.Enum):
    """a tuple value of (icon, fillcolor) for each statusenum"""

    overdue = ("alarm", Palette.BLACK.dark)
    failed = ("error_outline", Palette.RED.dark)
    rejected = ("thumb_down", Palette.RED.dark)
    blocked = ("block", Palette.VIOLET.dark)
    paused = ("pause_circle", Palette.YELLOW.light)
    rescuable = ("support", Palette.ORANGE.light)
    waiting = ("watch_later", Palette.BLUE.dark)
    ready = ("pending_actions", Palette.BLUE.light)
    prepared = ("pending", Palette.INDIGO.dark)
    running = ("run_circle", Palette.ORANGE.light)
    reviewable = ("running_with_errors", Palette.RED.light)
    accepted = ("verified", Palette.GREEN.dark)
    rescued = ("check_circle", Palette.GREEN.dark)
