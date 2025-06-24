from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompts import research_planner_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

research_planner_agent = LlmAgent(
    name="ResearchPlannerAgent",
    description="A specialized sub-agent that creates a research plan based on the supervisor's instructions.",
    instruction=research_planner_prompt,
    model=model,
    output_key="research_planner_output",
)