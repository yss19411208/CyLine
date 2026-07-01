import unittest
from pathlib import Path

from cyline.minimap import _apply_attacker_up_transform, estimate_player_position


class MinimapDetectionTest(unittest.TestCase):
    def test_ascent_fixture_detects_player_pin_near_a_not_yellow_spike(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        screenshot_path = (
            repo_root
            / "docs"
            / "assets"
            / "lineups"
            / "20260701T021144Z-5c0f1605.webp"
        )
        screenshot_bytes = screenshot_path.read_bytes()

        position_analysis = estimate_player_position(
            screenshot_bytes=screenshot_bytes,
            manual_position=None,
            valorant_map="Unknown",
            maps_dir=repo_root / "docs" / "assets" / "maps",
        )

        self.assertGreater(position_analysis.detected_position.x_percent, 60)
        self.assertLess(position_analysis.detected_position.y_percent, 45)

    def test_ascent_fixture_keeps_display_coordinates_for_fallback(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        screenshot_path = (
            repo_root
            / "docs"
            / "assets"
            / "lineups"
            / "20260701T021144Z-5c0f1605.webp"
        )
        screenshot_bytes = screenshot_path.read_bytes()

        position_analysis = estimate_player_position(
            screenshot_bytes=screenshot_bytes,
            manual_position=None,
            valorant_map="Ascent",
            maps_dir=repo_root / "docs" / "assets" / "maps",
        )

        self.assertGreater(position_analysis.map_position.x_percent, 60)
        self.assertLess(position_analysis.map_position.y_percent, 45)

    def test_ascent_transform_rotates_api_coordinates_to_display_position(self) -> None:
        transformed_x_percent, transformed_y_percent = _apply_attacker_up_transform(
            30.0,
            30.0,
            "Ascent",
        )

        self.assertAlmostEqual(transformed_x_percent, 70.0, places=2)
        self.assertAlmostEqual(transformed_y_percent, 30.0, places=2)


if __name__ == "__main__":
    unittest.main()
