"""Tests for LLM-based meal item refinement (reconciling LLM vs DB estimates)."""

import pytest
from unittest.mock import patch, MagicMock

from meals.services.nutrition_service import items_diverge
from meals.services.llm_service import refine_meal_item, LLMServiceError
from meals.services.food_lookup_service import resolve_and_refine_item


class TestItemsDiverge:
	"""Test the divergence check between LLM and DB estimates."""

	def test_items_diverge_no_divergence(self):
		"""Items with matching macros should not diverge."""
		llm = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5}
		db = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5}
		assert not items_diverge(llm, db, threshold=0.20)

	def test_items_diverge_within_threshold(self):
		"""Items with macros within 20% should not diverge."""
		llm = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5}
		db = {"calories": 115, "protein_g": 11, "carbs_g": 16, "fats_g": 5.5}  # ~15% diff
		assert not items_diverge(llm, db, threshold=0.20)

	def test_items_diverge_exceeds_threshold_calories(self):
		"""Items with calories diverging >20% should diverge."""
		llm = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5}
		db = {"calories": 250, "protein_g": 10, "carbs_g": 15, "fats_g": 5}  # 150% diff
		assert items_diverge(llm, db, threshold=0.20)

	def test_items_diverge_exceeds_threshold_protein(self):
		"""Items with protein diverging >20% should diverge."""
		llm = {"calories": 100, "protein_g": 5, "carbs_g": 15, "fats_g": 5}
		db = {"calories": 100, "protein_g": 15, "carbs_g": 15, "fats_g": 5}  # 200% diff
		assert items_diverge(llm, db, threshold=0.20)

	def test_items_diverge_custom_threshold(self):
		"""Test with a custom threshold."""
		llm = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5}
		db = {"calories": 120, "protein_g": 10, "carbs_g": 15, "fats_g": 5}  # 20% diff
		assert not items_diverge(llm, db, threshold=0.25)
		assert items_diverge(llm, db, threshold=0.15)

	def test_items_diverge_zero_db_value(self):
		"""Test with zero DB value (avoided via epsilon)."""
		llm = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5}
		db = {"calories": 0, "protein_g": 10, "carbs_g": 15, "fats_g": 5}
		# With epsilon, should not raise division by zero
		result = items_diverge(llm, db, threshold=0.20)
		assert isinstance(result, bool)


