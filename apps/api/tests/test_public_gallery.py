from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.public import GalleryResponse, GallerySort


def test_gallery_sort_enum():
    assert GallerySort.NEWEST.value == "NEWEST"
    assert GallerySort.NAME.value == "NAME"
    assert GallerySort.RANDOM.value == "RANDOM"


def test_gallery_response_rejects_zero_page_size():
    with pytest.raises(ValidationError):
        GalleryResponse(
            event_id=uuid4(),
            event_name="Event",
            items=[],
            tracks=[],
            tags=[],
            page=1,
            page_size=0,
            total_items=0,
            total_pages=0,
            sort=GallerySort.NEWEST,
        )
