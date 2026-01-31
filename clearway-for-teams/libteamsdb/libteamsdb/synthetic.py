"""Teams IndexedDB synthetic data models.

This module provides Pydantic models that represent the internal structure
of the Teams IndexedDB databases. These models can:
- Load from real Teams databases (via ccl_chromium_reader)
- Dump to synthetic LevelDB files (via plyvel)
- Generate completely synthetic test data
- Anonymize real data for testing purposes

This allows us to:
1. Create test fixtures from real data (anonymized)
2. Generate synthetic data for unit testing
3. Detect schema changes by comparing models to real data
"""

from __future__ import annotations

import json
import hashlib
import random
import string
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple, Union

from pydantic import BaseModel, ConfigDict, Field


class IndexedDBRecord(BaseModel):
    """Represents a single IndexedDB record.

    This is the raw storage format used by Chromium's IndexedDB implementation.
    """

    key: Union[str, int, bytes] = Field(..., description="Record key")
    value: Dict[str, Any] = Field(..., description="Record value as JSON object")

    def to_leveldb_key(self) -> bytes:
        """Convert the key to LevelDB key format.

        Returns:
            Serialized key as bytes
        """
        if isinstance(self.key, bytes):
            return self.key
        elif isinstance(self.key, str):
            return self.key.encode("utf-8")
        elif isinstance(self.key, int):
            return str(self.key).encode("utf-8")
        else:
            return str(self.key).encode("utf-8")

    def to_leveldb_value(self) -> bytes:
        """Convert the value to LevelDB value format.

        Returns:
            Serialized value as JSON bytes
        """
        return json.dumps(self.value, separators=(",", ":")).encode("utf-8")

    model_config = ConfigDict(frozen=True)


class IndexedDBStore(BaseModel):
    """Represents an IndexedDB object store.

    An object store is a collection of records within a database.
    """

    store_id: int = Field(..., description="Store ID number")
    name: str = Field(..., description="Store name")
    records: List[IndexedDBRecord] = Field(
        default_factory=list, description="Records in this store"
    )

    def add_record(
        self, key: Union[str, int], value: Dict[str, Any]
    ) -> IndexedDBRecord:
        """Add a record to this store.

        Args:
            key: Record key
            value: Record value

        Returns:
            The created record
        """
        record = IndexedDBRecord(key=key, value=value)
        self.records.append(record)
        return record

    model_config = ConfigDict(frozen=False)  # Allow adding records


class IndexedDBDatabase(BaseModel):
    """Represents an IndexedDB database.

    A database contains multiple object stores.
    """

    db_id: int = Field(..., description="Database ID number")
    name: str = Field(..., description="Database name")
    stores: Dict[int, IndexedDBStore] = Field(
        default_factory=dict, description="Stores by ID"
    )

    def get_or_create_store(self, store_id: int, name: str = "") -> IndexedDBStore:
        """Get an existing store or create a new one.

        Args:
            store_id: Store ID
            name: Store name (for new stores)

        Returns:
            The store instance
        """
        if store_id not in self.stores:
            self.stores[store_id] = IndexedDBStore(store_id=store_id, name=name)
        return self.stores[store_id]

    model_config = ConfigDict(frozen=False)  # Allow adding stores


