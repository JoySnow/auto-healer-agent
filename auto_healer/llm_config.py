"""
LLM Configuration for Local Ollama

This module provides configuration for the local LLM (qwen2.5:14b via Ollama).

CRITICAL: The context window (num_ctx) MUST be set to 16384 minimum.
The default 2048 tokens will truncate application logs and cause silent reasoning failures.
"""
from typing import Optional
import logging

try:
    from langchain_ollama import ChatOllama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("langchain-ollama not installed. LLM features will be disabled.")

logger = logging.getLogger(__name__)


def get_llm(
    model: str = "qwen2.5:14b",
    num_ctx: int = 16384,
    temperature: float = 0.0,
    **kwargs
) -> Optional[ChatOllama]:
    """
    Initialize and return a ChatOllama LLM instance with proper configuration.

    CRITICAL CONFIGURATION:
    - num_ctx MUST be 16384 or higher to handle full application logs and stack traces
    - temperature=0.0 for deterministic debugging (reproducible outputs)

    Args:
        model (str): Ollama model name. Default is "qwen2.5:14b".
                    This model has strong coding and tool-calling capabilities.
        num_ctx (int): Context window size in tokens. MUST be >= 16384.
                      The agent analyzes massive log dumps and tracebacks.
                      Default 2048 will silently fail.
        temperature (float): Sampling temperature (0.0 = deterministic, 1.0 = creative).
                           Default is 0.0 for consistent debugging behavior.
        **kwargs: Additional arguments passed to ChatOllama.

    Returns:
        ChatOllama: Configured LLM instance ready for agent use.

    Raises:
        RuntimeError: If langchain-ollama is not installed.
        ValueError: If num_ctx is less than 16384 (safety check).

    Example:
        >>> llm = get_llm()
        >>> response = llm.invoke("Analyze this error...")

    Prerequisites:
        1. Ollama must be running: `ollama serve`
        2. Model must be pulled: `ollama pull qwen2.5:14b`
        3. Test with: `ollama run qwen2.5:14b "Hello"`
    """
    if not OLLAMA_AVAILABLE:
        raise RuntimeError(
            "langchain-ollama not installed. "
            "Install with: uv pip install langchain-ollama"
        )

    # Safety check: Enforce minimum context window
    if num_ctx < 16384:
        logger.warning(
            f"num_ctx={num_ctx} is too small! "
            f"Agent needs 16384+ to analyze logs. Forcing num_ctx=16384."
        )
        num_ctx = 16384

    logger.info(f"Initializing ChatOllama with model={model}, num_ctx={num_ctx}, temperature={temperature}")

    try:
        llm = ChatOllama(
            model=model,
            num_ctx=num_ctx,
            temperature=temperature,
            **kwargs
        )

        logger.info("ChatOllama LLM initialized successfully")
        return llm

    except Exception as e:
        logger.error(f"Failed to initialize LLM: {str(e)}")
        logger.error("Make sure Ollama is running: ollama serve")
        logger.error(f"And model is pulled: ollama pull {model}")
        raise


def test_llm_connection(model: str = "qwen2.5:14b") -> bool:
    """
    Test if Ollama is running and the model is available.

    Args:
        model (str): Model name to test.

    Returns:
        bool: True if connection successful, False otherwise.

    Example:
        >>> if test_llm_connection():
        ...     print("LLM ready!")
        ... else:
        ...     print("Ollama not running or model not available")
    """
    if not OLLAMA_AVAILABLE:
        logger.error("langchain-ollama not installed")
        return False

    try:
        llm = get_llm(model=model)
        response = llm.invoke("Hello")

        logger.info(f"LLM connection test successful. Response: {response.content[:50]}...")
        return True

    except Exception as e:
        logger.error(f"LLM connection test failed: {str(e)}")
        return False


# Model recommendations for different use cases
RECOMMENDED_MODELS = {
    "default": "qwen2.5:14b",  # Best balance of capability and speed for M3 Pro
    "fast": "qwen2.5:7b",       # Faster but less capable
    "powerful": "qwen2.5:32b",  # More capable but slower, requires more RAM
}


def get_recommended_model(use_case: str = "default") -> str:
    """
    Get recommended model name for a specific use case.

    Args:
        use_case (str): One of "default", "fast", "powerful"

    Returns:
        str: Model name

    Example:
        >>> model = get_recommended_model("powerful")
        >>> llm = get_llm(model=model)
    """
    return RECOMMENDED_MODELS.get(use_case, RECOMMENDED_MODELS["default"])
