from __future__ import annotations

from pathlib import Path
from typing import Any


VALORANT_API_MAP_SOURCE = "https://valorant-api.com/v1/maps"

ATTACKER_UP_TRANSFORMS: dict[str, str] = {
    "Ascent": "rotate_clockwise_90",
}

MAP_CATALOG: list[dict[str, Any]] = [
    {
        "display_name": "Abyss",
        "uuid": "224b0a95-48b9-f703-1bd8-67aca101a61f",
        "display_icon": "https://media.valorant-api.com/maps/224b0a95-48b9-f703-1bd8-67aca101a61f/displayicon.png",
        "x_multiplier": 0.000081,
        "y_multiplier": -0.000081,
        "x_scalar_to_add": 0.5,
        "y_scalar_to_add": 0.5,
    },
    {
        "display_name": "Ascent",
        "uuid": "7eaecc1b-4337-bbf6-6ab9-04b8f06b3319",
        "display_icon": "https://media.valorant-api.com/maps/7eaecc1b-4337-bbf6-6ab9-04b8f06b3319/displayicon.png",
        "x_multiplier": 0.00007,
        "y_multiplier": -0.00007,
        "x_scalar_to_add": 0.813895,
        "y_scalar_to_add": 0.573242,
    },
    {
        "display_name": "Bind",
        "uuid": "2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba",
        "display_icon": "https://media.valorant-api.com/maps/2c9d57ec-4431-9c5e-2939-8f9ef6dd5cba/displayicon.png",
        "x_multiplier": 0.000059,
        "y_multiplier": -0.000059,
        "x_scalar_to_add": 0.576941,
        "y_scalar_to_add": 0.967566,
    },
    {
        "display_name": "Breeze",
        "uuid": "2fb9a4fd-47b8-4e7d-a969-74b4046ebd53",
        "display_icon": "https://media.valorant-api.com/maps/2fb9a4fd-47b8-4e7d-a969-74b4046ebd53/displayicon.png",
        "x_multiplier": 0.00007,
        "y_multiplier": -0.00007,
        "x_scalar_to_add": 0.465123,
        "y_scalar_to_add": 0.833078,
    },
    {
        "display_name": "Corrode",
        "uuid": "1c18ab1f-420d-0d8b-71d0-77ad3c439115",
        "display_icon": "https://media.valorant-api.com/maps/1c18ab1f-420d-0d8b-71d0-77ad3c439115/displayicon.png",
        "x_multiplier": 0.00007,
        "y_multiplier": -0.00007,
        "x_scalar_to_add": 0.526158,
        "y_scalar_to_add": 0.5,
    },
    {
        "display_name": "District",
        "uuid": "690b3ed2-4dff-945b-8223-6da834e30d24",
        "display_icon": "https://media.valorant-api.com/maps/690b3ed2-4dff-945b-8223-6da834e30d24/displayicon.png",
        "x_multiplier": 0.0,
        "y_multiplier": 0.0,
        "x_scalar_to_add": 0.0,
        "y_scalar_to_add": 0.0,
    },
    {
        "display_name": "Drift",
        "uuid": "2c09d728-42d5-30d8-43dc-96a05cc7ee9d",
        "display_icon": "https://media.valorant-api.com/maps/2c09d728-42d5-30d8-43dc-96a05cc7ee9d/displayicon.png",
        "x_multiplier": 0.0,
        "y_multiplier": 0.0,
        "x_scalar_to_add": 0.0,
        "y_scalar_to_add": 0.0,
    },
    {
        "display_name": "Fracture",
        "uuid": "b529448b-4d60-346e-e89e-00a4c527a405",
        "display_icon": "https://media.valorant-api.com/maps/b529448b-4d60-346e-e89e-00a4c527a405/displayicon.png",
        "x_multiplier": 0.000078,
        "y_multiplier": -0.000078,
        "x_scalar_to_add": 0.556952,
        "y_scalar_to_add": 1.155886,
    },
    {
        "display_name": "Glitch",
        "uuid": "d6336a5a-428f-c591-98db-c8a291159134",
        "display_icon": "https://media.valorant-api.com/maps/d6336a5a-428f-c591-98db-c8a291159134/displayicon.png",
        "x_multiplier": 0.0,
        "y_multiplier": 0.0,
        "x_scalar_to_add": 0.0,
        "y_scalar_to_add": 0.0,
    },
    {
        "display_name": "Haven",
        "uuid": "2bee0dc9-4ffe-519b-1cbd-7fbe763a6047",
        "display_icon": "https://media.valorant-api.com/maps/2bee0dc9-4ffe-519b-1cbd-7fbe763a6047/displayicon.png",
        "x_multiplier": 0.000075,
        "y_multiplier": -0.000075,
        "x_scalar_to_add": 1.09345,
        "y_scalar_to_add": 0.642728,
    },
    {
        "display_name": "Icebox",
        "uuid": "e2ad5c54-4114-a870-9641-8ea21279579a",
        "display_icon": "https://media.valorant-api.com/maps/e2ad5c54-4114-a870-9641-8ea21279579a/displayicon.png",
        "x_multiplier": 0.000072,
        "y_multiplier": -0.000072,
        "x_scalar_to_add": 0.460214,
        "y_scalar_to_add": 0.304687,
    },
    {
        "display_name": "Kasbah",
        "uuid": "12452a9d-48c3-0b02-e7eb-0381c3520404",
        "display_icon": "https://media.valorant-api.com/maps/12452a9d-48c3-0b02-e7eb-0381c3520404/displayicon.png",
        "x_multiplier": 0.0,
        "y_multiplier": 0.0,
        "x_scalar_to_add": 0.0,
        "y_scalar_to_add": 0.0,
    },
    {
        "display_name": "Lotus",
        "uuid": "2fe4ed3a-450a-948b-6d6b-e89a78e680a9",
        "display_icon": "https://media.valorant-api.com/maps/2fe4ed3a-450a-948b-6d6b-e89a78e680a9/displayicon.png",
        "x_multiplier": 0.000072,
        "y_multiplier": -0.000072,
        "x_scalar_to_add": 0.454789,
        "y_scalar_to_add": 0.917752,
    },
    {
        "display_name": "Pearl",
        "uuid": "fd267378-4d1d-484f-ff52-77821ed10dc2",
        "display_icon": "https://media.valorant-api.com/maps/fd267378-4d1d-484f-ff52-77821ed10dc2/displayicon.png",
        "x_multiplier": 0.000078,
        "y_multiplier": -0.000078,
        "x_scalar_to_add": 0.480469,
        "y_scalar_to_add": 0.916016,
    },
    {
        "display_name": "Piazza",
        "uuid": "de28aa9b-4cbe-1003-320e-6cb3ec309557",
        "display_icon": "https://media.valorant-api.com/maps/de28aa9b-4cbe-1003-320e-6cb3ec309557/displayicon.png",
        "x_multiplier": 0.0,
        "y_multiplier": 0.0,
        "x_scalar_to_add": 0.0,
        "y_scalar_to_add": 0.0,
    },
    {
        "display_name": "Split",
        "uuid": "d960549e-485c-e861-8d71-aa9d1aed12a2",
        "display_icon": "https://media.valorant-api.com/maps/d960549e-485c-e861-8d71-aa9d1aed12a2/displayicon.png",
        "x_multiplier": 0.000078,
        "y_multiplier": -0.000078,
        "x_scalar_to_add": 0.842188,
        "y_scalar_to_add": 0.697578,
    },
    {
        "display_name": "Summit",
        "uuid": "756da597-416b-c0f2-f47b-afbdf28670bc",
        "display_icon": "https://media.valorant-api.com/maps/756da597-416b-c0f2-f47b-afbdf28670bc/displayicon.png",
        "x_multiplier": 0.000075,
        "y_multiplier": -0.000075,
        "x_scalar_to_add": 0.047401,
        "y_scalar_to_add": 0.978891,
    },
    {
        "display_name": "Sunset",
        "uuid": "92584fbe-486a-b1b2-9faa-39b0f486b498",
        "display_icon": "https://media.valorant-api.com/maps/92584fbe-486a-b1b2-9faa-39b0f486b498/displayicon.png",
        "x_multiplier": 0.000078,
        "y_multiplier": -0.000078,
        "x_scalar_to_add": 0.5,
        "y_scalar_to_add": 0.515625,
    },
]


def map_slug(map_name: str) -> str:
    return "".join(
        character.lower() if character.isalnum() else "-"
        for character in map_name.strip()
    ).strip("-")


def get_map_names() -> list[str]:
    return [metadata["display_name"] for metadata in MAP_CATALOG]


def get_map_metadata(map_name: str) -> dict[str, Any] | None:
    normalized_map_name = map_name.strip().casefold()
    for metadata in MAP_CATALOG:
        if metadata["display_name"].casefold() == normalized_map_name:
            return {
                **metadata,
                "attacker_up_transform": get_attacker_up_transform(metadata["display_name"]),
            }
    return None


def get_map_asset_path(maps_dir: Path, map_name: str) -> Path:
    return maps_dir / f"{map_slug(map_name)}.png"


def get_attacker_up_transform(map_name: str) -> str:
    return ATTACKER_UP_TRANSFORMS.get(map_name, "identity")
