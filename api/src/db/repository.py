"""Generic async repository pattern with typed CRUD operations."""

from __future__ import annotations

import uuid
from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.database import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository for SQLAlchemy async models."""

    def __init__(self, model: type[ModelT], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: uuid.UUID) -> ModelT | None:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[ModelT], int]:
        query = select(self.model)
        count_query = select(func.count()).select_from(self.model)

        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.where(
                        getattr(self.model, key) == value  # type: ignore[attr-defined]
                    )
                    count_query = count_query.where(
                        getattr(self.model, key) == value  # type: ignore[attr-defined]
                    )

        total_result = await self.session.execute(count_query)
        total = total_result.scalar_one()

        result = await self.session.execute(query.offset(skip).limit(limit))
        items = list(result.scalars().all())

        return items, total

    async def create(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def update(self, obj: ModelT, data: dict[str, Any]) -> ModelT:
        for key, value in data.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
        await self.session.flush()
        await self.session.refresh(obj)
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def count(self, filters: dict[str, Any] | None = None) -> int:
        query = select(func.count()).select_from(self.model)
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.where(getattr(self.model, key) == value)  # type: ignore[attr-defined]
        result = await self.session.execute(query)
        return result.scalar_one()
