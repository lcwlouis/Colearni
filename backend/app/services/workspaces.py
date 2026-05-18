import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.workspace import Workspace

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE_NAME = "My Workspace"


async def ensure_default_workspace(session: AsyncSession) -> Workspace:
    """Create the default workspace if none exists.

    Called at startup for local-ready single-user mode. Safe to call multiple
    times — returns the existing workspace without creating a duplicate.
    When auth + multi-user support is added, replace the lifespan call with
    user-scoped workspace provisioning instead.
    """
    existing = await session.scalar(select(Workspace).limit(1))
    if existing is not None:
        logger.debug("Default workspace already exists: id=%s", existing.id)
        return existing
    workspace = Workspace(name=DEFAULT_WORKSPACE_NAME)
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    logger.info("Created default workspace: id=%s name=%r", workspace.id, workspace.name)
    return workspace


async def create_workspace(session: AsyncSession, *, name: str) -> Workspace:
    workspace = Workspace(name=name)
    session.add(workspace)
    await session.commit()
    await session.refresh(workspace)
    return workspace


async def list_workspaces(session: AsyncSession) -> list[Workspace]:
    return list(await session.scalars(select(Workspace).order_by(Workspace.created_at)))


async def get_workspace(session: AsyncSession, *, workspace_id: uuid.UUID) -> Workspace:
    workspace = await session.get(Workspace, workspace_id)
    if workspace is None:
        raise LookupError(f"Workspace {workspace_id} not found")
    return workspace
