from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompts import knowledge_ingestion_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

knowledge_ingestion_agent = LlmAgent(
    name="KnowledgeIngestionAgent",
    description=(
        "Prepares extracted POIs and insights for storage in the knowledge base, returning indexable entries."
    ),
    instruction=knowledge_ingestion_prompt,
    model=model,
    output_key="knowledge_ingestion_output",
)


