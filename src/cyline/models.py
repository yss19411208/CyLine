from __future__ import annotations

from dataclasses import dataclass

from .constants import ABILITIES, VALORANT_MAPS


@dataclass(frozen=True)
class ManualPosition:
    x_percent: float
    y_percent: float


@dataclass(frozen=True)
class Author:
    source: str
    user_id: str
    display_name: str


@dataclass(frozen=True)
class LineupInput:
    valorant_map: str
    ability: str
    jump: bool
    title: str
    description: str
    manual_position: ManualPosition | None

    def validate(self) -> None:
        if self.valorant_map not in VALORANT_MAPS:
            valid_maps = ", ".join(VALORANT_MAPS)
            raise ValueError(f"Unknown map: {self.valorant_map}. Valid maps: {valid_maps}")

        if self.ability not in ABILITIES:
            valid_abilities = ", ".join(sorted(ABILITIES))
            raise ValueError(
                f"Unknown ability: {self.ability}. Valid abilities: {valid_abilities}"
            )

        if self.manual_position is not None:
            if not 0 <= self.manual_position.x_percent <= 100:
                raise ValueError("manual x position must be between 0 and 100.")

            if not 0 <= self.manual_position.y_percent <= 100:
                raise ValueError("manual y position must be between 0 and 100.")