class TeamsIndexedDB(BaseModel):
    """Represents the complete Teams IndexedDB structure.

    This model captures the entire database including:
    - User profiles (Teams:profiles)
    - Conversations (Teams:conversation-manager)
    - Messages/reply chains (Teams:replychain-manager)
    - Metadata including read horizons (Teams:replychain-metadata-manager)

    The model can load from real databases and dump to synthetic ones,
    with full anonymization support.
    """

    databases: Dict[int, IndexedDBDatabase] = Field(
        default_factory=dict, description="Databases by ID"
    )

    # Metadata about the source
    source_path: Optional[Path] = Field(None, description="Original database path")
    loaded_at: datetime = Field(default_factory=datetime.now, description="When loaded")

    # Anonymization mapping (for testing/debugging)
    _anonymization_map: ClassVar[Dict[str, str]] = {}

    # Database name constants
    PROFILES_DB_NAME: ClassVar[str] = "Teams:profiles"
    CONVERSATION_DB_NAME: ClassVar[str] = "Teams:conversation-manager"
    REPLY_DB_NAME: ClassVar[str] = "Teams:replychain-manager"
    METADATA_DB_NAME: ClassVar[str] = "Teams:replychain-metadata-manager"

    # Store ID constants
    PROFILES_STORE_ID: ClassVar[int] = 1
    CONVERSATION_STORE_ID: ClassVar[int] = 1
    REPLY_STORE_ID: ClassVar[int] = 1
    METADATA_STORE_ID: ClassVar[int] = 1

    model_config = ConfigDict(frozen=False)

    def get_or_create_database(self, db_id: int, name: str = "") -> IndexedDBDatabase:
        """Get an existing database or create a new one.

        Args:
            db_id: Database ID
            name: Database name (for new databases)

        Returns:
            The database instance
        """
        if db_id not in self.databases:
            self.databases[db_id] = IndexedDBDatabase(db_id=db_id, name=name)
        return self.databases[db_id]

    def find_database_by_name(self, name_snippet: str) -> Optional[IndexedDBDatabase]:
        """Find a database by name snippet.

        Args:
            name_snippet: String to search for in database names

        Returns:
            The database if found, None otherwise
        """
        for db in self.databases.values():
            if name_snippet in db.name:
                return db
        return None

    def load_from_leveldb(self, db_path: Path) -> TeamsIndexedDB:
        """Load database structure from a real LevelDB.

        This uses ccl_chromium_reader to parse the actual database.

        Args:
            db_path: Path to the LevelDB directory

        Returns:
            Self for method chaining

        Raises:
            ImportError: If ccl_chromium_reader is not available
            FileNotFoundError: If the database path doesn't exist
        """
        from ccl_chromium_reader import ccl_chromium_indexeddb

        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        db = ccl_chromium_indexeddb.IndexedDb(db_path)

        try:
            # Load each database and its stores
            for db_meta in db.global_metadata.db_ids:
                indexed_db = self.get_or_create_database(db_meta.dbid_no, db_meta.name)

                # Iterate through stores (we'll need to discover store IDs)
                # For Teams, we know the store IDs are typically 1
                for store_id in [1]:  # Could be extended to discover all stores
                    try:
                        for record in db.iterate_records(db_meta.dbid_no, store_id):
                            store = indexed_db.get_or_create_store(store_id, "records")

                            # Extract key and value
                            key = (
                                record.key.value
                                if hasattr(record.key, "value")
                                else str(record.key)
                            )
                            value = record.value if record.value else {}

                            store.add_record(key, value)
                    except Exception:
                        # Store might not exist, skip
                        pass

            self.source_path = db_path
            self.loaded_at = datetime.now()

        finally:
            db.close()

        return self

    def dump_to_leveldb(self, output_path: Path, anonymize: bool = True) -> None:
        """Dump the database to a LevelDB directory.

        This uses plyvel to write the LevelDB files.

        Args:
            output_path: Path to create the database
            anonymize: Whether to anonymize data before writing

        Raises:
            ImportError: If plyvel is not available
        """
        import plyvel

        # Create output directory
        output_path.mkdir(parents=True, exist_ok=True)

        # Open the database
        leveldb = plyvel.DB(str(output_path), create_if_missing=True)

        try:
            # Write a batch of records
            batch = leveldb.write_batch()

            for db_id, indexed_db in self.databases.items():
                for store_id, store in indexed_db.stores.items():
                    for record in store.records:
                        # Create key with database prefix
                        # Chromium IndexedDB keys have a specific format
                        key_bytes = record.to_leveldb_key()

                        # Anonymize if requested
                        if anonymize:
                            value = self._anonymize_value(record.value)
                        else:
                            value = record.value

                        # Write to LevelDB
                        batch.put(key_bytes, json.dumps(value).encode("utf-8"))

            batch.write()

        finally:
            leveldb.close()

        # Write manifest and current files (simplified)
        self._write_leveldb_metadata(output_path)

    def _anonymize_value(self, value: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize a record value.

        This replaces personal identifiers with hashed/synthetic values
        while preserving structure.

        Args:
            value: Original record value

        Returns:
            Anonymized value
        """
        result = {}

        for key, val in value.items():
            if isinstance(val, dict):
                result[key] = self._anonymize_value(val)
            elif isinstance(val, list):
                result[key] = [
                    self._anonymize_value(v) if isinstance(v, dict) else v for v in val
                ]
            elif key in self._get_sensitive_keys():
                # Hash sensitive values
                result[key] = self._hash_identifier(str(val))
            elif self._is_identifier(key, val):
                # Hash identifiers
                result[key] = self._hash_identifier(str(val))
            else:
                # Keep other values as-is
                result[key] = val

        return result

    def _get_sensitive_keys(self) -> Set[str]:
        """Get the set of keys that contain sensitive data.

        Returns:
            Set of sensitive key names
        """
        return {
            "mri",
            "displayName",
            "mail",
            "email",
            "content",
            "imDisplayName",
            "from",
            "conversationId",
            "id",
        }

    def _is_identifier(self, key: str, value: Any) -> bool:
        """Check if a key-value pair is an identifier that should be hashed.

        Args:
            key: The field name
            value: The field value

        Returns:
            True if this should be treated as an identifier
        """
        if not isinstance(value, str):
            return False

        # Check for common identifier patterns
        identifier_keys = {"id", "mri", "userId", "conversationId", "messageId"}
        if key.lower() in identifier_keys or key.endswith("Id") or key.endswith("ID"):
            return True

        # Check for email patterns
        if "@" in value and "." in value:
            return True

        # Check for MRI patterns (8:orgid:...)
        if value.startswith("8:") or value.startswith("9:"):
            return True

        return False

    def _hash_identifier(self, value: str) -> str:
        """Hash an identifier to anonymize it.

        Args:
            value: Original identifier

        Returns:
            Hashed/synthetic identifier that preserves structure but hides identity
        """
        # Create a deterministic hash
        hash_obj = hashlib.sha256(value.encode())
        hash_hex = hash_obj.hexdigest()[:16]

        # Preserve structure hints
        if value.startswith("8:orgid:"):
            return f"8:orgid:synth-{hash_hex}"
        elif value.startswith("8:"):
            return f"8:synth-{hash_hex}"
        elif value.startswith("9:"):
            return f"9:synth-{hash_hex}"
        elif "@" in value:
            # Preserve domain for email structure
            parts = value.split("@")
            if len(parts) == 2:
                return f"user-{hash_hex}@{parts[1]}"
            return f"synth-{hash_hex}@example.com"
        elif "meeting_" in value:
            return f"meeting_synth-{hash_hex}"
        elif "@thread." in value:
            return f"19:synth-{hash_hex}@thread.tacv2"
        else:
            return f"synth-{hash_hex}"

    def _write_leveldb_metadata(self, db_path: Path) -> None:
        """Write LevelDB metadata files.

        Args:
            db_path: Database directory path
        """
        # Write CURRENT file
        current_path = db_path / "CURRENT"
        current_path.write_text("MANIFEST-000001\n")

        # Note: A real implementation would also write:
        # - MANIFEST file with proper metadata
        # - LOG file
        # - .ldb data files
        # This is a simplified version for testing

    def generate_synthetic(
        self,
        num_conversations: int = 10,
        messages_per_conv: Tuple[int, int] = (5, 20),
        num_users: int = 5,
    ) -> TeamsIndexedDB:
        """Generate completely synthetic test data.

        Args:
            num_conversations: Number of conversations to generate
            messages_per_conv: Range (min, max) of messages per conversation
            num_users: Number of synthetic user profiles to create

        Returns:
            Self for method chaining
        """
        # Create synthetic users
        users = self._generate_users(num_users)

        # Create databases
        profiles_db = self.get_or_create_database(1, self.PROFILES_DB_NAME)
        conv_db = self.get_or_create_database(2, self.CONVERSATION_DB_NAME)
        reply_db = self.get_or_create_database(3, self.REPLY_DB_NAME)
        meta_db = self.get_or_create_database(4, self.METADATA_DB_NAME)

        # Add profiles store
        profiles_store = profiles_db.get_or_create_store(
            self.PROFILES_STORE_ID, "profiles"
        )
        for user in users:
            profiles_store.add_record(
                user["mri"],
                {
                    "mri": user["mri"],
                    "displayName": user["name"],
                    "mail": user["email"],
                },
            )

        # Generate conversations
        for i in range(num_conversations):
            conv_id = f"19:synth-conv-{i}@thread.tacv2"
            is_chat = random.choice([True, False])

            if is_chat:
                thread_type = "Chat"
                title = f"Chat with {random.choice(users)['name']}"
            else:
                thread_type = "Topic"
                title = f"Channel: General Team {i}"

            # Add conversation record
            conv_store = conv_db.get_or_create_store(
                self.CONVERSATION_STORE_ID, "conversations"
            )
            conv_store.add_record(
                conv_id,
                {
                    "id": conv_id,
                    "threadType": thread_type,
                    "displayName": title,
                    "version": 1.0,
                    "threadProperties": {
                        "isRead": random.choice([True, False]),
                    },
                },
            )

            # Generate messages
            num_messages = random.randint(*messages_per_conv)
            msg_map = {}

            for j in range(num_messages):
                msg_id = f"synth-msg-{i}-{j}"
                sender = random.choice(users)

                msg_map[msg_id] = {
                    "id": msg_id,
                    "from": sender["mri"],
                    "imDisplayName": sender["name"],
                    "content": f"Synthetic message {j} in conversation {i}",
                    "originalArrivalTimestamp": int(
                        (datetime.now() - timedelta(hours=j)).timestamp() * 1000
                    ),
                }

            reply_store = reply_db.get_or_create_store(
                self.REPLY_STORE_ID, "replychains"
            )
            reply_store.add_record(
                conv_id,
                {
                    "conversationId": conv_id,
                    "messageMap": msg_map,
                },
            )

            # Add metadata (read horizon)
            meta_store = meta_db.get_or_create_store(
                self.METADATA_STORE_ID, "replychainmetadata"
            )
            meta_store.add_record(
                conv_id,
                {
                    "conversationId": conv_id,
                    "consumptionHorizon": str(
                        int(
                            (
                                datetime.now() - timedelta(hours=num_messages // 2)
                            ).timestamp()
                            * 1000
                        )
                    ),
                },
            )

        return self

    def _generate_users(self, num_users: int) -> List[Dict[str, str]]:
        """Generate synthetic user profiles.

        Args:
            num_users: Number of users to generate

        Returns:
            List of user dictionaries
        """
        users = []
        first_names = [
            "Alice",
            "Bob",
            "Charlie",
            "Diana",
            "Eve",
            "Frank",
            "Grace",
            "Henry",
        ]
        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
        ]

        for i in range(num_users):
            first = random.choice(first_names)
            last = random.choice(last_names)
            name = f"{first} {last}"
            email = f"{first.lower()}.{last.lower()}@example.com"
            mri = f"8:orgid:synth-user-{i:04d}"

            users.append(
                {
                    "name": name,
                    "email": email,
                    "mri": mri,
                }
            )

        return users


def load_real_db_anonymize(db_path: Path, output_path: Path) -> TeamsIndexedDB:
    """Load a real Teams database and create an anonymized copy.

    Args:
        db_path: Path to the real database
        output_path: Path to write the anonymized database

    Returns:
        The loaded (and anonymized) database model
    """
    db = TeamsIndexedDB()
    db.load_from_leveldb(db_path)
    db.dump_to_leveldb(output_path, anonymize=True)
    return db
