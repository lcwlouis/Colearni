from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.tool_context import ToolContext
from .prompts import research_reviewer_prompt

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

model = LiteLlm(
    model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY")
)


def exit_loop(tool_context: ToolContext):
    """Call this function ONLY when the critique indicates no further changes are needed, signaling the iterative process should end."""
    print(f"  [Tool Call] exit_loop triggered by {tool_context.agent_name}")
    tool_context.actions.escalate = True
    # Return empty dict as tools should typically return JSON-serializable output
    return {}


research_reviewer_agent = LlmAgent(
    name="ResearchReviewerAgent",
    description="A specialized sub-agent that reviews the research plan and the results from the search agent.",
    instruction=research_reviewer_prompt,
    model=model,
    tools=[exit_loop],
    output_key="research_reviewer_output",
)
