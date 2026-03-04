from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompts import quiz_generator_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

quiz_generator_agent = LlmAgent(
    name="QuizGeneratorAgent",
    description=(
        "Generates an interactive quiz from extracted POIs and insights to validate understanding."
    ),
    instruction=quiz_generator_prompt,
    model=model,
    output_key="quiz_generator_output",
)


