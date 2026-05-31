"""Detached post-turn tutor follow-up work (conversation summary + learner state).

These refinements run AFTER the visible turn's `done` event. Previously they ran
inline in the request handler, which held the request's pooled DB connection open
for the duration of an extra LLM call. Now they are detached onto a background
task that owns its OWN session (built from the app sessionmaker), mirroring the
primer generation manager: the request connection is released as soon as the
stream finishes, and the follow-up runs to completion independently.

Safe to detach because `persist_assistant_turn` has already committed every turn
of the visible exchange before `done` is emitted, so the background session reads
fully-committed data.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from typing import TYPE_CHECKING

from backend.app.models.concept import ConceptNode
from backend.app.services.conversation_summaries import (
    LLMConversationSummarizer,
    maybe_generate_conversation_summary,
)
from backend.app.services.learner_state import (
    LLMLearnerStateObserver,
    maybe_update_learner_state_from_chat,
)
from backend.app.settings import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from backend.app.agents.llm_client import LLMClient

logger = logging.getLogger(__name__)


async def run_tutor_followups(
    session_factory: async_sessionmaker[AsyncSession],
    client: LLMClient,
    *,
    workspace_id: uuid.UUID,
    concept_id: uuid.UUID,
    conversation_id: uuid.UUID,
    through_turn_index: int,
) -> None:
    """Run summary + learner-state refinement in a fresh, owned session.

    Each step is independently failure-isolated: a failure in one (or a rollback)
    never affects the already-committed visible turn or the other step.
    """
    async with session_factory() as session:
        try:
            await maybe_generate_conversation_summary(
                session,
                LLMConversationSummarizer(client),
                conversation_id=conversation_id,
                through_turn_index=through_turn_index,
                recent_visible_turns_limit=settings.tutor_recent_visible_turns_limit,
                history_char_budget=settings.tutor_history_char_budget,
                batch_size=settings.tutor_summary_batch_size,
            )
            await session.commit()
        except Exception as exc:
            logger.warning("Conversation summary generation failed: %s", exc)
            await session.rollback()

        if settings.learner_state_update_interval > 0:
            try:
                concept = await session.get(ConceptNode, concept_id)
                if concept is not None:
                    await maybe_update_learner_state_from_chat(
                        session,
                        LLMLearnerStateObserver(client),
                        workspace_id=workspace_id,
                        concept=concept,
                        conversation_id=conversation_id,
                        interval=settings.learner_state_update_interval,
                        recent_visible_turns_limit=settings.tutor_recent_visible_turns_limit,
                    )
                    await session.commit()
            except Exception as exc:
                logger.warning("Learner-state update failed: %s", exc)
                await session.rollback()


class TutorFollowupManager:
    """Owns detached post-turn follow-up tasks.

    Tasks are created with ``asyncio.create_task`` and are NOT tied to the
    request that started them, so the request connection is released immediately.
    ``main.py``'s lifespan owns clean shutdown via :meth:`shutdown`.
    """

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()

    def schedule(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: LLMClient,
        *,
        workspace_id: uuid.UUID,
        concept_id: uuid.UUID,
        conversation_id: uuid.UUID,
        through_turn_index: int,
    ) -> asyncio.Task[None]:
        task = asyncio.create_task(
            self._run(
                session_factory,
                client,
                workspace_id=workspace_id,
                concept_id=concept_id,
                conversation_id=conversation_id,
                through_turn_index=through_turn_index,
            )
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _run(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        client: LLMClient,
        **kwargs: uuid.UUID | int,
    ) -> None:
        try:
            await run_tutor_followups(session_factory, client, **kwargs)  # type: ignore[arg-type]
        except asyncio.CancelledError:
            raise
        except Exception:  # background safety net: never crash the loop.
            logger.exception("detached tutor follow-up failed")

    async def shutdown(self) -> None:
        """Cancel and await any outstanding follow-up tasks (lifespan teardown)."""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task

    async def drain(self) -> None:
        """Await all outstanding follow-up tasks (tests / graceful flush)."""
        while self._tasks:
            tasks = list(self._tasks)
            await asyncio.gather(*tasks, return_exceptions=True)


# Process-wide registry of in-flight follow-up tasks. Instantiated at import;
# main.py's lifespan owns its clean shutdown. Replace with a shared external
# worker/queue if post-turn refinement moves off-process.
tutor_followup_manager = TutorFollowupManager()
