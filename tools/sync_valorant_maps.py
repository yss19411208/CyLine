from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

from cyline.map_catalog import (
    MAP_CATALOG,
    VALORANT_API_MAP_SOURCE,
    get_attacker_up_transform,
    map_slug,
)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    maps_dir = repo_root / "docs" / "assets" / "maps"
    data_dir = repo_root / "docs" / "data"
    maps_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    maps_index = []
    for metadata in MAP_CATALOG:
        display_name = metadata["display_name"]
        slug = map_slug(display_name)
        asset_path = maps_dir / f"{slug}.png"
        with urlopen(metadata["display_icon"], timeout=30) as response:
            asset_path.write_bytes(response.read())

        maps_index.append(
            {
                "display_name": display_name,
                "slug": slug,
                "asset_path": f"assets/maps/{slug}.png",
                "source_url": metadata["display_icon"],
                "source": VALORANT_API_MAP_SOURCE,
                "orientation": "attacker_up",
                "attacker_up_transform": get_attacker_up_transform(display_name),
                "x_multiplier": metadata["x_multiplier"],
                "y_multiplier": metadata["y_multiplier"],
                "x_scalar_to_add": metadata["x_scalar_to_add"],
                "y_scalar_to_add": metadata["y_scalar_to_add"],
            }
        )

    (data_dir / "maps.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source": VALORANT_API_MAP_SOURCE,
                "maps": maps_index,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
