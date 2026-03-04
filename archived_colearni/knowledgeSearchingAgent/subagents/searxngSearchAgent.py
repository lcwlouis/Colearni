from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.langchain_tool import LangchainTool
from langchain_community.tools import SearxSearchResults
from langchain_community.utilities.searx_search import SearxSearchWrapper
from .prompts import searxng_search_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

searxng_tool_instance = SearxSearchResults(
    wrapper=SearxSearchWrapper(
        searx_host=(
            os.getenv("SEARXNG_HOST")
            or os.getenv("SEARXNG_API_URL")
        ),
    ),
    num_results=5,
    description="A tool that uses the SearxNG metasearch engine to find high-quality, relevant, and authoritative information to support deep learning and research objectives."
)

searxng_tool = LangchainTool(searxng_tool_instance)

searxng_search_agent = LlmAgent(
    name="SearxNGSearchAgent",
    description="A specialized sub-agent that uses the SearxNG metasearch engine to find high-quality, relevant, and authoritative information to support deep learning and research objectives.",
    instruction=searxng_search_prompt,
    model=model,
    tools=[
        searxng_tool
    ],
    output_key="searxng_search_results",
)