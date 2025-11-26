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

import asyncio
import inspect
import json
import traceback
from concurrent.futures import ThreadPoolExecutor
from json import JSONDecodeError
from typing import List, Dict, Any

from app.agent_dispatcher.domain.plan.action.skill.mcp.engine import MCPEngine
from app.agent_dispatcher.infrastructure.entity.AgentInstance import AgentInstance
from app.manus.agent.base.skill_to_tool import convert_skill_to_tool
from app.manus.llm.chat_llm import ChatLLM
from app.manus.llm.langfuse_config import observe, is_langfuse_enabled, get_langfuse_client
from app.manus.task.time_record_util import time_record
from app.manus.task.todolist import Plan


class BaseAgent:
    def __init__(self, agent_instance: AgentInstance, llm: ChatLLM, functions: {}):
        self.agent_instance = agent_instance
        self.llm = llm
        self.tools = []
        self.mcp_tools = []
        # self.tools = [convert_skill_to_tool(skill.model_dump(), 'en') for skill in self.agent_instance.template.skills]
        for skill in self.agent_instance.template.skills:
            self.tools.extend(convert_skill_to_tool(skill.model_dump(), 'en'))
        # self.tools.extend(convert_mcp_tools(self.mcp_tools))
        self.functions = functions
        self.history = []

    def find_mcp_tool(self, tool_name):
        for tool in self.mcp_tools:
            for func in tool['mcp_tools']:
                if func.name == tool_name:
                    return tool, func.name
        return None

    def _detect_tool_category(self, function_name: str) -> str:
        """
        Detect tool category based on function name for better tracing visibility.
        
        Returns category like: web_search, arxiv, wikipedia, file, code, document, etc.
        """
        name_lower = function_name.lower()
        
        # Search tools
        if 'google' in name_lower or 'duckduckgo' in name_lower or 'linkup' in name_lower:
            return 'web_search'
        if 'wiki' in name_lower:
            return 'wikipedia'
        if 'arxiv' in name_lower:
            return 'arxiv'
        if 'search' in name_lower:
            return 'search'
        
        # Web tools
        if 'scrape' in name_lower or 'fetch_website' in name_lower or 'website' in name_lower:
            return 'web_scraping'
        if 'browser' in name_lower:
            return 'browser'
        if 'download' in name_lower:
            return 'download'
        
        # File tools
        if 'file' in name_lower or 'read_file' in name_lower or 'write_file' in name_lower:
            return 'file'
        if 'excel' in name_lower or 'csv' in name_lower:
            return 'spreadsheet'
        if 'pdf' in name_lower or 'document' in name_lower or 'doc' in name_lower:
            return 'document'
        if 'pptx' in name_lower or 'powerpoint' in name_lower:
            return 'presentation'
        
        # Code tools
        if 'code' in name_lower or 'python' in name_lower or 'execute' in name_lower:
            return 'code_execution'
        
        # Media tools
        if 'image' in name_lower or 'vision' in name_lower or 'visual' in name_lower:
            return 'image_analysis'
        if 'audio' in name_lower:
            return 'audio_analysis'
        if 'video' in name_lower:
            return 'video_analysis'
        
        # Planning tools
        if 'plan' in name_lower or 'create_fact' in name_lower:
            return 'planning'
        if 'terminate' in name_lower or 'mark_step' in name_lower:
            return 'control'
        
        # Default
        return 'other'

    def _get_tool_display_name(self, function_name: str, category: str) -> str:
        """
        Generate human-readable display name for tool traces.
        
        Examples:
            search_google -> "[Web Search] Google"
            search_wiki -> "[Wikipedia] Search"
            arxiv_search_papers -> "[ArXiv] Search Papers"
            read_file -> "[File] Read"
        """
        # Map categories to display prefixes
        category_prefix = {
            'web_search': '🔍 Web Search',
            'wikipedia': '📚 Wikipedia',
            'arxiv': '📄 ArXiv',
            'search': '🔎 Search',
            'web_scraping': '🌐 Web Scraping',
            'browser': '🖥️  Browser',
            'download': '⬇️  Download',
            'file': '📁 File',
            'spreadsheet': '📊 Spreadsheet',
            'document': '📄 Document',
            'presentation': '📊 Presentation',
            'code_execution': '⚙️  Code',
            'image_analysis': '🖼️  Image',
            'audio_analysis': '🔊 Audio',
            'video_analysis': '🎥 Video',
            'planning': '🗺️  Planning',
            'control': '🎯 Control',
            'other': '🔧 Tool'
        }
        
        prefix = category_prefix.get(category, '🔧 Tool')
        
        # Clean up function name for display
        # search_google -> Google
        # arxiv_search_papers -> Search Papers
        # fetch_website_content -> Fetch Website Content
        
        name_parts = function_name.replace('_', ' ').title()
        
        # For common patterns, simplify further
        if 'search' in function_name.lower():
            if 'google' in function_name.lower():
                return f"{prefix}: Google"
            elif 'duckduckgo' in function_name.lower():
                return f"{prefix}: DuckDuckGo"
            elif 'linkup' in function_name.lower():
                return f"{prefix}: LinkUp"
            elif 'wiki' in function_name.lower():
                return f"{prefix}: {name_parts.replace('Search Wiki', 'Search')}"
            elif 'arxiv' in function_name.lower():
                return f"{prefix}: {name_parts.replace('Arxiv ', '').replace('Search Papers', 'Search')}"
        
        return f"{prefix}: {name_parts}"

    @observe(name="base_agent_execute")
    def execute(self, messages: List[Dict[str, Any]], step_index=None, plan: Plan = None, max_iteration=10):
        print(f"\n[DEBUG] === BASE_AGENT EXECUTE START ===")
        print(f"[DEBUG] Max iterations: {max_iteration}, Step index: {step_index}")
        print(f"[DEBUG] Number of messages: {len(messages)}")
        
        for i in range(max_iteration):
            print(f"\n[DEBUG] --- Iteration {i} ---")
            # print(f"messages:{messages}")
            try:
                print(f"[DEBUG] Calling llm.create_with_tools with {len(self.tools)} tools...")
                response = self.llm.create_with_tools(messages, self.tools)
                print(f"[DEBUG] LLM response received")
                print(f"[DEBUG] Response has tool_calls: {bool(response.tool_calls)}")
                if response.tool_calls:
                    print(f"[DEBUG] Number of tool calls: {len(response.tool_calls)}")
                    for tc in response.tool_calls:
                        print(f"[DEBUG]   - Tool: {tc.function.name}")
                else:
                    print(f"[DEBUG] Response content (first 200 chars): {response.content[:200] if response.content else 'None'}...")

            except Exception as e:
                print(f"[DEBUG] LLM call error in iteration {i}: {e}")
                messages[-1]["content"]=f"{e},若要读取文件，使用python代码解析和正则匹配"
                continue
            print(f"index: {i}, response:{response}")

            # Process initial response
            print(f"[DEBUG] Calling _process_response...")
            result = self._process_response(response, messages, step_index, plan)
            print(f"[DEBUG] _process_response returned: {type(result).__name__}")
            if result:
                print(f"[DEBUG] Result exists, returning (first 200 chars): {str(result)[:200]}...")
                print(f"[DEBUG] === BASE_AGENT EXECUTE END (with result) ===\n")
                return result

            print(f"iter {i} for {self.agent_instance.instance_name}")

        print(f"[DEBUG] Max iteration reached")
        if max_iteration > 1:
            print(f"[DEBUG] Calling _handle_max_iteration...")
            result = self._handle_max_iteration(messages, step_index)
            print(f"[DEBUG] === BASE_AGENT EXECUTE END (max iteration) ===\n")
            return result
        
        final_result = messages[-1].get("content")
        print(f"[DEBUG] Returning last message content (first 200 chars): {str(final_result)[:200] if final_result else 'None'}...")
        print(f"[DEBUG] === BASE_AGENT EXECUTE END (fallback) ===\n")
        return final_result

    def _process_response(self, response, messages, step_index, plan: Plan = None, ):
        if not response.tool_calls:
            messages.append({"role": "assistant", "content": response.content})
            return response.content

        messages.append({
            "role": "assistant",
            "content": response.content if response.content is not None else "",
            "tool_calls": response.tool_calls
        })

        results = self._execute_tool_calls(response.tool_calls, step_index, plan)
        messages.extend(results)

        # Check for termination conditions
        for result in results:
            if result["name"] in ["terminate", "mark_step"]:
                return result["content"]
        return None

    # REMOVED @observe decorator - individual tool calls are traced, this aggregate is useless
    def _execute_tool_calls(self, tool_calls, step_index, plan: Plan = None, ):
        print(f"\n[DEBUG] === _execute_tool_calls START ===")
        print(f"[DEBUG] Number of tool calls: {len(tool_calls)}")
        
        results = []
        with ThreadPoolExecutor() as executor:
            print(f"[DEBUG] Creating ThreadPoolExecutor...")
            futures = []
            for idx, tool_call in enumerate(tool_calls):
                function_name = tool_call.function.name
                function_args = tool_call.function.arguments
                
                print(f"[DEBUG] Tool call {idx}: {function_name}")

                if function_name in self.functions:
                    print(f"[DEBUG]   -> Found in self.functions, submitting to executor...")
                    futures.append(executor.submit(
                        self._execute_tool_call,
                        function_name=function_name,
                        function_args=function_args,
                        tool_call_id=tool_call.id,
                        step_index=step_index,
                        plan=plan
                    ))
                else:
                    print(f"[DEBUG]   -> Not in self.functions, checking MCP tools...")
                    futures.append(executor.submit(
                        self._execute_mcp_tool_call,
                        function_name=function_name,
                        function_args=function_args,
                        tool_call_id=tool_call.id,
                        plan=plan
                    ))

            print(f"[DEBUG] All tool calls submitted, waiting for futures...")
            for idx, future in enumerate(futures):
                try:
                    print(f"[DEBUG] Waiting for future {idx}...")
                    result = future.result()
                    print(f"[DEBUG] Future {idx} completed: {result['name']}")
                    
                    # 创建新的结果字典，排除function_args
                    result_for_append = {
                        "role": result["role"],
                        "name": result["name"],
                        "content": result["content"],
                        "tool_call_id": result["tool_call_id"]
                    }
                    results.append(result_for_append)
                    
                    # Record tool execution in plan if available
                    try:
                        if step_index is not None and plan:
                            print(f"[DEBUG] Recording tool execution in plan...")
                            # 解析工具参数
                            json_function_args = result.get('function_args')
                            json_str = json_function_args if json_function_args else '{}'
                            args_dict = json.loads(json_str)
                            plan.record_tool_execution(
                                step_index=step_index,
                                tool_name=result['name'],
                                tool_args=args_dict,
                                result=result['content']
                            )
                            print(f"[DEBUG] Tool execution recorded")
                    except JSONDecodeError as e:
                        print(f"Error recording tool execution: {e}, function_args={json_function_args}  {traceback.format_exc()}")
                    except Exception as e:
                        print(f"Error recording tool execution: {e},{traceback.format_exc()}")

                except Exception as e:
                    print(f"[DEBUG] Future {idx} failed with error: {e}")
                    import traceback
                    print(f"[DEBUG] Traceback:\n{traceback.format_exc()}")
                    results.append({
                        "role": "tool",
                        "name": function_name,
                        "tool_call_id": tool_call.id,
                        "content": f"Execution error: {str(e)}"
                    })
        
        print(f"[DEBUG] === _execute_tool_calls END ({len(results)} results) ===\n")
        return results

    def _handle_max_iteration(self, messages, step_index):
        messages.append({"role": "user", "content": "Summarize the above conversation, use mark_step to mark the step"})
        mark_step_tools = [tool for tool in self.tools if tool['function']['name'] == 'mark_step']
        response = self.llm.create_with_tools(messages, mark_step_tools)
        print(f"max_iteration response:{response}")

        result = self._process_response(response, messages, step_index)
        if result:
            return result

        return messages[-1].get("content")

    @time_record
    @observe()  # Remove static name to allow dynamic naming
    def _execute_tool_call(self, function_name="", function_args="", tool_call_id="", step_index=None, plan: Plan = None):
        print(f"\n[DEBUG] === _execute_tool_call START ===")
        print(f"[DEBUG] Function: {function_name}")
        print(f"[DEBUG] Args (first 200 chars): {function_args[:200] if function_args else 'None'}...")
        print(f"[DEBUG] Tool call ID: {tool_call_id}")
        print(f"[DEBUG] Step index: {step_index}")
        
        # Add dynamic span naming for per-tool tracing with category detection
        if is_langfuse_enabled():
            try:
                # Detect tool category/type for better visibility
                tool_category = self._detect_tool_category(function_name)
                tool_display_name = self._get_tool_display_name(function_name, tool_category)
                
                # Truncate args for metadata (avoid huge traces)
                args_preview = function_args[:500] if function_args else ""
                if len(function_args or "") > 500:
                    args_preview += "... (truncated)"
                
                get_langfuse_client().update_current_span(
                    name=tool_display_name,  # Human-readable name with category!
                    metadata={
                        "tool_function": function_name,
                        "tool_category": tool_category,
                        "tool_call_id": tool_call_id,
                        "step_index": step_index,
                        "args_preview": args_preview,
                        "plan_id": plan.plan_id if plan else None
                    }
                )
                print(f"[DEBUG] Updated Langfuse span: {tool_display_name} (category: {tool_category})")
            except Exception as e:
                print(f"[DEBUG] Failed to update Langfuse span: {e}")
        
        try:
            print(f"[DEBUG] Cleaning and parsing JSON args...")
            # Clean and validate JSON
            cleaned_args = function_args.replace('\\\'', '\'')
            args_dict = json.loads(cleaned_args or "{}")
            print(f"[DEBUG] Parsed args keys: {list(args_dict.keys())}")

            # Add step_index to args_dict if provided and not already present
            if step_index is not None and 'step_index' not in args_dict and function_name in ['mark_step']:
                args_dict['step_index'] = step_index

            print(f"[DEBUG] Looking up function in self.functions...")
            function_to_call = self.functions[function_name]
            print(f"[DEBUG] Function found: {function_to_call.__name__ if hasattr(function_to_call, '__name__') else type(function_to_call)}")

            # 检查是否是异步函数
            is_async = inspect.iscoroutinefunction(function_to_call)
            print(f"[DEBUG] Is async function: {is_async}")
            
            if is_async:
                print(f"[DEBUG] Creating new event loop for async function...")
                # 创建新的事件循环来运行异步函数
                loop = asyncio.new_event_loop()
                try:
                    asyncio.set_event_loop(loop)
                    print(f"[DEBUG] Calling async function with run_until_complete...")
                    result = loop.run_until_complete(function_to_call(**args_dict))
                    print(f"[DEBUG] Async function completed")
                finally:
                    print(f"[DEBUG] Closing event loop...")
                    loop.close()
            else:
                # 同步函数直接调用
                print(f"[DEBUG] Calling sync function directly...")
                result = function_to_call(**args_dict)
                print(f"[DEBUG] Sync function completed")

            print(f"[DEBUG] Converting result to string (first 200 chars): {str(result)[:200]}...")
            result_str = str(result)
            
            # Update span with result metadata
            if is_langfuse_enabled():
                try:
                    tool_category = self._detect_tool_category(function_name)
                    result_preview = result_str[:500] if result_str else ""
                    if len(result_str or "") > 500:
                        result_preview += "... (truncated)"
                    
                    get_langfuse_client().update_current_span(
                        metadata={
                            "tool_function": function_name,
                            "tool_category": tool_category,
                            "tool_call_id": tool_call_id,
                            "step_index": step_index,
                            "args_preview": function_args[:500] if function_args else "",
                            "result_preview": result_preview,
                            "result_length": len(result_str),
                            "plan_id": plan.plan_id if plan else None,
                            "status": "success"
                        }
                    )
                except Exception as e:
                    print(f"[DEBUG] Failed to update span with result: {e}")
            
            print(f"[DEBUG] Creating return dict...")
            return_dict = {
                "role": "tool",
                "name": function_name,
                "content": result_str,
                "tool_call_id": tool_call_id,
                "function_args": function_args
            }
            
            print(f"[DEBUG] === _execute_tool_call END (SUCCESS) ===\n")
            return return_dict
            
        except Exception as e:
            print(f"[DEBUG] === _execute_tool_call END (ERROR) ===")
            print(f"[DEBUG] Error: {e}")
            import traceback
            error_trace = traceback.format_exc()
            print(f"[DEBUG] Traceback:\n{error_trace}")
            
            # Update span with error metadata
            if is_langfuse_enabled():
                try:
                    tool_category = self._detect_tool_category(function_name)
                    get_langfuse_client().update_current_span(
                        metadata={
                            "tool_function": function_name,
                            "tool_category": tool_category,
                            "tool_call_id": tool_call_id,
                            "step_index": step_index,
                            "args_preview": function_args[:500] if function_args else "",
                            "plan_id": plan.plan_id if plan else None,
                            "status": "error",
                            "error_message": str(e),
                            "error_trace": error_trace[:1000]  # Truncate long traces
                        }
                    )
                except Exception as span_error:
                    print(f"[DEBUG] Failed to update span with error: {span_error}")
            
            return {
                "role": "tool",
                "name": function_name,
                "tool_call_id": tool_call_id,
                "content": f"Execution error: {str(e)}"
            }

    @time_record
    def _execute_mcp_tool_call(self, function_name="", function_args="", tool_call_id="", plan: Plan = None):
        try:
            mcp_tool, tool_name = self.find_mcp_tool(function_name)
            if mcp_tool and tool_name:
                cleaned_args = function_args.replace('\\\'', '\'')
                args_dict = json.loads(cleaned_args or "{}")
                result = asyncio.run(
                    MCPEngine.invoke_mcp_tool(mcp_tool['mcp_name'], mcp_tool['mcp_config'], tool_name,
                                              args_dict))
                return {
                    "role": "tool",
                    "name": function_name,
                    "content": str(result),
                    "tool_call_id": tool_call_id,
                    "function_args": function_args
                }
            else:
                return {
                    "role": "tool",
                    "name": function_name,
                    "tool_call_id": tool_call_id,
                    "content": f"Function {function_name} not found in available functions"
                }
        except Exception as e:
            return {
                "role": "tool",
                "name": function_name,
                "tool_call_id": tool_call_id,
                "content": f"Execution error: {str(e)}"
            }
