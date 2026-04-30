"""
Unit tests for LLM configuration.

These tests validate LLM initialization parameters and safety checks.
"""

from unittest.mock import Mock, patch

import pytest

from auto_healer.llm_config import RECOMMENDED_MODELS, get_llm, get_recommended_model


class TestGetLLM:
    """Test cases for get_llm function."""

    @patch("auto_healer.llm_config.ChatOllama")
    @patch("auto_healer.llm_config.OLLAMA_AVAILABLE", True)
    def test_get_llm_default_params(self, mock_chat_ollama):
        """Test LLM initialization with default parameters."""
        # Mock ChatOllama
        mock_llm = Mock()
        mock_chat_ollama.return_value = mock_llm

        # Call function with defaults
        result = get_llm()

        # Assertions
        mock_chat_ollama.assert_called_once_with(model="qwen2.5:14b", num_ctx=16384, temperature=0.0)
        assert result == mock_llm

    @patch("auto_healer.llm_config.ChatOllama")
    @patch("auto_healer.llm_config.OLLAMA_AVAILABLE", True)
    def test_get_llm_custom_params(self, mock_chat_ollama):
        """Test LLM initialization with custom parameters."""
        # Mock ChatOllama
        mock_llm = Mock()
        mock_chat_ollama.return_value = mock_llm

        # Call function with custom params
        get_llm(model="qwen2.5:7b", num_ctx=32768, temperature=0.7)

        # Assertions
        mock_chat_ollama.assert_called_once_with(model="qwen2.5:7b", num_ctx=32768, temperature=0.7)

    @patch("auto_healer.llm_config.ChatOllama")
    @patch("auto_healer.llm_config.OLLAMA_AVAILABLE", True)
    def test_get_llm_enforces_minimum_context(self, mock_chat_ollama):
        """Test that num_ctx is enforced to minimum 16384."""
        # Mock ChatOllama
        mock_llm = Mock()
        mock_chat_ollama.return_value = mock_llm

        # Call function with too-small num_ctx
        get_llm(num_ctx=2048)  # Too small!

        # Assertions - should be forced to 16384
        call_args = mock_chat_ollama.call_args
        assert call_args[1]["num_ctx"] == 16384

    @patch("auto_healer.llm_config.OLLAMA_AVAILABLE", False)
    def test_get_llm_ollama_not_available(self):
        """Test error when Ollama not installed."""
        # Call function when Ollama not available
        with pytest.raises(RuntimeError, match="langchain-ollama not installed"):
            get_llm()

    @patch("auto_healer.llm_config.ChatOllama")
    @patch("auto_healer.llm_config.OLLAMA_AVAILABLE", True)
    def test_get_llm_with_kwargs(self, mock_chat_ollama):
        """Test passing additional kwargs to ChatOllama."""
        # Mock ChatOllama
        mock_llm = Mock()
        mock_chat_ollama.return_value = mock_llm

        # Call with extra kwargs
        get_llm(model="qwen2.5:14b", num_ctx=16384, temperature=0.0, top_p=0.9, top_k=40)

        # Assertions
        call_args = mock_chat_ollama.call_args
        assert call_args[1]["top_p"] == 0.9
        assert call_args[1]["top_k"] == 40


class TestGetRecommendedModel:
    """Test cases for get_recommended_model function."""

    def test_get_default_model(self):
        """Test getting default recommended model."""
        model = get_recommended_model("default")
        assert model == "qwen2.5:14b"

    def test_get_fast_model(self):
        """Test getting fast recommended model."""
        model = get_recommended_model("fast")
        assert model == "qwen2.5:7b"

    def test_get_powerful_model(self):
        """Test getting powerful recommended model."""
        model = get_recommended_model("powerful")
        assert model == "qwen2.5:32b"

    def test_get_invalid_use_case_returns_default(self):
        """Test that invalid use case returns default model."""
        model = get_recommended_model("nonexistent")
        assert model == "qwen2.5:14b"

    def test_recommended_models_dict(self):
        """Test RECOMMENDED_MODELS dictionary structure."""
        assert "default" in RECOMMENDED_MODELS
        assert "fast" in RECOMMENDED_MODELS
        assert "powerful" in RECOMMENDED_MODELS
        assert len(RECOMMENDED_MODELS) == 3


class TestLLMConfiguration:
    """Integration tests for LLM configuration."""

    @patch("auto_healer.llm_config.ChatOllama")
    @patch("auto_healer.llm_config.OLLAMA_AVAILABLE", True)
    def test_temperature_zero_for_deterministic(self, mock_chat_ollama):
        """Test that default temperature is 0.0 for deterministic output."""
        # Mock ChatOllama
        mock_llm = Mock()
        mock_chat_ollama.return_value = mock_llm

        # Call function
        get_llm()

        # Assertions
        call_args = mock_chat_ollama.call_args
        assert call_args[1]["temperature"] == 0.0

    @patch("auto_healer.llm_config.ChatOllama")
    @patch("auto_healer.llm_config.OLLAMA_AVAILABLE", True)
    def test_context_window_large_enough_for_logs(self, mock_chat_ollama):
        """Test that context window is large enough for log analysis."""
        # Mock ChatOllama
        mock_llm = Mock()
        mock_chat_ollama.return_value = mock_llm

        # Call function
        get_llm()

        # Assertions - 16384 is 8x default, enough for 100 lines of logs
        call_args = mock_chat_ollama.call_args
        assert call_args[1]["num_ctx"] >= 16384