class TestRefineMealItem:
	"""Test the Groq-based refinement function."""

	@patch('meals.services.llm_service.Groq')
	def test_refine_meal_item_success(self, mock_groq_class):
		"""Test successful refinement call."""
		mock_client = MagicMock()
		mock_groq_class.return_value = mock_client

		refined_json = '{"calories": 150, "protein_g": 12, "carbs_g": 20, "fats_g": 6, "fiber_g": 2, "confidence": 0.92}'
		mock_client.chat.completions.create.return_value = MagicMock(
			choices=[MagicMock(message=MagicMock(content=refined_json))]
		)

		llm_est = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5, "fiber_g": 1}
		db_match = {"calories": 200, "protein_g": 15, "carbs_g": 25, "fats_g": 8, "fiber_g": 3}

		result = refine_meal_item("chicken", 100, "g", llm_est, db_match, "usda_fdc")

		assert result["calories"] == 150
		assert result["protein_g"] == 12
		assert result["confidence"] == 0.92

	@patch('meals.services.llm_service.Groq')
	def test_refine_meal_item_strips_markdown_fences(self, mock_groq_class):
		"""Test that markdown fences are stripped from LLM response."""
		mock_client = MagicMock()
		mock_groq_class.return_value = mock_client

		# Response with markdown fences
		refined_json = '```json\n{"calories": 150, "protein_g": 12, "carbs_g": 20, "fats_g": 6, "fiber_g": 2, "confidence": 0.92}\n```'
		mock_client.chat.completions.create.return_value = MagicMock(
			choices=[MagicMock(message=MagicMock(content=refined_json))]
		)

		llm_est = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5, "fiber_g": 1}
		db_match = {"calories": 200, "protein_g": 15, "carbs_g": 25, "fats_g": 8, "fiber_g": 3}

		result = refine_meal_item("chicken", 100, "g", llm_est, db_match, "ifct")

		assert result["calories"] == 150

	@patch('meals.services.llm_service.Groq')
	def test_refine_meal_item_invalid_json(self, mock_groq_class):
		"""Test that invalid JSON raises LLMServiceError."""
		mock_client = MagicMock()
		mock_groq_class.return_value = mock_client

		mock_client.chat.completions.create.return_value = MagicMock(
			choices=[MagicMock(message=MagicMock(content='not valid json'))]
		)

		llm_est = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5, "fiber_g": 1}
		db_match = {"calories": 200, "protein_g": 15, "carbs_g": 25, "fats_g": 8, "fiber_g": 3}

		with pytest.raises(LLMServiceError, match="invalid JSON"):
			refine_meal_item("chicken", 100, "g", llm_est, db_match, "usda_fdc")

	@patch('meals.services.llm_service.Groq')
	def test_refine_meal_item_missing_required_field(self, mock_groq_class):
		"""Test that missing required fields raise LLMServiceError."""
		mock_client = MagicMock()
		mock_groq_class.return_value = mock_client

		# Missing confidence field
		refined_json = '{"calories": 150, "protein_g": 12, "carbs_g": 20, "fats_g": 6, "fiber_g": 2}'
		mock_client.chat.completions.create.return_value = MagicMock(
			choices=[MagicMock(message=MagicMock(content=refined_json))]
		)

		llm_est = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5, "fiber_g": 1}
		db_match = {"calories": 200, "protein_g": 15, "carbs_g": 25, "fats_g": 8, "fiber_g": 3}

		with pytest.raises(LLMServiceError, match="missing required field"):
			refine_meal_item("chicken", 100, "g", llm_est, db_match, "usda_fdc")

	@patch('meals.services.llm_service.Groq')
	def test_refine_meal_item_negative_value(self, mock_groq_class):
		"""Test that negative macro values raise LLMServiceError."""
		mock_client = MagicMock()
		mock_groq_class.return_value = mock_client

		refined_json = '{"calories": -150, "protein_g": 12, "carbs_g": 20, "fats_g": 6, "fiber_g": 2, "confidence": 0.92}'
		mock_client.chat.completions.create.return_value = MagicMock(
			choices=[MagicMock(message=MagicMock(content=refined_json))]
		)

		llm_est = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5, "fiber_g": 1}
		db_match = {"calories": 200, "protein_g": 15, "carbs_g": 25, "fats_g": 8, "fiber_g": 3}

		with pytest.raises(LLMServiceError, match="negative"):
			refine_meal_item("chicken", 100, "g", llm_est, db_match, "usda_fdc")

	@patch('meals.services.llm_service.Groq')
	def test_refine_meal_item_invalid_confidence(self, mock_groq_class):
		"""Test that confidence outside [0, 1] raises LLMServiceError."""
		mock_client = MagicMock()
		mock_groq_class.return_value = mock_client

		refined_json = '{"calories": 150, "protein_g": 12, "carbs_g": 20, "fats_g": 6, "fiber_g": 2, "confidence": 1.5}'
		mock_client.chat.completions.create.return_value = MagicMock(
			choices=[MagicMock(message=MagicMock(content=refined_json))]
		)

		llm_est = {"calories": 100, "protein_g": 10, "carbs_g": 15, "fats_g": 5, "fiber_g": 1}
		db_match = {"calories": 200, "protein_g": 15, "carbs_g": 25, "fats_g": 8, "fiber_g": 3}

		with pytest.raises(LLMServiceError, match="Confidence out of range"):
			refine_meal_item("chicken", 100, "g", llm_est, db_match, "usda_fdc")


