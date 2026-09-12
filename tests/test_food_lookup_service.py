import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from meals.services.food_lookup_service import (
    lookup_ifct,
    lookup_usda,
    resolve_item_macros,
    rescale_item_macros,
)


class TestLookupIfct:
    """Test IFCT bundled dataset lookup."""

    def test_lookup_ifct_exact_match(self):
        """Query exact item name, expect IFCT match with per-100g calories."""
        result = lookup_ifct("Rice, white, cooked")
        assert result is not None
        assert result["item_name"] == "Rice, white, cooked"
        assert result["calories_per_100g"] == 130
        assert result["protein_g_per_100g"] == 2.7
        assert result["source"] == "ifct"

    def test_lookup_ifct_alias_match(self):
        """Query via alias (case-insensitive), expect match."""
        result = lookup_ifct("daal")
        assert result is not None
        assert result["item_name"] == "Daal (Red lentils), cooked"
        assert result["calories_per_100g"] == 101
        assert result["source"] == "ifct"

    def test_lookup_ifct_alias_case_insensitive(self):
        """Alias match should be case-insensitive."""
        result = lookup_ifct("RICE")
        assert result is not None
        assert result["calories_per_100g"] == 130

    def test_lookup_ifct_no_match(self):
        """Query non-existent food, expect None."""
        result = lookup_ifct("xyz_nonexistent_food_123")
        assert result is None

    def test_lookup_ifct_returns_dict_with_all_fields(self):
        """Ensure returned dict has all expected fields."""
        result = lookup_ifct("paneer")
        assert result is not None
        assert "item_name" in result
        assert "calories_per_100g" in result
        assert "protein_g_per_100g" in result
        assert "carbs_g_per_100g" in result
        assert "fats_g_per_100g" in result
        assert "fiber_g_per_100g" in result
        assert "aliases" in result
        assert "source" in result
        assert "source_detail" in result


