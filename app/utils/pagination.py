from __future__ import annotations

from math import ceil


def build_pagination_meta(*, total: int, page: int, page_size: int) -> dict[str, int]:
    """Build a consistent pagination payload."""
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": ceil(total / page_size) if page_size else 0,
    }
