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
            raise ValueError(f"不明なマップです: {self.valorant_map}。選択可能: {valid_maps}")

        if self.ability not in ABILITIES:
            valid_abilities = ", ".join(sorted(ABILITIES))
            raise ValueError(
                f"不明なアビリティです: {self.ability}。選択可能: {valid_abilities}"
            )

        if self.manual_position is not None:
            if not 0 <= self.manual_position.x_percent <= 100:
                raise ValueError("手動補正のX座標は0から100の範囲で指定してください。")

            if not 0 <= self.manual_position.y_percent <= 100:
                raise ValueError("手動補正のY座標は0から100の範囲で指定してください。")
