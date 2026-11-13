"""Running paces.

`Pace` is salvaged from the prototype (D-014). Deriving default paces from a
race result (D-015) is added in T-03.
"""

import re
from dataclasses import dataclass

SECONDS_PER_MINUTE = 60

_PACE_PATTERN = re.compile(r"(\d+):([0-5]\d)")


@dataclass(frozen=True, order=True)
class Pace:
    """A running pace in seconds per kilometre."""

    seconds_per_km: float

    @classmethod
    def parse(cls, text: str) -> "Pace":
        """Parse "m:ss" (per km), e.g. "4:58"."""
        match = _PACE_PATTERN.fullmatch(text.strip())
        if match is None:
            raise ValueError(f'expected a pace like "4:58" (minutes:seconds per km), got "{text}"')
        minutes, seconds = (int(group) for group in match.groups())
        pace = cls(float(minutes * SECONDS_PER_MINUTE + seconds))
        if pace.seconds_per_km == 0:
            raise ValueError("a pace must be greater than 0:00")
        return pace

    def format(self) -> str:
        """Format as "m:ss", rounded to whole seconds."""
        minutes, seconds = divmod(round(self.seconds_per_km), SECONDS_PER_MINUTE)
        return f"{minutes}:{seconds:02d}"
