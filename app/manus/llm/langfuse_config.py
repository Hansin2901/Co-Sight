# Copyright 2025 ZTE Corporation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
Langfuse Configuration Module

This module provides centralized configuration for Langfuse observability:
- Initializes Langfuse client with credentials
- Sets up ThreadingInstrumentor for parallel execution context propagation
- Provides observe decorator and client access
- Handles graceful degradation when Langfuse is disabled
"""

import os
import logging

logger = logging.getLogger(__name__)

# Global Langfuse client instance
_langfuse_client = None

# Track if Langfuse is available and enabled
LANGFUSE_AVAILABLE = False
try:
    from langfuse import Langfuse
    LANGFUSE_AVAILABLE = True
except ImportError:
    logger.warning("[LangFuse] ⚠️  langfuse package not installed")


def is_langfuse_enabled() -> bool:
    """
    Check if LangFuse is enabled via ENABLE_LANGFUSE environment variable.

    Returns:
        bool: True if enabled, False otherwise
    """
    enabled = os.getenv('ENABLE_LANGFUSE', 'false').lower() == 'true'
    return enabled and LANGFUSE_AVAILABLE


def initialize_langfuse():
    """
    Initialize LangFuse client and ThreadingInstrumentor.

    This function should be called once at application startup.

    Returns:
        Langfuse client instance or None if disabled/failed
    """
    global _langfuse_client

    if not is_langfuse_enabled():
        logger.info("[LangFuse] ℹ️  Tracing disabled (ENABLE_LANGFUSE=false)")
        return None

    try:
        # Step 1: Initialize ThreadingInstrumentor for parallel execution
        try:
            from opentelemetry.instrumentation.threading import ThreadingInstrumentor
            ThreadingInstrumentor().instrument()
            logger.info("[LangFuse] ✅ ThreadingInstrumentor initialized - context will propagate to threads")
        except ImportError:
            logger.warning("[LangFuse] ⚠️  opentelemetry-instrumentation-threading not installed")
            logger.warning("[LangFuse] Threading context propagation may not work correctly")
            logger.warning("[LangFuse] Install with: pip install opentelemetry-instrumentation-threading")

        # Step 2: Initialize Langfuse client
        from langfuse import Langfuse

        host = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')
        public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
        secret_key = os.getenv('LANGFUSE_SECRET_KEY')
        release = os.getenv('LANGFUSE_RELEASE')
        environment = os.getenv('LANGFUSE_ENVIRONMENT', 'development')

        if not public_key or not secret_key:
            logger.error("[LangFuse] ❌ Missing API keys (LANGFUSE_PUBLIC_KEY or LANGFUSE_SECRET_KEY)")
            return None

        _langfuse_client = Langfuse(
            host=host,
            public_key=public_key,
            secret_key=secret_key,
            release=release,
            environment=environment
        )

        logger.info(f"[LangFuse] ✅ Initialized successfully")
        logger.info(f"[LangFuse]    Host: {host}")
        logger.info(f"[LangFuse]    Environment: {environment}")
        if release:
            logger.info(f"[LangFuse]    Release: {release}")

        return _langfuse_client

    except Exception as e:
        logger.error(f"[LangFuse] ❌ Initialization failed: {e}", exc_info=True)
        return None


def get_langfuse_client():
    """
    Get the initialized LangFuse client instance.

    Returns:
        Langfuse client or None if not initialized
    """
    return _langfuse_client


def shutdown_langfuse():
    """
    Flush pending traces and shutdown LangFuse client.

    This should be called before application exit to ensure all traces are uploaded.
    """
    global _langfuse_client

    if _langfuse_client:
        try:
            logger.info("[LangFuse] 📤 Flushing pending traces...")
            _langfuse_client.flush()
            logger.info("[LangFuse] ✅ Shutdown complete")
        except Exception as e:
            logger.error(f"[LangFuse] ❌ Shutdown error: {e}")


def observe_fallback(*args, **kwargs):
    """
    Fallback no-op decorator when LangFuse is disabled or unavailable.

    This allows code to use @observe decorator without ImportError.
    """
    def decorator(func):
        return func

    # Handle both @observe and @observe(...) syntax
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return decorator


# Export observe decorator
if LANGFUSE_AVAILABLE and is_langfuse_enabled():
    from langfuse import observe
else:
    observe = observe_fallback
