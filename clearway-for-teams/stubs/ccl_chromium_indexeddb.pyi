"""Type stubs for ccl_chromium_indexeddb module.

This module provides IndexedDB reading capabilities.
"""

from pathlib import Path
from typing import Any, Iterator

class DbId:
    """Represents a database ID in the IndexedDB metadata."""

    dbid_no: int
    name: str

class RecordKey:
    """Represents a record key in the IndexedDB."""

    value: Any

class Record:
    """Represents a single record from the IndexedDB."""

    key: RecordKey
    value: dict[str, Any] | None

class GlobalMetadata:
    """Represents global metadata for IndexedDB."""

    db_ids: list[DbId]

class IndexedDb:
    """Reader for Chromium IndexedDB LevelDB files."""

    global_metadata: GlobalMetadata

    def __init__(self, path: Path | str) -> None:
        """Initialize the IndexedDB reader."""
        ...

    def close(self) -> None:
        """Close the IndexedDB reader."""
        ...

    def iterate_records(self, db_id: int, store_id: int) -> Iterator[Record]:
        """Iterate over records in a specific database and object store."""
        ...
