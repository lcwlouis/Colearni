import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.workspace import Workspace


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
