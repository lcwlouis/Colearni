from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from .prompt import lead_expert_prompt, final_response_prompt
from .subagents import (
    google_search_agent,
    tavily_search_agent,
    searxng_search_agent,
    research_planner_agent,
    research_reviewer_agent,
    knowledge_finder_agent,
    knowledge_extractor_agent,
    quiz_generator_agent,
    knowledge_ingestion_agent,
    user_profile_update_agent,
)

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

# Step 6 agent can be chained after reviewer once user selects POIs.
knowledge_finder_sequence = SequentialAgent(
    name="KnowledgeFinderSequence",
    description="Takes selected POIs and user context to produce targeted SearxNG queries.",
    sub_agents=[
        knowledge_finder_agent,
    ],
)

knowledge_extractor_sequence = SequentialAgent(
    name="KnowledgeExtractorSequence",
    description="Extracts POIs and insights from gathered sources using user context.",
    sub_agents=[
        knowledge_extractor_agent,
    ],
)

quiz_generator_sequence = SequentialAgent(
    name="QuizGeneratorSequence",
    description="Generates an interactive quiz from extracted POIs and insights.",
    sub_agents=[
        quiz_generator_agent,
    ],
)

knowledge_ingestion_sequence = SequentialAgent(
    name="KnowledgeIngestionSequence",
    description="Prepares extracted POIs and insights for storage.",
    sub_agents=[
        knowledge_ingestion_agent,
    ],
)

user_profile_update_sequence = SequentialAgent(
    name="UserProfileUpdateSequence",
    description="Updates user profile from feedback.",
    sub_agents=[
        user_profile_update_agent,
    ],
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
        # knowledge_finder_sequence is intended to be invoked after user selects POIs
        final_response_agent
    ],
)


def generate_step6_queries(selected_pois, user_context):
    """
    Run Step 6 (Knowledge Finder) to produce targeted SearxNG search queries.

    Returns final markdown string.
    """
    message = (
        "Selected POIs:\n" + str(selected_pois) + "\n\n" +
        "User Context:\n" + str(user_context)
    )
    app_name = "sapientian"
    user_id = "user_local"
    session_id = "step6"
    runner = InMemoryRunner(agent=knowledge_finder_sequence, app_name=app_name)
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async def _run():
        nonlocal final_text
        # Ensure session exists
        session = None
        try:
            session = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception:
            session = None
        if not session:
            await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts and event.content.parts[0].text:
                final_text = event.content.parts[0].text
    import asyncio
    asyncio.run(_run())
    return final_text


def extract_pois_and_insights(sources, user_context):
    """
    Step 8–9a: Run Knowledge Extractor on the gathered sources.
    Returns final markdown string.
    """
    message = (
        "Sources (JSON):\n" + str(sources) + "\n\n" +
        "User Context:\n" + str(user_context)
    )
    app_name = "sapientian"
    user_id = "user_local"
    session_id = "step8"
    runner = InMemoryRunner(agent=knowledge_extractor_sequence, app_name=app_name)
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async def _run():
        nonlocal final_text
        session = None
        try:
            session = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception:
            session = None
        if not session:
            await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts and event.content.parts[0].text:
                final_text = event.content.parts[0].text
    import asyncio
    asyncio.run(_run())
    return final_text


def generate_quiz_from_extracted(extracted_markdown):
    """
    Step 9b: Generate a quiz from extracted POIs and insights.
    Returns final markdown string.
    """
    message = "Extracted POIs and Insights Markdown:\n\n" + extracted_markdown
    app_name = "sapientian"
    user_id = "user_local"
    session_id = "step9"
    runner = InMemoryRunner(agent=quiz_generator_sequence, app_name=app_name)
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async def _run():
        nonlocal final_text
        session = None
        try:
            session = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception:
            session = None
        if not session:
            await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts and event.content.parts[0].text:
                final_text = event.content.parts[0].text
    import asyncio
    asyncio.run(_run())
    return final_text


def ingest_extracted_after_pass(extracted_markdown, quiz_result):
    """
    Step 10: Ingest extracted POIs and insights into knowledge base (preparation output only).
    Returns final markdown string.
    """
    message = (
        "Extracted Markdown:\n\n" + extracted_markdown + "\n\n" +
        "Quiz Result:\n" + str(quiz_result)
    )
    app_name = "sapientian"
    user_id = "user_local"
    session_id = "step10"
    runner = InMemoryRunner(agent=knowledge_ingestion_sequence, app_name=app_name)
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async def _run():
        nonlocal final_text
        session = None
        try:
            session = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception:
            session = None
        if not session:
            await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts and event.content.parts[0].text:
                final_text = event.content.parts[0].text
    import asyncio
    asyncio.run(_run())
    return final_text


def update_user_profile(feedback, current_profile):
    """
    Step 11: Update user profile JSON based on feedback.
    Returns dict.
    """
    message = (
        "Feedback (JSON):\n" + str(feedback) + "\n\n" +
        "Current Profile (JSON):\n" + str(current_profile)
    )
    app_name = "sapientian"
    user_id = "user_local"
    session_id = "step11"
    runner = InMemoryRunner(agent=user_profile_update_sequence, app_name=app_name)
    content = types.Content(role="user", parts=[types.Part(text=message)])
    final_text = ""
    async def _run():
        nonlocal final_text
        try:
            await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception:
            await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts and event.content.parts[0].text:
                final_text = event.content.parts[0].text
    import asyncio
    asyncio.run(_run())
    # Try to parse JSON; fallback to raw string envelope
    try:
        import json
        return json.loads(final_text)
    except Exception:
        return {"raw": final_text}


def run_steps_1_4(topic: str):
    """Run the planner → executor → reviewer → final response pipeline with a topic.

    Returns a dict with final_text and (if available) session state.
    """
    app_name = "sapientian"
    user_id = "user_local"
    session_id = "steps1_4"
    runner = InMemoryRunner(agent=root_agent, app_name=app_name)
    content = types.Content(role="user", parts=[types.Part(text=f"Topic: {topic}")])
    final_text = ""
    state_dict = {}
    async def _run():
        nonlocal final_text, state_dict
        session_obj = None
        try:
            session_obj = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        except Exception:
            session_obj = None
        if not session_obj:
            await runner.session_service.create_session(app_name=app_name, user_id=user_id, session_id=session_id)
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response() and event.content and event.content.parts and event.content.parts[0].text:
                final_text = event.content.parts[0].text
        # capture session state for debugging/inspection
        session_obj = await runner.session_service.get_session(app_name=app_name, user_id=user_id, session_id=session_id)
        state_dict = session_obj.state.to_dict() if hasattr(session_obj, 'state') else {}
    import asyncio
    asyncio.run(_run())
    return {"final": final_text, "state": state_dict}