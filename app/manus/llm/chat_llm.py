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

from typing import List, Dict, Any
from openai import OpenAI

from app.manus.task.time_record_util import time_record
from app.manus.llm.langfuse_config import is_langfuse_enabled, observe, get_langfuse_client

# Conditional import for Langfuse OpenAI wrapper
try:
    from langfuse.openai import openai as langfuse_openai
    LANGFUSE_OPENAI_AVAILABLE = True
except ImportError:
    LANGFUSE_OPENAI_AVAILABLE = False


class ChatLLM:
    def __init__(self, base_url: str, api_key: str, model: str, client: OpenAI, max_tokens: int = 4096,
                 temperature: float = 0.0, stream: bool = False, tools: List[Any] = None):
        self.tools = tools or []
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.stream = stream
        self.temperature = temperature
        self.max_tokens = max_tokens

        # NEW: Add session_id for tracing (will be set by Manus)
        self.session_id = None

        # NEW: Wrap OpenAI client with Langfuse instrumentation if enabled
        if is_langfuse_enabled() and LANGFUSE_OPENAI_AVAILABLE:
            try:
                self.client = langfuse_openai.OpenAI(
                    base_url=base_url,
                    api_key=api_key,
                    http_client=client._client
                )
                print(f"[LangFuse] ✅ ChatLLM using instrumented OpenAI client")
            except Exception as e:
                print(f"[LangFuse] ⚠️  Failed to wrap OpenAI client: {e}")
                self.client = client
        else:
            self.client = client

    @staticmethod
    def clean_none_values(data):
        """
        递归遍历数据结构，将所有 None 替换为 ""
        静态方法，无需实例化类即可调用
        """
        if isinstance(data, dict):
            return {k: ChatLLM.clean_none_values(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [ChatLLM.clean_none_values(item) for item in data]
        elif data is None:
            return ""
        else:
            return data

    @time_record
    @observe(name="llm_create_with_tools")
    def create_with_tools(self, messages: List[Dict[str, Any]], tools: List[Dict]):
        """
        Create a chat completion with support for function/tool calls
        """
        import time
        import json

        # NEW: Update trace with metadata
        if is_langfuse_enabled():
            try:
                trace_params = {
                    "metadata": {
                        "model": self.model,
                        "temperature": self.temperature,
                        "tools_count": len(tools),
                        "base_url": self.base_url
                    }
                }
                if self.session_id:
                    trace_params["session_id"] = self.session_id
                get_langfuse_client().update_current_trace(**trace_params)
            except Exception as e:
                print(f"[LangFuse] Failed to update trace: {e}")

        # 清洗提示词，去除None
        messages = ChatLLM.clean_none_values(messages)
        print(f'create_with_tools messages:{messages}')
        max_retries = 2
        for attempt in range(max_retries):
            model_name = self.model
            try:
                if attempt == 1:
                    model_name = 'anthropic/claude-sonnet-4'
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=self.temperature
                )
                print(f"LLM with tools chat completions response{attempt + 1} is {response}")
                break
            except Exception as e:
                print(f"JSON decode error: {e} on attempt {attempt + 1}, retrying...")
                if attempt == max_retries:
                    print(f"Failed to create after {max_retries + 1} attempts.")
                    raise
                time.sleep(3)  # 增加等待时间，避免频繁重试

        # 去除think标签
        content = response.choices[0].message.content
        if content is not None and '</think>' in content:
            response.choices[0].message.content = content.split('</think>')[-1].strip('\n')

        return response.choices[0].message

    @time_record
    @observe(name="llm_chat_to_llm")
    def chat_to_llm(self, messages: List[Dict[str, Any]]):
        import time
        import json

        # NEW: Update trace with metadata
        if is_langfuse_enabled():
            try:
                trace_params = {
                    "metadata": {
                        "model": self.model,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "base_url": self.base_url
                    }
                }
                if self.session_id:
                    trace_params["session_id"] = self.session_id
                get_langfuse_client().update_current_trace(**trace_params)
            except Exception as e:
                print(f"[LangFuse] Failed to update trace: {e}")

        # 清洗提示词，去除None
        messages = ChatLLM.clean_none_values(messages)
        print(f'chat_to_llm messages:{messages}')
        max_retries = 2
        for attempt in range(max_retries):
            model_name = self.model
            try:
                if attempt == 1:
                    model_name = 'anthropic/claude-sonnet-4'
                print(f"[DEBUG] About to call LLM API (attempt {attempt + 1})...")
                print(f"[DEBUG] Model: {model_name}, Base URL: {self.base_url}")
                print(f"[DEBUG] Temperature: {self.temperature}, Max tokens: {self.max_tokens}")
                import sys
                sys.stdout.flush()
                response = self.client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens
                )
                print(f"[DEBUG] LLM API call completed successfully!")
                print(f"LLM with tools chat completions response{attempt + 1} is {response}")
                break
            except Exception as e:
                print(f"JSON decode error: {e} on attempt {attempt + 1}, retrying...")
                if attempt == max_retries:
                    print(f"Failed to create after {max_retries + 1} attempts.")
                    raise
                time.sleep(3)  # 增加等待时间，避免频繁重试
        # print(f"response is {response}")
        # 去除think标签
        content = response.choices[0].message.content
        if content is not None and '</think>' in content:
            response.choices[0].message.content = content.split('</think>')[-1].strip('\n')

        return response.choices[0].message.content
