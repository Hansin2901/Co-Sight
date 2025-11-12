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
import json
import os
import sys
import traceback

# Temporarily commented out for citation tracking test
# from browser_use import Agent
# from browser_use.agent.views import AgentHistoryList
# from browser_use.browser.browser import Browser, BrowserConfig
# from browser_use.browser.context import BrowserContext, BrowserContextConfig
from dotenv import load_dotenv
# from langchain_openai import ChatOpenAI
from mcp.server.fastmcp import FastMCP
from pydantic import Field
import asyncio
# from aworld.logs.util import logger
from app.common.infrastructure.utils.log import logger  # Use existing logger
# from browser_use.agent.memory import MemoryConfig

browser_system_prompt = """
===== NAVIGATION STRATEGY =====
1. START: Navigate to the most authoritative source for this information
   - For general queries: Use Google with specific search terms
   - For known sources: Go directly to the relevant website

2. EVALUATE: Assess each page methodically
   - Scan headings and highlighted text first
   - Look for data tables, charts, or official statistics
   - Check publication dates for timeliness

3. EXTRACT: Capture exactly what's needed
   - Take screenshots of visual evidence (charts, tables, etc.)
   - Copy precise text that answers the query
   - Note source URLs for citation

4. DOWNLOAD: Save the most relevant file to local path for further processing
   - Save the text if possible for futher text reading and analysis
   - Save the image if possible for futher image reasoning analysis
   - Save the pdf if possible for futher pdf reading and analysis

5. ROBOT DETECTION:
   - If the page is a robot detection page, abort immediately
   - Navigate to the most authoritative source for similar information instead

===== EFFICIENCY GUIDELINES =====
- Use specific search queries with key terms from the task
- Avoid getting distracted by tangential information
- If blocked by paywalls, try archive.org or similar alternatives
- Document each significant finding clearly and concisely

Your goal is to extract precisely the information needed with minimal browsing steps.
"""


async def browser_use(
        task_prompt: str = Field(description="The task to perform using the browser."),
) -> str:
    """
    Perform browser actions using the browser-use package.
    Args:
        task_prompt (str): The task to perform using the browser.
    Returns:
        str: The result of the browser actions.
    """
    browser = Browser(
        config=BrowserConfig(
            headless=False,
            new_context_config=BrowserContextConfig(
                disable_security=True,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                minimum_wait_page_load_time=10,
                maximum_wait_page_load_time=30,
            ),
        )
    )
    browser_context = BrowserContext(
        config=BrowserContextConfig(
            trace_path=os.getenv("browser_trace.log")
        ),
        browser=browser,
    )
    agent = Agent(
        task=task_prompt,
        llm=ChatOpenAI(
            model=os.getenv("TOOL_MODEL_NAME"),
            api_key=os.getenv("TOOL_API_KEY"),
            base_url=os.getenv("TOOL_API_BASE_URL"),
            model_name=os.getenv("TOOL_MODEL_NAME"),
            openai_api_base=os.getenv("TOOL_API_BASE_URL"),
            openai_api_key=os.getenv("TOOL_API_KEY"),
            temperature=1.0,
        ),
        browser_context=browser_context,
        extend_system_message=browser_system_prompt,
    )
    try:
        browser_execution: AgentHistoryList = await agent.run(max_steps=50)
        if (
                browser_execution is not None
                and browser_execution.is_done()
                and browser_execution.is_successful()
        ):
            exec_trace = browser_execution.extracted_content()
            print(
                ">>> 🌏 Browse Execution Succeed!\n"
                f">>> 💡 Result: {json.dumps(exec_trace, ensure_ascii=False, indent=4)}\n"
                ">>> 🌏 Browse Execution Succeed!\n"
            )
            print(f"Browser execution success for task: {task_prompt}, result {browser_execution.final_result()}")
            return browser_execution.final_result()
        else:
            return f"Browser execution failed for task: {task_prompt}"
    except Exception as e:
        print(f"Browser execution failed: {traceback.format_exc()}")
        return f"Browser execution failed for task: {task_prompt} due to {str(e)}"
    finally:
        await browser.close()
        print("Browser Closed!")


def sync_browser_use(task_prompt):
    return asyncio.run(browser_use(task_prompt))


if __name__ == "__main__":
    load_dotenv(override=True)
    os.environ['OPENAI_API_KEY'] = os.environ.get('TOOL_API_KEY', '')
    try:
        sync_browser_use("在所提供图像中动物的维基百科页面上，2020 年之前的多少次修订具有“视觉编辑”标签？")
    except Exception as e:
        print(f"Error: {e}")
