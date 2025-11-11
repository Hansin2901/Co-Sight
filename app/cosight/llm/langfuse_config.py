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
LangFuse Observability Configuration

This module initializes LangFuse for tracing LLM calls and tool executions.
Provides centralized configuration and graceful degradation if LangFuse is unavailable.
"""

import os
from typing import Optional
from functools import wraps
from app.common.logger_util import logger

# Global LangFuse instance
_langfuse_enabled = None
_langfuse_client = None


def is_langfuse_enabled() -> bool:
    """
    Check if LangFuse is enabled via environment variable.
    
    Returns:
        bool: True if ENABLE_LANGFUSE=true, False otherwise
    """
    global _langfuse_enabled
    if _langfuse_enabled is None:
        _langfuse_enabled = os.getenv('ENABLE_LANGFUSE', 'false').lower() == 'true'
    return _langfuse_enabled


def initialize_langfuse() -> Optional[any]:
    """
    Initialize LangFuse client if enabled.
    
    This function:
    - Checks if LangFuse is enabled via environment variable
    - Attempts to import and initialize the LangFuse client
    - Handles errors gracefully with fallback to no-op
    
    Returns:
        LangFuse client instance or None if disabled/failed
    """
    global _langfuse_client
    
    if not is_langfuse_enabled():
        logger.info("[LangFuse] 📊 Observability disabled (ENABLE_LANGFUSE=false)")
        return None
    
    # Return existing client if already initialized
    if _langfuse_client is not None:
        return _langfuse_client
    
    try:
        # Initialize OpenTelemetry ThreadingInstrumentor for automatic context propagation
        # This enables trace context to automatically propagate to child threads
        # See: https://langfuse.com/docs/observability/sdk/python/advanced-usage
        try:
            from opentelemetry.instrumentation.threading import ThreadingInstrumentor
            ThreadingInstrumentor().instrument()
            logger.info("[LangFuse] ✅ ThreadingInstrumentor initialized - context will propagate to threads")
        except ImportError:
            logger.warning("[LangFuse] ⚠️  opentelemetry-instrumentation-threading not installed")
            logger.warning("[LangFuse] Install with: uv add opentelemetry-instrumentation-threading")
            logger.warning("[LangFuse] Threading context propagation may not work correctly")
        except Exception as e:
            logger.warning(f"[LangFuse] ⚠️  Failed to initialize ThreadingInstrumentor: {e}")

        # Import LangFuse
        from langfuse import Langfuse

        # Get configuration from environment
        host = os.getenv('LANGFUSE_HOST', 'https://cloud.langfuse.com')
        public_key = os.getenv('LANGFUSE_PUBLIC_KEY')
        secret_key = os.getenv('LANGFUSE_SECRET_KEY')
        
        # Validate required credentials for cloud/remote instances
        if not host.startswith('http://localhost'):
            if not public_key or not secret_key:
                logger.warning("[LangFuse] ⚠️  LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY required for cloud/remote instances")
                logger.warning("[LangFuse] ⚠️  Set these in your .env file or disable with ENABLE_LANGFUSE=false")
                return None
        
        # Initialize client with credentials
        init_kwargs = {'host': host}
        if public_key and secret_key:
            init_kwargs['public_key'] = public_key
            init_kwargs['secret_key'] = secret_key
        
        # Add optional configuration
        release = os.getenv('LANGFUSE_RELEASE')
        environment = os.getenv('LANGFUSE_ENVIRONMENT', 'development')
        
        if release:
            init_kwargs['release'] = release
        
        _langfuse_client = Langfuse(**init_kwargs)
        
        # Test connection with a simple operation
        try:
            # This will validate credentials without creating a trace
            _langfuse_client.auth_check()
            logger.info(f"[LangFuse] ✅ Initialized successfully")
            logger.info(f"[LangFuse] 🌐 Host: {host}")
            logger.info(f"[LangFuse] 🏷️  Environment: {environment}")
            logger.info(f"[LangFuse] 📊 Dashboard: {host}")
        except Exception as auth_error:
            logger.error(f"[LangFuse] ❌ Authentication failed: {auth_error}")
            logger.error("[LangFuse] Please check your LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY")
            _langfuse_client = None
            return None
        
        return _langfuse_client
        
    except ImportError:
        logger.warning("[LangFuse] ⚠️  Package not installed. Run: pip install langfuse")
        logger.warning("[LangFuse] Continuing without observability...")
        return None
    except Exception as e:
        logger.error(f"[LangFuse] ❌ Initialization failed: {e}", exc_info=True)
        logger.error("[LangFuse] Continuing without observability...")
        return None


def get_langfuse_client():
    """
    Get the initialized LangFuse client.
    
    Returns:
        LangFuse client instance or None if not initialized
    """
    return _langfuse_client


def shutdown_langfuse():
    """
    Flush any pending traces before shutdown.
    
    This should be called during application shutdown to ensure
    all traces are sent to LangFuse before the application exits.
    """
    global _langfuse_client
    if _langfuse_client is not None:
        try:
            logger.info("[LangFuse] Flushing pending traces...")
            _langfuse_client.flush()
            logger.info("[LangFuse] ✅ All traces flushed successfully")
        except Exception as e:
            logger.error(f"[LangFuse] ⚠️  Error flushing traces: {e}")


# Fallback decorator for when LangFuse is not available
def observe_fallback(*args, **kwargs):
    """
    Fallback decorator that does nothing when LangFuse is unavailable.
    This ensures code doesn't break if LangFuse isn't installed.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    # Handle both @observe and @observe() syntax
    if len(args) == 1 and callable(args[0]) and not kwargs:
        return decorator(args[0])
    return decorator
