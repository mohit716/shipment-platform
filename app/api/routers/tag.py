from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentStaff, CurrentUser
from app.db.session import SessionDep
from app.models.tag import Tag
from app.schemas.tag import TagCreate, TagRead

router = APIRouter(prefix="/tags", tags=["tags"])

TagId = Annotated[int, Path(ge=1, description="Tag reference.")]


async def require_tag(session: AsyncSession, tag_id: int) -> Tag:
    """Return a tag row or abort the request with 404."""
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tag {tag_id} does not exist.",
        )
    return tag


@router.post(
    "",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a handling label",
    responses={
        403: {"description": "Only staff may define handling labels."},
        409: {"description": "That tag already exists."},
    },
)
async def create_tag(
    body: TagCreate,
    session: SessionDep,
    # The vocabulary is only closed if customers cannot extend it.
    current_staff: CurrentStaff,
) -> Tag:
    tag = Tag(**body.model_dump())
    session.add(tag)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tag {body.name} already exists.",
        ) from None
    await session.refresh(tag)
    return tag


@router.get("", response_model=list[TagRead], summary="List handling labels")
async def list_tags(session: SessionDep, current_user: CurrentUser) -> list[Tag]:
    results = await session.exec(select(Tag).order_by(Tag.name))
    return list(results.all())
