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

import re
import json
from typing import Dict, List, Any

from app.agent_dispatcher.infrastructure.entity.AgentInstance import AgentInstance
from app.manus.agent.base.base_agent import BaseAgent
from app.manus.agent.planner.prompt.planner_prompt import planner_system_prompt, \
    planner_create_plan_prompt, planner_re_plan_prompt, planner_finalize_plan_prompt, \
    planner_init_facts_prompt
from app.manus.llm.chat_llm import ChatLLM
from app.manus.llm.langfuse_config import observe
from app.manus.task.plan_report_manager import plan_report_event_manager
from app.manus.task.task_manager import TaskManager
from app.manus.tool.plan_toolkit import PlanToolkit
from app.manus.tool.terminate_toolkit import TerminateToolkit


class TaskPlannerAgent(BaseAgent):
    def __init__(self, agent_instance: AgentInstance, llm: ChatLLM, plan_id, functions: Dict = None):
        self.plan = TaskManager.get_plan(plan_id)
        plan_toolkit = PlanToolkit(self.plan)
        terminate_toolkit = TerminateToolkit()
        all_functions = {"create_plan": plan_toolkit.create_plan, "update_plan": plan_toolkit.update_plan,
                         "terminate": terminate_toolkit.terminate}
        if functions:
            all_functions = functions.update(functions)
        super().__init__(agent_instance, llm, all_functions)

    @observe(name="planner_create_fact")
    def create_fact(self, question):
        self.history.append({"role": "system", "content": planner_system_prompt()})
        self.history.append({"role": "user", "content": planner_init_facts_prompt(question)})
        result = self.llm.chat_to_llm(self.history)
        self.history.append({"role": "assistant", "content": result})
        self.plan.update_facts(result)
        return result

    @observe(name="planner_create_plan")
    def create_plan(self, question, output_format=""):
        # self.history.append({"role": "system", "content": planner_system_prompt()})
        self.history.append(
            {"role": "user", "content": planner_create_plan_prompt(question, self.plan.facts, output_format)})
        result = self.execute(self.history, max_iteration=1)
        return result

    @observe(name="planner_re_plan")
    def re_plan(self, question, output_format=""):
        self.history.append(
            {"role": "user", "content": planner_re_plan_prompt(question, self.plan.format(),self.plan.facts, output_format)})
        result = self.execute(self.history, max_iteration=1)
        # print(f"result of replan is {result}")
        return result

    @observe(name="planner_finalize")
    def finalize_plan(self, question, output_format=""):
        # Get search results for citation generation
        search_results = self.plan.get_search_results() if hasattr(self.plan, 'get_search_results') else []
        self.history.append(
            {"role": "user", "content": planner_finalize_plan_prompt(question, self.plan.format(), output_format, search_results)})
        raw_result = self.execute(self.history, max_iteration=1)
        result = self.extract_pattern(raw_result, "final_answer")
        print(f"raw_resultesult is >>{raw_result}<<, result is {result}")
        self.plan.set_plan_result(result)
        plan_report_event_manager.publish("plan_result", self.plan)
        return result

    def finalize_plan_hle(self, question, output_format=""):
        # Get search results for citation generation
        search_results = self.plan.get_search_results() if hasattr(self.plan, 'get_search_results') else []
        self.history.append(
            {"role": "user", "content": planner_finalize_plan_prompt(question, self.plan.format(), output_format, search_results)})
        raw_result = self.execute(self.history, max_iteration=1)
        result = self.extract_pattern(raw_result, "final_answer")
        print(f"raw_resultesult is >>{raw_result}<<, result is {result}")
        self.plan.set_plan_result(result)
        plan_report_event_manager.publish("plan_result", self.plan)
        return result, raw_result

    def extract_pattern(self, content: str, pattern="final_answer"):
        try:
            _pattern = fr"<{pattern}>(.*?)</{pattern}>"
            matches = re.findall(_pattern, content, re.DOTALL)
            if matches:
                text = matches[-1]
                return text.strip()
            else:
                return content
        except Exception as e:
            print(f"Error extracting answer: {e}, current content: {content}")
            return content
    
    def _parse_plan_from_text(self, text_response: str) -> dict:
        """
        Fallback parser: Extract plan structure from text response when LLM doesn't call create_plan tool.
        
        Parses formats like:
        - title: Research radar data representation
        - steps: ["Search ArXiv for papers", "Analyze findings", ...]
        - dependencies: {1: [0], 2: [0, 1]}
        
        Returns dict with keys: title, steps, dependencies (or None if parsing fails)
        """
        try:
            print("[FALLBACK] LLM returned text instead of calling create_plan tool. Attempting to parse...")
            
            # Extract title
            title_match = re.search(r'title:\s*(.+?)(?:\n|$)', text_response, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else "Research Plan"
            
            # Extract steps - try multiple formats
            steps = []
            
            # Format 1: steps: ["step1", "step2", ...]
            steps_match = re.search(r'steps:\s*(\[.+?\])', text_response, re.IGNORECASE | re.DOTALL)
            if steps_match:
                try:
                    steps = json.loads(steps_match.group(1))
                except:
                    # Try with single quotes
                    steps_str = steps_match.group(1).replace("'", '"')
                    steps = json.loads(steps_str)
            else:
                # Format 2: Numbered or bulleted list
                # Look for patterns like "1.", "2.", or "-", "*"
                list_pattern = r'(?:^\d+[\.\)]\s*|\n\d+[\.\)]\s*|\n[-*]\s*)(.+?)(?=\n\d+[\.\)]|\n[-*]|\n\n|$)'
                list_matches = re.findall(list_pattern, text_response, re.MULTILINE)
                if list_matches:
                    steps = [s.strip() for s in list_matches if s.strip()]
            
            # Extract dependencies
            dependencies = {}
            dep_match = re.search(r'dependencies:\s*(\{.+?\})', text_response, re.IGNORECASE | re.DOTALL)
            if dep_match:
                try:
                    dependencies = json.loads(dep_match.group(1))
                    # Convert string keys to int if needed
                    dependencies = {int(k): v for k, v in dependencies.items()}
                except Exception as e:
                    print(f"[FALLBACK] Could not parse dependencies: {e}")
                    dependencies = {}
            
            # Validation
            if not steps:
                print("[FALLBACK] Failed to extract steps from text response")
                return None
            
            result = {
                "title": title,
                "steps": steps,
                "dependencies": dependencies
            }
            
            print(f"[FALLBACK] Successfully parsed plan:")
            print(f"  - Title: {title}")
            print(f"  - Steps: {len(steps)} steps")
            print(f"  - Dependencies: {len(dependencies)} dependency groups")
            
            return result
            
        except Exception as e:
            print(f"[FALLBACK] Parsing failed: {e}")
            return None
    
    @observe(name="planner_execute_with_fallback")
    def execute(self, messages: List[Dict[str, Any]], step_index=None, plan=None, max_iteration=10):
        """
        Override base execute to add fallback parsing for create_plan responses.
        """
        # Call parent execute
        result = super().execute(messages, step_index, plan, max_iteration)
        
        # Check if we're in create_plan or update_plan context and got text instead of tool call
        # Look for the create_plan prompt in recent messages
        is_plan_creation = any("create_plan tool" in (msg.get("content") or "").lower() 
                               for msg in messages[-3:] if isinstance(msg, dict))
        
        # If result is a string (not from tool execution) and we're in planning context
        if isinstance(result, str) and is_plan_creation and "title:" in result.lower():
            print("[FALLBACK] Detected text-based plan response, attempting to parse and call tool manually...")
            
            parsed_plan = self._parse_plan_from_text(result)
            
            if parsed_plan:
                # Manually call create_plan function with parsed data
                try:
                    print("[FALLBACK] Calling create_plan function with parsed data...")
                    tool_result = self.functions["create_plan"](**parsed_plan)
                    print(f"[FALLBACK] Successfully executed create_plan: {tool_result}")
                    return tool_result
                except Exception as e:
                    print(f"[FALLBACK] Failed to call create_plan function: {e}")
                    # Fall through to return original result
        
        return result