class TestLookupUsda:
    """Test USDA FDC API lookup."""

    @patch("meals.services.food_lookup_service.requests.get")
    @override_settings(USDA_API_KEY="test_key", USDA_API_BASE_URL="https://test.api")
    def test_lookup_usda_valid_response(self, mock_get):
        """Mock USDA API, expect valid response parsed correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "foods": [
                {
                    "fdcId": 168101,
                    "description": "Banana, raw",
                    "foodNutrients": [
                        {"nutrientId": 1008, "value": 89},  # kcal
                        {"nutrientId": 1003, "value": 1.09},  # protein
                        {"nutrientId": 1005, "value": 23},  # carbs
                        {"nutrientId": 1004, "value": 0.33},  # fats
                        {"nutrientId": 1079, "value": 2.6},  # fiber
                    ],
                }
            ]
        }
        mock_get.return_value = mock_response

        result = lookup_usda("banana")
        assert result is not None
        assert result["item_name"] == "Banana, raw"
        assert result["calories_per_100g"] == 89
        assert result["protein_g_per_100g"] == 1.09
        assert result["source"] == "usda_fdc"
        assert result["fdc_id"] == "168101"

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["api_key"] == "test_key"
        assert call_kwargs["params"]["query"] == "banana"

    @patch("meals.services.food_lookup_service.requests.get")
    @override_settings(USDA_API_KEY="test_key", USDA_API_BASE_URL="https://test.api")
    def test_lookup_usda_no_match(self, mock_get):
        """Mock USDA empty results, expect None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"foods": []}
        mock_get.return_value = mock_response

        result = lookup_usda("xyz_nonexistent_food")
        assert result is None

    @patch("meals.services.food_lookup_service.requests.get")
    @override_settings(USDA_API_KEY="test_key", USDA_API_BASE_URL="https://test.api")
    def test_lookup_usda_timeout(self, mock_get):
        """Mock timeout exception, expect None + warning log (no raise)."""
        import requests
        mock_get.side_effect = requests.Timeout("API timeout")

        result = lookup_usda("banana")
        assert result is None

    @patch("meals.services.food_lookup_service.requests.get")
    @override_settings(USDA_API_KEY="test_key", USDA_API_BASE_URL="https://test.api")
    def test_lookup_usda_invalid_json(self, mock_get):
        """Mock non-JSON response, expect None + warning log."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response

        result = lookup_usda("banana")
        assert result is None

    @override_settings(USDA_API_KEY="")
    def test_lookup_usda_missing_api_key(self):
        """When USDA_API_KEY is empty, lookup returns None."""
        result = lookup_usda("banana")
        assert result is None

    @patch("meals.services.food_lookup_service.requests.get")
    @override_settings(USDA_API_KEY="test_key", USDA_API_BASE_URL="https://test.api")
    def test_lookup_usda_uses_params_dict(self, mock_get):
        """Verify USDA call uses params= dict (not URL interpolation)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"foods": []}
        mock_get.return_value = mock_response

        lookup_usda("test food")

        call_args, call_kwargs = mock_get.call_args
        assert "params" in call_kwargs
        assert call_kwargs["params"]["query"] == "test food"

    @patch("meals.services.food_lookup_service.requests.get")
    @override_settings(USDA_API_KEY="test_key", USDA_API_BASE_URL="https://test.api")
    def test_lookup_usda_api_key_not_logged(self, mock_get, caplog):
        """Verify USDA_API_KEY never appears in logs."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"foods": []}
        mock_get.return_value = mock_response

        with caplog.at_level(logging.WARNING):
            lookup_usda("test food")

        log_output = caplog.text
        assert "test_key" not in log_output


class TestResolveItemMacros:
    """Test the orchestrator function that resolves item nutrition."""

    def test_resolve_item_macros_ifct_priority(self):
        """IFCT match takes priority over USDA."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            with patch("meals.services.food_lookup_service.lookup_usda") as mock_usda:
                mock_ifct.return_value = {
                    "item_name": "Rice",
                    "calories_per_100g": 130,
                    "protein_g_per_100g": 2.7,
                    "carbs_g_per_100g": 28.0,
                    "fats_g_per_100g": 0.3,
                    "fiber_g_per_100g": 0.4,
                    "source": "ifct",
                }
                mock_usda.return_value = {
                    "item_name": "Rice",
                    "calories_per_100g": 135,
                    "protein_g_per_100g": 2.8,
                    "carbs_g_per_100g": 29.0,
                    "fats_g_per_100g": 0.3,
                    "fiber_g_per_100g": 0.4,
                    "source": "usda_fdc",
                }

                item = {
                    "item_name": "rice",
                    "serving_size_grams": 100,
                    "quantity": 1,
                    "unit": "serving",
                    "calories": 100,
                    "protein_g": 2,
                    "carbs_g": 20,
                    "fats_g": 1,
                    "fiber_g": 0.5,
                    "confidence": 0.85,
                }

                result = resolve_item_macros(item)
                assert result["source"] == "ifct"
                assert result["calories"] == 130

                mock_ifct.assert_called_once()
                mock_usda.assert_not_called()

    def test_resolve_item_macros_ifct_miss_then_usda(self):
        """IFCT miss, USDA hit."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            with patch("meals.services.food_lookup_service.lookup_usda") as mock_usda:
                mock_ifct.return_value = None
                mock_usda.return_value = {
                    "item_name": "Banana",
                    "calories_per_100g": 89,
                    "protein_g_per_100g": 1.09,
                    "carbs_g_per_100g": 23,
                    "fats_g_per_100g": 0.33,
                    "fiber_g_per_100g": 2.6,
                    "source": "usda_fdc",
                }

                item = {
                    "item_name": "banana",
                    "serving_size_grams": 100,
                    "quantity": 1,
                    "unit": "serving",
                    "calories": 85,
                    "protein_g": 1,
                    "carbs_g": 20,
                    "fats_g": 0.3,
                    "fiber_g": 2,
                    "confidence": 0.80,
                }

                result = resolve_item_macros(item)
                assert result["source"] == "usda_fdc"
                assert result["calories"] == 89
                mock_usda.assert_called_once()

    def test_resolve_item_macros_no_match_llm_fallback(self):
        """Both IFCT and USDA miss, LLM estimate unchanged."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            with patch("meals.services.food_lookup_service.lookup_usda") as mock_usda:
                mock_ifct.return_value = None
                mock_usda.return_value = None

                item = {
                    "item_name": "unicorn_food",
                    "serving_size_grams": 100,
                    "quantity": 1,
                    "unit": "serving",
                    "calories": 150,
                    "protein_g": 5,
                    "carbs_g": 25,
                    "fats_g": 3,
                    "fiber_g": 1,
                    "confidence": 0.70,
                    "source": "llm_estimate",
                }

                result = resolve_item_macros(item)
                assert result["calories"] == 150
                assert result["source"] == "llm_estimate"
                assert result["confidence"] == 0.70

    def test_resolve_item_macros_scaling_with_serving_size_grams(self):
        """Scale matched data by serving_size_grams."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            mock_ifct.return_value = {
                "item_name": "Rice",
                "calories_per_100g": 130,
                "protein_g_per_100g": 2.7,
                "carbs_g_per_100g": 28.0,
                "fats_g_per_100g": 0.3,
                "fiber_g_per_100g": 0.4,
                "source": "ifct",
            }

            item = {
                "item_name": "rice",
                "serving_size_grams": 200,
                "quantity": 1,
                "unit": "serving",
                "calories": 100,
                "protein_g": 2,
                "carbs_g": 20,
                "fats_g": 1,
                "fiber_g": 0.5,
                "confidence": 0.85,
            }

            result = resolve_item_macros(item)
            assert result["calories"] == 260
            assert result["protein_g"] == 5.4
            assert result["carbs_g"] == 56.0

    def test_resolve_item_macros_scaling_with_unit_grams(self):
        """Scale by quantity + unit when unit is 'g' and serving_size_grams is None."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            mock_ifct.return_value = {
                "item_name": "Rice",
                "calories_per_100g": 130,
                "protein_g_per_100g": 2.7,
                "carbs_g_per_100g": 28.0,
                "fats_g_per_100g": 0.3,
                "fiber_g_per_100g": 0.4,
                "source": "ifct",
            }

            item = {
                "item_name": "rice",
                "serving_size_grams": None,
                "quantity": 150,
                "unit": "g",
                "calories": 100,
                "protein_g": 2,
                "carbs_g": 20,
                "fats_g": 1,
                "fiber_g": 0.5,
                "confidence": 0.85,
            }

            result = resolve_item_macros(item)
            scale = 150 / 100.0
            assert result["calories"] == pytest.approx(130 * scale)
            assert result["protein_g"] == pytest.approx(2.7 * scale)

    def test_resolve_item_macros_no_serving_size_no_weight_unit(self, caplog):
        """No serving_size_grams and non-weight unit (e.g., 'cups'), skip override + log warning."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            mock_ifct.return_value = {
                "item_name": "Rice",
                "calories_per_100g": 130,
                "protein_g_per_100g": 2.7,
                "carbs_g_per_100g": 28.0,
                "fats_g_per_100g": 0.3,
                "fiber_g_per_100g": 0.4,
                "source": "ifct",
            }

            item = {
                "item_name": "rice",
                "serving_size_grams": None,
                "quantity": 2,
                "unit": "cups",
                "calories": 200,
                "protein_g": 3,
                "carbs_g": 35,
                "fats_g": 1,
                "fiber_g": 0.5,
                "confidence": 0.85,
                "source": "llm_estimate",
            }

            with caplog.at_level(logging.WARNING):
                result = resolve_item_macros(item)

            assert result["calories"] == 200
            assert result["source"] == "llm_estimate"
            assert "Cannot scale" in caplog.text

    def test_resolve_item_macros_confidence_floor(self):
        """Matched foods get confidence floored at 0.90."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            mock_ifct.return_value = {
                "item_name": "Rice",
                "calories_per_100g": 130,
                "protein_g_per_100g": 2.7,
                "carbs_g_per_100g": 28.0,
                "fats_g_per_100g": 0.3,
                "fiber_g_per_100g": 0.4,
                "source": "ifct",
            }

            item = {
                "item_name": "rice",
                "serving_size_grams": 100,
                "quantity": 1,
                "unit": "serving",
                "calories": 100,
                "protein_g": 2,
                "carbs_g": 20,
                "fats_g": 1,
                "fiber_g": 0.5,
                "confidence": 0.70,
            }

            result = resolve_item_macros(item)
            assert result["confidence"] == 0.90

    def test_resolve_item_macros_confidence_already_high(self):
        """If confidence already >= 0.90, don't lower it."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            mock_ifct.return_value = {
                "item_name": "Rice",
                "calories_per_100g": 130,
                "protein_g_per_100g": 2.7,
                "carbs_g_per_100g": 28.0,
                "fats_g_per_100g": 0.3,
                "fiber_g_per_100g": 0.4,
                "source": "ifct",
            }

            item = {
                "item_name": "rice",
                "serving_size_grams": 100,
                "quantity": 1,
                "unit": "serving",
                "calories": 100,
                "protein_g": 2,
                "carbs_g": 20,
                "fats_g": 1,
                "fiber_g": 0.5,
                "confidence": 0.95,
            }

            result = resolve_item_macros(item)
            assert result["confidence"] == 0.95

    def test_resolve_item_macros_source_tag_ifct(self):
        """Source should be 'ifct' on IFCT match."""
        with patch("meals.services.food_lookup_service.lookup_ifct") as mock_ifct:
            with patch("meals.services.food_lookup_service.lookup_usda"):
                mock_ifct.return_value = {
                    "item_name": "Rice",
                    "calories_per_100g": 130,
                    "protein_g_per_100g": 2.7,
                    "carbs_g_per_100g": 28.0,
                    "fats_g_per_100g": 0.3,
                    "fiber_g_per_100g": 0.4,
                    "source": "ifct",
                }

                item = {
                    "item_name": "rice",
                    "serving_size_grams": 100,
                    "quantity": 1,
                    "unit": "serving",
                    "calories": 100,
                    "protein_g": 2,
                    "carbs_g": 20,
                    "fats_g": 1,
                    "fiber_g": 0.5,
                }

                result = resolve_item_macros(item)
                assert result["source"] == "ifct"

    def test_resolve_item_macros_empty_item_name(self):
        """Empty item_name should return item unchanged."""
        item = {
            "item_name": "",
            "serving_size_grams": 100,
            "quantity": 1,
            "unit": "serving",
            "calories": 100,
            "protein_g": 2,
            "carbs_g": 20,
            "fats_g": 1,
            "fiber_g": 0.5,
        }

        result = resolve_item_macros(item)
        assert result == item


class TestRescaleItemMacros:
    """Test the rescale_item_macros function for editing saved items."""

    def test_rescale_same_unit_serving(self):
        """Same unit (serving), quantity 1 → 3. Scale = 3."""
        base_macros = {
            "calories": 100.0, "protein_g": 5.0, "carbs_g": 20.0,
            "fats_g": 3.0, "fiber_g": 1.0
        }
        result = rescale_item_macros(
            base_macros, old_quantity=1, old_unit="serving",
            new_quantity=3, new_unit="serving"
        )
        assert result is not None
        assert result["calories"] == pytest.approx(300.0)
        assert result["protein_g"] == pytest.approx(15.0)
        assert result["carbs_g"] == pytest.approx(60.0)
        assert result["fats_g"] == pytest.approx(9.0)
        assert result["fiber_g"] == pytest.approx(3.0)

    def test_rescale_same_unit_piece(self):
        """Same unit (piece), count-based rescale works. 2 pieces → 5 pieces, scale = 2.5."""
        base_macros = {
            "calories": 80.0, "protein_g": 4.0, "carbs_g": 15.0,
            "fats_g": 2.0, "fiber_g": 0.5
        }
        result = rescale_item_macros(
            base_macros, old_quantity=2, old_unit="piece",
            new_quantity=5, new_unit="piece"
        )
        assert result is not None
        assert result["calories"] == pytest.approx(200.0)
        assert result["protein_g"] == pytest.approx(10.0)
        assert result["carbs_g"] == pytest.approx(37.5)
        assert result["fats_g"] == pytest.approx(5.0)
        assert result["fiber_g"] == pytest.approx(1.25)

    def test_rescale_same_unit_gram(self):
        """Same unit (g), quantity 100 → 150. Scale = 1.5."""
        base_macros = {
            "calories": 130.0, "protein_g": 2.7, "carbs_g": 28.0,
            "fats_g": 0.3, "fiber_g": 0.4
        }
        result = rescale_item_macros(
            base_macros, old_quantity=100, old_unit="g",
            new_quantity=150, new_unit="g"
        )
        assert result is not None
        assert result["calories"] == pytest.approx(195.0)
        assert result["protein_g"] == pytest.approx(4.05)
        assert result["carbs_g"] == pytest.approx(42.0)

    def test_rescale_different_unit_g_to_oz(self):
        """Unit change g → oz, both convertible. 100g → 1oz."""
        base_macros = {
            "calories": 130.0, "protein_g": 2.7, "carbs_g": 28.0,
            "fats_g": 0.3, "fiber_g": 0.4
        }
        result = rescale_item_macros(
            base_macros, old_quantity=100, old_unit="g",
            new_quantity=1, new_unit="oz"
        )
        assert result is not None
        assert result["calories"] == pytest.approx(130 * (1 * 28.3495) / (100 * 1))

    def test_rescale_different_unit_cup_to_ml(self):
        """Unit change cup → ml, both convertible. 1 cup → 240ml (same serving size)."""
        base_macros = {
            "calories": 200.0, "protein_g": 8.0, "carbs_g": 40.0,
            "fats_g": 5.0, "fiber_g": 2.0
        }
        result = rescale_item_macros(
            base_macros, old_quantity=1, old_unit="cup",
            new_quantity=240, new_unit="ml"
        )
        assert result is not None
        assert result["calories"] == pytest.approx(200.0)

    def test_rescale_unit_change_piece_to_serving_uses_quantity_ratio(self):
        """Unit change from piece (count) to serving (count). Neither is gram-convertible,
        so fall back to a pure quantity-ratio scale (2 piece -> 1 serving = 0.5x)."""
        base_macros = {
            "calories": 100.0, "protein_g": 5.0, "carbs_g": 20.0,
            "fats_g": 3.0, "fiber_g": 1.0
        }
        result = rescale_item_macros(
            base_macros, old_quantity=2, old_unit="piece",
            new_quantity=1, new_unit="serving"
        )
        assert result is not None
        assert result["calories"] == pytest.approx(50.0)
        assert result["protein_g"] == pytest.approx(2.5)
        assert result["carbs_g"] == pytest.approx(10.0)
        assert result["fats_g"] == pytest.approx(1.5)
        assert result["fiber_g"] == pytest.approx(0.5)

    def test_rescale_unit_change_piece_to_g_fails(self):
        """Unit change from piece (count, no gram equiv) to g. Piece is unconvertible → None."""
        base_macros = {
            "calories": 100.0, "protein_g": 5.0, "carbs_g": 20.0,
            "fats_g": 3.0, "fiber_g": 1.0
        }
        result = rescale_item_macros(
            base_macros, old_quantity=1, old_unit="piece",
            new_quantity=100, new_unit="g"
        )
        assert result is None

    def test_rescale_zero_quantity_fails(self):
        """Old quantity = 0 (div by zero risk) → None."""
        base_macros = {
            "calories": 100.0, "protein_g": 5.0, "carbs_g": 20.0,
            "fats_g": 3.0, "fiber_g": 1.0
        }
        result = rescale_item_macros(
            base_macros, old_quantity=0, old_unit="g",
            new_quantity=100, new_unit="g"
        )
        assert result is None

    def test_rescale_negative_quantity_fails(self):
        """Negative old quantity → None."""
        base_macros = {
            "calories": 100.0, "protein_g": 5.0, "carbs_g": 20.0,
            "fats_g": 3.0, "fiber_g": 1.0
        }
        result = rescale_item_macros(
            base_macros, old_quantity=-1, old_unit="g",
            new_quantity=100, new_unit="g"
        )
        assert result is None

    def test_rescale_case_insensitive_unit(self):
        """Units are normalized to lowercase before comparison."""
        base_macros = {
            "calories": 100.0, "protein_g": 5.0, "carbs_g": 20.0,
            "fats_g": 3.0, "fiber_g": 1.0
        }
        result = rescale_item_macros(
            base_macros, old_quantity=1, old_unit="SERVING",
            new_quantity=2, new_unit="Serving"
        )
        assert result is not None
        assert result["calories"] == pytest.approx(200.0)
