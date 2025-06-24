from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.langchain_tool import LangchainTool
from langchain_community.tools import TavilySearchResults
from .prompts import tavily_search_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

tavily_tool_instance = TavilySearchResults(
    max_results=5,
    search_depth="advanced",
    include_answer=True,
    include_raw_content=True,
    include_images=True,
)

tavily_tool = LangchainTool(tavily_tool_instance)

tavily_search_agent = LlmAgent(
    name="TavilySearchAgent",
    description="A specialized sub-agent that uses Tavily Search API to find high-quality, relevant, better suited to finding information on the web.",
    instruction=tavily_search_prompt,
    model=model,
    tools=[
        tavily_tool
        ],
    output_key="tavily_search_results",
)