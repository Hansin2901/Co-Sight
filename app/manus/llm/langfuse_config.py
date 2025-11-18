"""
Langfuse Configuration Module

This module provides centralized Langfuse observability configuration for the Manus agent system.
It enables distributed tracing of LLM calls, tool executions, parallel agent operations, and plan execution
while maintaining proper session context across concurrent threads.

Usage:
    1. Set ENABLE_LANGFUSE=true in .env and configure API keys
    2. Call initialize_langfuse() at application startup
    3. Use @observe decorator on functions to trace
    4. Call shutdown_langfuse() before application exit

Features:
    - Singleton pattern for global Langfuse client management
    - Thread context propagation via OpenTelemetry ThreadingInstrumentor
    - Graceful degradation when tracing is disabled
    - Conditional imports to avoid runtime errors when Langfuse is not installed
"""

import os
from typing import Optional
from functools import wraps

# Global state
_langfuse_client = None
_langfuse_enabled = False
_threading_instrumented = False

# Conditional imports - only import Langfuse if available
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False
    print("[LangFuse] ⚠️  langfuse package not installed. Tracing will be disabled.")

try:
    from opentelemetry.instrumentation.threading import ThreadingInstrumentor
    THREADING_INSTRUMENTATION_AVAILABLE = True
except ImportError:
    THREADING_INSTRUMENTATION_AVAILABLE = False
    print("[LangFuse] ⚠️  opentelemetry-instrumentation-threading not installed. Thread context propagation will be disabled.")


def is_langfuse_enabled() -> bool:
    """
    Check if Langfuse tracing is enabled.

    Returns:
        bool: True if tracing is enabled and initialized, False otherwise
    """
    return _langfuse_enabled


def get_langfuse_client() -> Optional[object]:
    """
    Get the global Langfuse client instance.

    Returns:
        Optional[Langfuse]: The Langfuse client if initialized, None otherwise
    """
    return _langfuse_client


def initialize_langfuse() -> bool:
    """
    Initialize Langfuse observability system.

    This function:
    1. Checks if tracing is enabled via ENABLE_LANGFUSE environment variable
    2. Initializes OpenTelemetry ThreadingInstrumentor for context propagation
    3. Creates and configures the global Langfuse client
    4. Sets up proper error handling and logging

    Returns:
        bool: True if initialization succeeded, False otherwise
    """
    global _langfuse_client, _langfuse_enabled, _threading_instrumented

    # Check if tracing should be enabled
    enable_langfuse = os.getenv("ENABLE_LANGFUSE", "false").lower() == "true"

    if not enable_langfuse:
        print("[LangFuse] ℹ️  Tracing disabled (ENABLE_LANGFUSE=false)")
        _langfuse_enabled = False
        return False

    if not LANGFUSE_AVAILABLE:
        print("[LangFuse] ❌ Cannot enable tracing - langfuse package not installed")
        print("[LangFuse] ℹ️  Install with: pip install langfuse")
        _langfuse_enabled = False
        return False

    # Initialize ThreadingInstrumentor for context propagation across threads
    # This is CRITICAL for parallel execution in Manus
    if THREADING_INSTRUMENTATION_AVAILABLE and not _threading_instrumented:
        try:
            ThreadingInstrumentor().instrument()
            _threading_instrumented = True
            print("[LangFuse] ✅ ThreadingInstrumentor initialized - context will propagate to threads")
        except Exception as e:
            print(f"[LangFuse] ⚠️  Failed to initialize ThreadingInstrumentor: {e}")
            print("[LangFuse] ℹ️  Thread context propagation may not work properly")

    # Get Langfuse configuration from environment
    langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    langfuse_release = os.getenv("LANGFUSE_RELEASE", "v1.0.0")
    langfuse_environment = os.getenv("LANGFUSE_ENVIRONMENT", "development")

    # Validate required credentials
    if not langfuse_public_key or not langfuse_secret_key:
        print("[LangFuse] ❌ Missing required credentials")
        print("[LangFuse] ℹ️  Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env")
        _langfuse_enabled = False
        return False

    if langfuse_public_key == "pk-lf-..." or langfuse_secret_key == "sk-lf-...":
        print("[LangFuse] ❌ Default placeholder credentials detected")
        print("[LangFuse] ℹ️  Sign up at https://cloud.langfuse.com and update .env with real API keys")
        _langfuse_enabled = False
        return False

    # Initialize Langfuse client
    try:
        _langfuse_client = Langfuse(
            public_key=langfuse_public_key,
            secret_key=langfuse_secret_key,
            host=langfuse_host,
            release=langfuse_release,
            environment=langfuse_environment
        )
        _langfuse_enabled = True

        print("[LangFuse] ✅ Initialized successfully")
        print(f"[LangFuse]    Host: {langfuse_host}")
        print(f"[LangFuse]    Environment: {langfuse_environment}")
        print(f"[LangFuse]    Release: {langfuse_release}")

        return True

    except Exception as e:
        print(f"[LangFuse] ❌ Failed to initialize: {e}")
        _langfuse_enabled = False
        _langfuse_client = None
        return False


