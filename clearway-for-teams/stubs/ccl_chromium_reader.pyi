"""Type stubs for the ccl_chromium_reader library.

This library provides tools for reading Chromium browser data files,
including IndexedDB LevelDB storage.
"""

from pathlib import Path
from typing import Any, Iterator

class DbId:
    """Represents a database ID in the IndexedDB metadata.

    Attributes:
        dbid_no: The numeric database ID.
        name: The name of the database.
    """

    dbid_no: int
    name: str

class RecordKey:
    """Represents a record key in the IndexedDB.

    Attributes:
        value: The raw key value.
    """

    value: Any

class Record:
    """Represents a single record from the IndexedDB.

    Attributes:
        key: The record key containing the key value.
        value: The record value as a dictionary.
    """

    key: RecordKey
    value: dict[str, Any] | None

class GlobalMetadata:
    """Represents global metadata for IndexedDB.

    Attributes:
        db_ids: List of database IDs in the IndexedDB.
    """

    db_ids: list[DbId]

class IndexedDb:
    """Reader for Chromium IndexedDB LevelDB files.

    This class provides access to Chromium browser's IndexedDB LevelDB
    database files for forensic analysis and data extraction.

    Args:
        path: Path to the IndexedDB LevelDB directory.

    Example:
        >>> db = IndexedDb(Path("/path/to/indexeddb.leveldb"))
        >>> for db_id in db.global_metadata.db_ids:
        ...     print(f"Database: {db_id.name} (ID: {db_id.dbid_no})")
        >>> for record in db.iterate_records(db_id=1, store_id=1):
        ...     print(f"Key: {record.key.value}, Value: {record.value}")
        >>> db.close()
    """

    global_metadata: GlobalMetadata

    def __init__(self, path: Path | str) -> None:
        """Initialize the IndexedDB reader.

        Args:
            path: Path to the IndexedDB LevelDB directory.
        """
        ...

    def close(self) -> None:
        """Close the IndexedDB reader and release resources."""
        ...

    def iterate_records(self, db_id: int, store_id: int) -> Iterator[Record]:
        """Iterate over records in a specific database and object store.

        Args:
            db_id: The database ID to read from.
            store_id: The object store ID within the database.

        Yields:
            Record objects containing key-value pairs from the database.
        """
        ...
