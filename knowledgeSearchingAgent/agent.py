from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from .prompt import lead_expert_prompt, final_response_prompt
from .subagents import google_search_agent, tavily_search_agent, searxng_search_agent, research_planner_agent, research_reviewer_agent

import logging
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

litellm_model = LiteLlm(model="deepseek/deepseek-chat", api_key=os.getenv("DEEPSEEK_API_KEY"))


research_executor_agent = LlmAgent(
    name="ResearchExecutorAgent",
    description=(
        "Research Execution Agent. Given a research plan, this agent delegates search queries to its sub-agents "
        "(Google, Tavily, SearxNG) to gather resources. It aggregates the findings and passes them on for review."
    ),
    instruction=lead_expert_prompt,
    model=litellm_model,
    sub_agents=[
        # google_search_agent,
        # tavily_search_agent,
        searxng_search_agent,
    ],
    generate_content_config=types.GenerateContentConfig(temperature=0.5),
    output_key="research_output",
)

loop_search_agent = LoopAgent(
    name="KnowledgeResearcher",
    description=(
        "The lead orchestrator for knowledge searching. It coordinates a sequence of sub-agents "
        "(planner, executor, reviewer) to take a user's topic and produce a comprehensive, "
        "curated set of learning resources."
    ),
    sub_agents=[
        research_planner_agent,
        research_executor_agent,
        research_reviewer_agent
    ],
    max_iterations=3,
)

final_response_agent = LlmAgent(
    name="FinalResponseAgent",
    description="Returns the final response to the user",
    instruction=final_response_prompt,
    model=litellm_model,
    output_key="final_response",
    generate_content_config=types.GenerateContentConfig(temperature=0.5),
)

root_agent = SequentialAgent(
    name="KnowledgeSearchExpert",
    description=(
        "Starts the research process and returns the final response"
    ),
    sub_agents=[
        loop_search_agent,
        final_response_agent
    ],
)