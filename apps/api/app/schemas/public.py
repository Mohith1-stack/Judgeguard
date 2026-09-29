from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class GallerySort(str, Enum):
    NEWEST = "NEWEST"
    NAME = "NAME"
    RANDOM = "RANDOM"


class GalleryMedia(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    url: HttpUrl | str
    caption: str
    sort_order: int


class GalleryTrack(BaseModel):
    id: UUID
    name: str
    slug: str


class GalleryItem(BaseModel):
    id: UUID
    event_id: UUID
    team_id: UUID
    team_name: str
    track_id: UUID | None
    track_name: str | None
    name: str
    tagline: str
    description: str
    thumbnail_url: HttpUrl | str | None
    demo_video_url: HttpUrl | str | None
    repository_url: HttpUrl | str | None
    live_url: HttpUrl | str | None
    tech_tags: list[str]
    submitted_at: str
    media: list[GalleryMedia]


class GalleryResponse(BaseModel):
    event_id: UUID
    event_name: str
    items: list[GalleryItem]
    tracks: list[GalleryTrack]
    tags: list[str]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=48)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
    sort: GallerySort


class VoteIn(BaseModel):
    submission_id: UUID


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
