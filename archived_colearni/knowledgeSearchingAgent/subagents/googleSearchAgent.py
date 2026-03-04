from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from google.adk.tools.agent_tool import AgentTool
from google.adk.models.lite_llm import LiteLlm
from .prompts import google_search_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

litellm_model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))
model = "gemini-2.0-flash"

tool_google_search_agent = LlmAgent(
    name="GoogleSearchAgent",
    description="A specialized sub-agent that uses Google Search API to find high-quality, relevant, and authoritative information for deep learning and research.",
    instruction=google_search_prompt,
    model=model,
    tools=[google_search],
    output_key="google_search_results",
)

google_search_agent = LlmAgent(
    name="GoogleSearchAgent",
    description="A specialized sub-agent that uses Google Search API to find high-quality, relevant, and authoritative information for deep learning and research.",
    instruction="Delegate to your agent tool to find the most relevant information for the user's query.",
    model=litellm_model,
    tools=[AgentTool(tool_google_search_agent)],
    output_key="google_search_results",
)
