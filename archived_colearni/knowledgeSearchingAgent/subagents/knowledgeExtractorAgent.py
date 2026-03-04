from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompts import knowledge_extractor_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

knowledge_extractor_agent = LlmAgent(
    name="KnowledgeExtractorAgent",
    description=(
        "Identifies POIs and extracts key insights from gathered sources, tailored to user context."
    ),
    instruction=knowledge_extractor_prompt,
    model=model,
    output_key="knowledge_extractor_output",
)