class TestResolveAndRefineItem:
	"""Test the orchestration wrapper resolve_and_refine_item."""

	@patch('meals.services.llm_service.refine_meal_item')
	@patch('meals.services.food_lookup_service.resolve_item_macros')
	def test_resolve_and_refine_no_db_match(self, mock_resolve, mock_refine):
		"""If no DB match, refinement should not be called."""
		# resolve_item_macros returns item unchanged (no DB match)
		item = {
			"item_name": "mystery_food",
			"quantity": 100,
			"unit": "g",
			"calories": 50,
			"protein_g": 5,
			"carbs_g": 10,
			"fats_g": 2,
			"fiber_g": 0,
		}
		mock_resolve.return_value = item

		result = resolve_and_refine_item(item)

		# resolve was called, but refine should not have been
		mock_resolve.assert_called_once()
		mock_refine.assert_not_called()
		assert result == item

	@patch('meals.services.llm_service.refine_meal_item')
	@patch('meals.services.food_lookup_service.resolve_item_macros')
	def test_resolve_and_refine_no_divergence(self, mock_resolve, mock_refine):
		"""If DB match but no divergence, refinement should not be called."""
		item = {
			"item_name": "chicken",
			"quantity": 100,
			"unit": "g",
			"calories": 165,
			"protein_g": 31,
			"carbs_g": 0,
			"fats_g": 3.6,
			"fiber_g": 0,
		}
		resolved = {
			"item_name": "chicken breast",
			"quantity": 100,
			"unit": "g",
			"calories": 165,  # ~same
			"protein_g": 31,  # ~same
			"carbs_g": 0,
			"fats_g": 3.6,
			"fiber_g": 0,
			"source": "usda_fdc",
			"confidence": 0.95,
		}
		mock_resolve.return_value = resolved

		result = resolve_and_refine_item(item)

		# resolve was called, but refine should not have been (values agree)
		mock_resolve.assert_called_once()
		mock_refine.assert_not_called()
		assert result == resolved

	@patch('meals.services.llm_service.refine_meal_item')
	@patch('meals.services.food_lookup_service.resolve_item_macros')
	def test_resolve_and_refine_divergence_triggers_refinement(self, mock_resolve, mock_refine):
		"""If DB match and values diverge, refinement should be called."""
		item = {
			"item_name": "chicken",
			"quantity": 100,
			"unit": "g",
			"calories": 100,  # LLM guess
			"protein_g": 10,
			"carbs_g": 5,
			"fats_g": 2,
			"fiber_g": 0,
		}
		resolved = {
			"item_name": "chicken breast",
			"quantity": 100,
			"unit": "g",
			"calories": 200,  # DB match (very different!)
			"protein_g": 31,
			"carbs_g": 0,
			"fats_g": 3.6,
			"fiber_g": 0,
			"source": "usda_fdc",
			"confidence": 0.95,
		}
		refined = {
			"calories": 165,  # Reconciled value
			"protein_g": 25,
			"carbs_g": 1,
			"fats_g": 3,
			"fiber_g": 0,
			"confidence": 0.92,
		}
		mock_resolve.return_value = resolved
		mock_refine.return_value = refined

		result = resolve_and_refine_item(item)

		# resolve was called
		mock_resolve.assert_called_once()
		# refinement should have been triggered due to divergence
		mock_refine.assert_called_once()
		# Result should have refined values
		assert result["calories"] == 165
		assert result["protein_g"] == 25
		assert result["confidence"] == 0.92
		# Source should remain "usda_fdc" (unchanged)
		assert result["source"] == "usda_fdc"

	@patch('meals.services.llm_service.refine_meal_item')
	@patch('meals.services.food_lookup_service.resolve_item_macros')
	def test_resolve_and_refine_refinement_error_falls_back(self, mock_resolve, mock_refine):
		"""If refinement fails, should fall back to DB-resolved values."""
		item = {
			"item_name": "chicken",
			"quantity": 100,
			"unit": "g",
			"calories": 100,
			"protein_g": 10,
			"carbs_g": 5,
			"fats_g": 2,
			"fiber_g": 0,
		}
		resolved = {
			"item_name": "chicken breast",
			"quantity": 100,
			"unit": "g",
			"calories": 200,
			"protein_g": 31,
			"carbs_g": 0,
			"fats_g": 3.6,
			"fiber_g": 0,
			"source": "usda_fdc",
			"confidence": 0.95,
		}
		mock_resolve.return_value = resolved
		mock_refine.side_effect = LLMServiceError("Groq API timeout")

		result = resolve_and_refine_item(item)

		# resolve was called
		mock_resolve.assert_called_once()
		# refinement was attempted but failed
		mock_refine.assert_called_once()
		# Should fall back to the resolved (DB-matched) values
		assert result["calories"] == 200
		assert result["protein_g"] == 31
		assert result["source"] == "usda_fdc"

	@patch('meals.services.llm_service.refine_meal_item')
	@patch('meals.services.food_lookup_service.resolve_item_macros')
	def test_resolve_and_refine_confidence_floor(self, mock_resolve, mock_refine):
		"""Refined confidence should be floored at 0.90."""
		item = {
			"item_name": "chicken",
			"quantity": 100,
			"unit": "g",
			"calories": 100,
			"protein_g": 10,
			"carbs_g": 5,
			"fats_g": 2,
			"fiber_g": 0,
		}
		resolved = {
			"item_name": "chicken breast",
			"quantity": 100,
			"unit": "g",
			"calories": 200,
			"protein_g": 31,
			"carbs_g": 0,
			"fats_g": 3.6,
			"fiber_g": 0,
			"source": "usda_fdc",
			"confidence": 0.95,
		}
		refined = {
			"calories": 165,
			"protein_g": 25,
			"carbs_g": 1,
			"fats_g": 3,
			"fiber_g": 0,
			"confidence": 0.85,  # Lower than floor
		}
		mock_resolve.return_value = resolved
		mock_refine.return_value = refined

		result = resolve_and_refine_item(item)

		# Confidence should be floored to 0.90
		assert result["confidence"] == 0.90
