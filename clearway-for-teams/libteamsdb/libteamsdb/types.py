"""Type stubs and wrappers for ccl_chromium_reader library.

This module provides typed interfaces to the ccl_chromium_reader library
to avoid Any types and ensure mypy strict mode compatibility.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Dict,
    Iterator,
    List,
    Optional,
    Protocol,
    Union,
    runtime_checkable,
)


@runtime_checkable
class IndexedDbKey(Protocol):
    """Protocol for IndexedDB record keys."""

    @property
    def value(self) -> Union[str, int, bytes]: ...


@runtime_checkable
class IndexedDbRecord(Protocol):
    """Protocol for IndexedDB records."""

    @property
    def key(self) -> IndexedDbKey: ...

    @property
    def value(self) -> Optional[Dict[str, Any]]: ...


@runtime_checkable
class DatabaseId(Protocol):
    """Protocol for database IDs."""

    @property
    def dbid_no(self) -> int: ...

    @property
    def name(self) -> str: ...


@runtime_checkable
class GlobalMetadata(Protocol):
    """Protocol for global metadata."""

    @property
    def db_ids(self) -> List[DatabaseId]: ...


class IndexedDbWrapper:
    """Typed wrapper for ccl_chromium_indexeddb.IndexedDb.

    This wrapper provides proper type annotations for the IndexedDb class
    from the ccl_chromium_reader library, allowing mypy strict mode
    to work without Any types.
    """

    def __init__(self, db_path: Path) -> None:
        """Initialize the IndexedDB wrapper.

        Args:
            db_path: Path to the LevelDB database directory
        """
        # Import here to avoid circular imports and allow for proper error handling
        try:
            from ccl_chromium_reader import ccl_chromium_indexeddb

            self._db: Any = ccl_chromium_indexeddb.IndexedDb(db_path)
        except ImportError as e:
            raise ImportError(
                "ccl_chromium_reader is required but not installed. "
                "Please install it: pip install ccl-chromium-reader"
            ) from e

    @property
    def global_metadata(self) -> GlobalMetadata:
        """Get the global metadata object."""
        return self._db.global_metadata

    def iterate_records(self, db_id: int, store_id: int) -> Iterator[IndexedDbRecord]:
        """Iterate over records in a database store.

        Args:
            db_id: Database ID number
            store_id: Store ID number within the database

        Yields:
            IndexedDbRecord objects
        """
        yield from self._db.iterate_records(db_id, store_id)

    def close(self) -> None:
        """Close the database connection."""
        self._db.close()


def parse_timestamp(ts_raw: object) -> datetime:
    """Parse a Teams timestamp value into a datetime object.

    Teams stores timestamps in various formats (milliseconds, seconds, or strings).
    This function handles all common cases and returns a valid datetime.

    Args:
        ts_raw: Raw timestamp value from the database (int, float, str, or None)

    Returns:
        Parsed datetime object (defaults to current time if parsing fails)
    """
    if ts_raw is None:
        return datetime.now()

    try:
        # Convert to float if it's a string or number
        if isinstance(ts_raw, str):
            ts_float = float(ts_raw.strip())
        elif isinstance(ts_raw, (int, float)):
            ts_float = float(ts_raw)
        else:
            return datetime.now()

        # Teams timestamps are often in milliseconds (large values)
        if ts_float > 1e12:
            return datetime.fromtimestamp(ts_float / 1000.0)
        elif ts_float > 0:
            return datetime.fromtimestamp(ts_float)
        else:
            return datetime.now()
    except (OSError, ValueError, OverflowError, TypeError):
        return datetime.now()


def parse_consumption_horizon(horizon_raw: Union[str, int, float, None]) -> float:
    """Parse a consumption horizon value.

    Consumption horizons are semicolon-separated lists of timestamps.
    We return the maximum valid timestamp from the list.

    Args:
        horizon_raw: Raw consumption horizon value

    Returns:
        Maximum timestamp value (0.0 if parsing fails)
    """
    if horizon_raw is None:
        return 0.0

    try:
        horizon_str = str(horizon_raw)
        parts = horizon_str.split(";")
        max_horizon = 0.0

        for part in parts:
            try:
                val = float(part.strip())
                if val > max_horizon:
                    max_horizon = val
            except (ValueError, TypeError):
                continue

        return max_horizon
    except (ValueError, TypeError):
        return 0.0


def get_string_value(data: Dict[str, Any], key: str, default: str = "") -> str:
    """Safely get a string value from a dictionary.

    Args:
        data: Dictionary to search
        key: Key to look up
        default: Default value if key not found or not a string

    Returns:
        String value or default
    """
    value = data.get(key)
    if value is None:
        return default
    return str(value)


def get_bool_value(data: Dict[str, Any], key: str, default: bool = False) -> bool:
    """Safely get a boolean value from a dictionary.

    Args:
        data: Dictionary to search
        key: Key to look up
        default: Default value if key not found

    Returns:
        Boolean value or default
    """
    value = data.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def get_float_value(data: Dict[str, Any], key: str, default: float = 0.0) -> float:
    """Safely get a float value from a dictionary.

    Args:
        data: Dictionary to search
        key: Key to look up
        default: Default value if key not found or not convertible

    Returns:
        Float value or default
    """
    value = data.get(key)
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def get_nested_dict(data: Dict[str, Any], key: str) -> Dict[str, Any]:
    """Safely get a nested dictionary from a dictionary.

    Args:
        data: Dictionary to search
        key: Key to look up

    Returns:
        Nested dictionary or empty dict if not found/not a dict
    """
    value = data.get(key)
    if isinstance(value, dict):
        return value
    return {}
