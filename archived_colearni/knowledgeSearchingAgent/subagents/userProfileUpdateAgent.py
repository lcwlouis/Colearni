from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from .prompts import user_profile_update_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))

user_profile_update_agent = LlmAgent(
    name="UserProfileUpdateAgent",
    description=(
        "Updates user profile based on feedback to guide future searches."
    ),
    instruction=user_profile_update_prompt,
    model=model,
    output_key="user_profile_update_output",
)


