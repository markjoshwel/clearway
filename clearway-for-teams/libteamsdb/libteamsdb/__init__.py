"""libteamsdb - A robust library for reading Microsoft Teams IndexedDB data."""

__version__ = "0.1.0"

from .models import Conversation, Message, UserProfile, ThreadType
from .extractor import TeamsDatabaseExtractor
from .discovery import TeamsDatabaseDiscovery, DatabaseLocation
from .exceptions import (
    TeamsDatabaseError,
    DatabaseNotFoundError,
    InvalidDatabaseError,
    ExtractionError,
)
from .types import (
    IndexedDbWrapper,
    parse_timestamp,
    parse_consumption_horizon,
    get_string_value,
    get_bool_value,
    get_float_value,
    get_nested_dict,
)

# Synthetic data generation (for testing)
from .synthetic import (
    TeamsIndexedDB,
    IndexedDBDatabase,
    IndexedDBStore,
    IndexedDBRecord,
    load_real_db_anonymize,
)

__all__ = [
    # Core models
    "Conversation",
    "Message",
    "UserProfile",
    "ThreadType",
    # Main classes
    "TeamsDatabaseExtractor",
    "TeamsDatabaseDiscovery",
    "DatabaseLocation",
    # Exceptions
    "TeamsDatabaseError",
    "DatabaseNotFoundError",
    "InvalidDatabaseError",
    "ExtractionError",
    # Type utilities
    "IndexedDbWrapper",
    "parse_timestamp",
    "parse_consumption_horizon",
    "get_string_value",
    "get_bool_value",
    "get_float_value",
    "get_nested_dict",
    # Synthetic data
    "TeamsIndexedDB",
    "IndexedDBDatabase",
    "IndexedDBStore",
    "IndexedDBRecord",
    "load_real_db_anonymize",
]
