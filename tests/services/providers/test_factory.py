"""Tests for the provider strategy factory."""

import pytest
from unittest.mock import Mock

from provider.services.providers import create_strategy


class TestCreateStrategy:
    def test_create_modelscope(self):
        """Should create a ModelScopeStrategy for 'modelscope'."""
        strategy = create_strategy(
            "modelscope",
            quota_updater=Mock(),
            quota_repository=Mock(),
        )
        assert type(strategy).__name__ == "ModelScopeStrategy"

    def test_create_sensetime(self, database):
        """Should create a SenseTimeStrategy for 'sensetime'."""
        strategy = create_strategy("sensetime", db=database)
        assert type(strategy).__name__ == "SenseTimeStrategy"

    def test_create_fixed_window_per_model(self, database):
        """Should create a PerModelFixedWindowStrategy for 'fixed_window_per_model'."""
        strategy = create_strategy(
            "fixed_window_per_model",
            db=database,
            window_seconds=3600,
            max_requests=500,
            model_configs={"model-a": {"window_seconds": 1800, "max_requests": 100}},
        )
        assert type(strategy).__name__ == "PerModelFixedWindowStrategy"

    def test_unknown_provider_raises(self):
        """Should raise ValueError for unknown provider_type."""
        with pytest.raises(ValueError, match="Unknown provider_type"):
            create_strategy("unknown_provider")
