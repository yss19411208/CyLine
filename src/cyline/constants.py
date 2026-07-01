from .map_catalog import get_map_names


ABILITIES = {
    "camera": "スパイカメラ",
    "cage": "サイバーケージ",
    "wire": "トラップワイヤー",
}

JUMP_LABELS = {
    False: "ジャンプなし",
    True: "ジャンプあり",
}

# Source: Valorant-API map endpoint, mirrored in map_catalog.py.
VALORANT_MAPS = get_map_names()