def shutdown_langfuse():
    """
    Flush pending traces and shutdown Langfuse client.

    Call this function before application exit to ensure all traces are uploaded.
    Safe to call even if Langfuse was never initialized.
    """
    global _langfuse_client, _langfuse_enabled

    if _langfuse_client is not None:
        try:
            print("[LangFuse] 📤 Flushing pending traces...")
            _langfuse_client.flush()
            print("[LangFuse] ✅ Shutdown complete")
        except Exception as e:
            print(f"[LangFuse] ⚠️  Error during shutdown: {e}")
        finally:
            _langfuse_client = None
            _langfuse_enabled = False


# Fallback decorator when Langfuse is disabled
def observe_fallback(name: Optional[str] = None, **kwargs):
    """
    Fallback decorator that does nothing when Langfuse is disabled.

    This provides a no-op decorator with the same signature as langfuse.decorators.observe,
    allowing code to use @observe unconditionally.

    Args:
        name: Optional span name (ignored in fallback)
        **kwargs: Additional tracing parameters (ignored in fallback)

    Returns:
        Decorator that returns the original function unchanged
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator


# Export the observe decorator - use real one if available, fallback otherwise
if LANGFUSE_AVAILABLE:
    try:
        from langfuse.decorators import observe as langfuse_observe
        observe = langfuse_observe
    except ImportError:
        # Older version of langfuse might have different import path
        try:
            from langfuse import observe as langfuse_observe
            observe = langfuse_observe
        except ImportError:
            print("[LangFuse] ⚠️  Could not import observe decorator, using fallback")
            observe = observe_fallback
else:
    observe = observe_fallback


# Convenience function to update current trace with session context
def update_trace_session(session_id: str, name: str = None, metadata: dict = None, tags: list = None):
    """
    Update the current trace with session context.

    This is a convenience function to safely update trace metadata even when tracing is disabled.

    Args:
        session_id: The session ID to associate with this trace
        name: Optional trace name
        metadata: Optional metadata dictionary
        tags: Optional list of tags
    """
    if not _langfuse_enabled or _langfuse_client is None:
        return

    try:
        update_params = {"session_id": session_id}
        if name:
            update_params["name"] = name
        if metadata:
            update_params["metadata"] = metadata
        if tags:
            update_params["tags"] = tags

        _langfuse_client.update_current_trace(**update_params)
    except Exception as e:
        print(f"[LangFuse] ⚠️  Failed to update trace session: {e}")


# Convenience function to update current span
def update_span(name: str = None, metadata: dict = None):
    """
    Update the current span with metadata.

    This is a convenience function to safely update span metadata even when tracing is disabled.

    Args:
        name: Optional span name
        metadata: Optional metadata dictionary
    """
    if not _langfuse_enabled or _langfuse_client is None:
        return

    try:
        update_params = {}
        if name:
            update_params["name"] = name
        if metadata:
            update_params["metadata"] = metadata

        if update_params:
            _langfuse_client.update_current_span(**update_params)
    except Exception as e:
        print(f"[LangFuse] ⚠️  Failed to update span: {e}")
