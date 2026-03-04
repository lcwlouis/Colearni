from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompts import knowledge_finder_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

knowledge_finder_agent = LlmAgent(
    name="KnowledgeFinderAgent",
    description=(
        "Generates a targeted set of SearxNG-optimized search queries from user-selected POIs "
        "and user context to discover academic papers and expert posts."
    ),
    instruction=knowledge_finder_prompt,
    model=model,
    output_key="knowledge_finder_queries",
)


