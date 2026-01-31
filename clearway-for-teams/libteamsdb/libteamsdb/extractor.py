"""Teams database extractor.

This module provides the main TeamsDatabaseExtractor class for reading
Microsoft Teams IndexedDB data and converting it to typed models.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .exceptions import DatabaseNotFoundError, ExtractionError, InvalidDatabaseError
from .models import Conversation, Message, ThreadType, UserProfile
from .types import (
    IndexedDbWrapper,
    get_bool_value,
    get_float_value,
    get_nested_dict,
    get_string_value,
    parse_consumption_horizon,
    parse_timestamp,
)


class TeamsDatabaseExtractor:
    """Extracts conversation data from Microsoft Teams IndexedDB.

    This class provides a context manager for safely reading Teams data
    from the LevelDB database. It handles:
    - Copying the database to avoid file locks
    - Loading user profiles, consumption horizons, and conversations
    - Deduplicating records by version
    - Calculating unread message counts

    Example:
        with TeamsDatabaseExtractor(db_path) as extractor:
            conversations = extractor.get_conversations()
            for conv in conversations:
                print(f"{conv.title}: {conv.unread_count} unread")
    """

    # Database and store names
    PROFILES_DB_NAME = "Teams:profiles"
    PROFILES_STORE_ID = 1

    CONVERSATION_DB_NAME = "Teams:conversation-manager"
    CONVERSATION_STORE_ID = 1

    REPLY_DB_NAME = "Teams:replychain-manager"
    REPLY_STORE_ID = 1

    METADATA_DB_NAME = "Teams:replychain-metadata-manager"
    METADATA_STORE_ID = 1

    def __init__(self, db_path: Path) -> None:
        """Initialize the extractor.

        Args:
            db_path: Path to the Teams LevelDB database directory

        Raises:
            DatabaseNotFoundError: If the database path doesn't exist
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise DatabaseNotFoundError(f"Database not found: {db_path}")

        self._temp_path: Optional[Path] = None
        self._db: Optional[IndexedDbWrapper] = None
        self._profiles: Dict[str, UserProfile] = {}
        self._consumption_horizons: Dict[str, float] = {}
        self._conversation_read_status: Dict[str, bool] = {}

    def __enter__(self) -> TeamsDatabaseExtractor:
        """Enter context manager - copy database and load metadata."""
        self._temp_path = self._copy_database()
        self._db = IndexedDbWrapper(self._temp_path)
        self._load_profiles()
        self._load_consumption_horizons()
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[object],
    ) -> None:
        """Exit context manager - cleanup temporary files."""
        if self._db is not None:
            self._db.close()
            self._db = None

        if self._temp_path is not None and self._temp_path.exists():
            shutil.rmtree(self._temp_path.parent, ignore_errors=True)
            self._temp_path = None

    def _copy_database(self) -> Path:
        """Copy database to temporary location to avoid file locks.

        Returns:
            Path to the copied database
        """
        temp_dir = Path(tempfile.mkdtemp(prefix="teamsdb_"))
        target_path = temp_dir / self.db_path.name

        # Copy all files except LOCK (which indicates the database is in use)
        shutil.copytree(
            self.db_path,
            target_path,
            ignore=shutil.ignore_patterns("LOCK", "*.lock"),
        )

        return target_path

    def _find_database_id(self, name_snippet: str) -> Optional[int]:
        """Find database ID by name snippet.

        Args:
            name_snippet: String to search for in database names

        Returns:
            Database ID number if found, None otherwise
        """
        if self._db is None:
            return None

        for db_id in self._db.global_metadata.db_ids:
            if name_snippet in db_id.name:
                return db_id.dbid_no

        return None

    def _load_profiles(self) -> None:
        """Load user profiles from the database."""
        db_id = self._find_database_id(self.PROFILES_DB_NAME)
        if db_id is None or self._db is None:
            return

        for record in self._db.iterate_records(db_id, self.PROFILES_STORE_ID):
            value = record.value
            if value is None:
                continue

            mri = get_string_value(value, "mri") or str(record.key.value)
            name = get_string_value(value, "displayName", "Unknown")
            email = value.get("mail")
            email_str = str(email) if email is not None else None

            self._profiles[mri] = UserProfile(
                id=mri,
                display_name=name,
                email=email_str,
            )

    def _load_consumption_horizons(self) -> None:
        """Load consumption horizons (read markers) from the database."""
        # First try to load from metadata database (older Teams versions)
        db_id = self._find_database_id(self.METADATA_DB_NAME)
        if db_id is not None and self._db is not None:
            for record in self._db.iterate_records(db_id, self.METADATA_STORE_ID):
                value = record.value
                if value is None:
                    continue

                conv_id = get_string_value(value, "conversationId")
                horizon_raw = value.get("consumptionHorizon")

                if conv_id and horizon_raw is not None:
                    horizon = parse_consumption_horizon(horizon_raw)
                    if horizon > 0:
                        self._consumption_horizons[conv_id] = horizon

        # Also load from reply chain records (current Teams versions)
        # Reply chains contain consumptionHorizon field per conversation
        reply_db_id = self._find_database_id(self.REPLY_DB_NAME)
        if reply_db_id is not None and self._db is not None:
            for record in self._db.iterate_records(reply_db_id, self.REPLY_STORE_ID):
                value = record.value
                if value is None:
                    continue

                conv_id = get_string_value(value, "conversationId")
                horizon_raw = value.get("consumptionHorizon")

                if conv_id and horizon_raw is not None:
                    horizon = parse_consumption_horizon(horizon_raw)
                    if horizon > 0:
                        # Only update if we don't already have a horizon or this one is newer
                        existing = self._consumption_horizons.get(conv_id, 0.0)
                        if horizon > existing:
                            self._consumption_horizons[conv_id] = horizon

    def get_conversations(self) -> List[Conversation]:
        """Extract all conversations from the database.

        Returns:
            List of Conversation objects sorted by last message time (newest first)

        Raises:
            ExtractionError: If database extraction fails
            InvalidDatabaseError: If the database structure is unexpected
        """
        if self._db is None:
            raise ExtractionError("Extractor not initialized. Use as context manager.")

        conv_db_id = self._find_database_id(self.CONVERSATION_DB_NAME)
        reply_db_id = self._find_database_id(self.REPLY_DB_NAME)

        if conv_db_id is None or reply_db_id is None:
            raise InvalidDatabaseError(
                "Could not find required databases. "
                "The database structure may have changed."
            )

        try:
            raw_conversations = self._load_raw_conversations(conv_db_id)
            messages_by_conv = self._load_messages(reply_db_id)
            return self._assemble_conversations(raw_conversations, messages_by_conv)
        except Exception as e:
            raise ExtractionError(f"Failed to extract conversations: {e}") from e

    def _load_raw_conversations(self, db_id: int) -> Dict[str, Dict[str, object]]:
        """Load raw conversation data with deduplication by version.

        Args:
            db_id: Database ID for conversations

        Returns:
            Dictionary mapping conversation ID to the best version of its data
        """
        if self._db is None:
            return {}

        conversations: Dict[str, Tuple[float, Dict[str, object]]] = {}

        for record in self._db.iterate_records(db_id, self.CONVERSATION_STORE_ID):
            value = record.value
            if value is None:
                continue

            conv_id = get_string_value(value, "id")
            if not conv_id:
                continue

            # Get version for deduplication
            version = get_float_value(value, "version")
            if version == 0.0:
                version = get_float_value(value, "detailsVersion")

            existing = conversations.get(conv_id)
            if existing is None:
                conversations[conv_id] = (version, value)
            else:
                existing_version, existing_data = existing
                # Keep newer version, or if same version, prefer unread state
                if version > existing_version:
                    conversations[conv_id] = (version, value)
                elif version == existing_version:
                    # Prefer the one that indicates unread
                    existing_props = get_nested_dict(existing_data, "threadProperties")
                    new_props = get_nested_dict(value, "threadProperties")

                    existing_read = get_bool_value(existing_props, "isRead", True)
                    new_read = get_bool_value(new_props, "isRead", True)

                    if existing_read and not new_read:
                        conversations[conv_id] = (version, value)

        # Return just the data, not the version tuple
        return {k: v[1] for k, v in conversations.items()}

    def _load_messages(self, db_id: int) -> Dict[str, List[Message]]:
        """Load messages from reply chains.

        Args:
            db_id: Database ID for reply chains

        Returns:
            Dictionary mapping conversation ID to list of messages
        """
        if self._db is None:
            return {}

        messages_by_conv: Dict[str, List[Message]] = {}

        for record in self._db.iterate_records(db_id, self.REPLY_STORE_ID):
            value = record.value
            if value is None:
                continue

            conv_id = get_string_value(value, "conversationId")
            msg_map = value.get("messageMap")

            if not conv_id or not isinstance(msg_map, dict):
                continue

            if conv_id not in messages_by_conv:
                messages_by_conv[conv_id] = []

            for msg_id, msg_data in msg_map.items():
                if not isinstance(msg_data, dict):
                    continue

                message = self._parse_message(msg_id, msg_data, conv_id)
                if message is not None:
                    messages_by_conv[conv_id].append(message)

        return messages_by_conv

    def _parse_message(
        self, msg_id: str, msg_data: Dict[str, object], conv_id: str
    ) -> Optional[Message]:
        """Parse a single message from raw data.

        Args:
            msg_id: Message ID
            msg_data: Raw message data dictionary
            conv_id: Parent conversation ID

        Returns:
            Parsed Message object or None if parsing fails
        """
        # Extract content - Teams stores it in various fields
        content = get_string_value(msg_data, "content")
        if not content:
            message_body = msg_data.get("messageBody")
            if isinstance(message_body, dict):
                content = get_string_value(message_body, "content")

        sender_mri = get_string_value(msg_data, "from")

        # Get sender name from profiles or message data
        sender_name = "Unknown"
        if sender_mri in self._profiles:
            sender_name = self._profiles[sender_mri].display_name
        else:
            sender_name = get_string_value(msg_data, "imDisplayName", "Unknown")

        # Parse timestamp
        ts_raw = msg_data.get("originalArrivalTimestamp")
        timestamp = parse_timestamp(ts_raw)

        # Determine if unread by comparing with consumption horizon
        is_unread = False
        horizon = self._consumption_horizons.get(conv_id, 0.0)

        try:
            if isinstance(ts_raw, (int, float)) and float(ts_raw) > horizon:
                is_unread = True
            elif isinstance(ts_raw, str):
                ts_float = float(ts_raw)
                if ts_float > horizon:
                    is_unread = True
        except (ValueError, TypeError):
            pass

        return Message(
            id=msg_id,
            sender_id=sender_mri or "unknown",
            sender_name=sender_name,
            content=content,
            timestamp=timestamp,
            conversation_id=conv_id,
            is_unread=is_unread,
        )

    def _assemble_conversations(
        self,
        raw_conversations: Dict[str, Dict[str, object]],
        messages_by_conv: Dict[str, List[Message]],
    ) -> List[Conversation]:
        """Assemble final conversation objects from raw data and messages.

        Args:
            raw_conversations: Raw conversation data by ID
            messages_by_conv: Messages grouped by conversation ID

        Returns:
            List of assembled Conversation objects
        """
        conversations: List[Conversation] = []

        for conv_id, raw_conv in raw_conversations.items():
            # Determine thread type
            thread_type_str = get_string_value(raw_conv, "threadType")
            thread_type = self._determine_thread_type(thread_type_str, conv_id)

            # Get thread properties
            thread_props = get_nested_dict(raw_conv, "threadProperties")

            # Build title
            title = self._build_conversation_title(raw_conv, thread_props, thread_type)

            # Get read status from metadata
            is_read_meta = get_bool_value(thread_props, "isRead", True)

            # Get last message time
            last_ts_raw = raw_conv.get("lastMessageTimeUtc")
            last_message_time = parse_timestamp(last_ts_raw)

            # Get hidden status
            is_hidden = get_bool_value(thread_props, "hidden", False)

            # Get messages and sort by timestamp
            msgs = messages_by_conv.get(conv_id, [])
            msgs_sorted = sorted(msgs, key=lambda m: m.timestamp)

            # Calculate unread count
            unread_count = sum(1 for m in msgs_sorted if m.is_unread)

            # Check if we should force unread count based on metadata
            horizon = self._consumption_horizons.get(conv_id, 0.0)

            # Additional check from conversation properties
            conv_props = get_nested_dict(raw_conv, "properties")
            conv_horizon_raw = conv_props.get("consumptionhorizon")
            if conv_horizon_raw is not None:
                conv_horizon = parse_consumption_horizon(conv_horizon_raw)
                if conv_horizon > horizon:
                    horizon = conv_horizon

            # Heuristic: if last message is after horizon, conversation is unread
            if isinstance(last_ts_raw, (int, float)):
                try:
                    if float(last_ts_raw) > horizon and unread_count == 0:
                        unread_count = 1
                except (ValueError, TypeError):
                    pass

            # If metadata says unread but no unread messages found, force at least 1
            # and mark the most recent message as unread
            if not is_read_meta and unread_count == 0:
                unread_count = 1
                if msgs_sorted:
                    # Mark the most recent message as unread
                    last_msg = msgs_sorted[-1]
                    msgs_sorted[-1] = Message(
                        id=last_msg.id,
                        sender_id=last_msg.sender_id,
                        sender_name=last_msg.sender_name,
                        content=last_msg.content,
                        timestamp=last_msg.timestamp,
                        conversation_id=last_msg.conversation_id,
                        is_unread=True,
                    )

            conversations.append(
                Conversation(
                    id=conv_id,
                    title=title,
                    last_message_time=last_message_time,
                    messages=msgs_sorted,
                    unread_count=unread_count,
                    is_read_metadata=is_read_meta,
                    hidden=is_hidden,
                    thread_type=thread_type,
                )
            )

        # Sort by last message time, newest first
        return sorted(conversations, key=lambda c: c.last_message_time, reverse=True)

    def _determine_thread_type(self, thread_type_str: str, conv_id: str) -> ThreadType:
        """Determine the thread type from string or conversation ID.

        Args:
            thread_type_str: Thread type string from database
            conv_id: Conversation ID for fallback detection

        Returns:
            ThreadType enum value
        """
        if thread_type_str:
            try:
                return ThreadType(thread_type_str.capitalize())
            except ValueError:
                pass

        # Fallback detection from conversation ID patterns
        if "@thread.tacv2" in conv_id or "@thread.v2" in conv_id:
            return ThreadType.TOPIC
        elif "meeting_" in conv_id.lower():
            return ThreadType.MEETING
        else:
            return ThreadType.CHAT

    def _build_conversation_title(
        self,
        raw_conv: Dict[str, object],
        thread_props: Dict[str, object],
        thread_type: ThreadType,
    ) -> str:
        """Build a display title for the conversation.

        Args:
            raw_conv: Raw conversation data
            thread_props: Thread properties dictionary
            thread_type: Type of thread

        Returns:
            Display title string
        """
        # Get base title - try multiple sources
        title = get_string_value(raw_conv, "displayName") or get_string_value(
            raw_conv, "topic"
        )

        # For chats, try chatTitle field which contains participant names
        if not title:
            chat_title = get_nested_dict(raw_conv, "chatTitle")
            if chat_title:
                # shortTitle is usually the other person's name in 1:1 chats
                # longTitle contains all participants in group chats
                short_title = chat_title.get("shortTitle")
                long_title = chat_title.get("longTitle")
                title = short_title or long_title

        # Fallback to conversation ID if nothing else found
        if not title:
            title = get_string_value(raw_conv, "id")

        # For channels (Topics), try to build Team > Channel format
        if thread_type == ThreadType.TOPIC:
            team_name = (
                get_string_value(raw_conv, "displayName")
                or get_string_value(thread_props, "spaceThreadTopic")
                or get_string_value(thread_props, "description")
            )

            channel_name = get_string_value(raw_conv, "topic")

            if team_name and channel_name and team_name != channel_name:
                title = f"{team_name} > {channel_name}"
            elif channel_name:
                title = channel_name
            elif team_name:
                title = team_name

        return title
