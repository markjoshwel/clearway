"""Pydantic models for Teams database entities."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional, Dict, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ThreadType(str, Enum):
    """Types of Teams conversation threads."""

    CHAT = "Chat"
    TOPIC = "Topic"
    MEETING = "Meeting"
    UNKNOWN = "Unknown"


class UserProfile(BaseModel):
    """Represents a Teams user profile.

    Attributes:
        id: The user's MRI (e.g., 8:orgid:...)
        display_name: The user's display name
        email: The user's email address, if available
    """

    id: str = Field(..., description="User MRI (e.g., 8:orgid:...)")
    display_name: str = Field(..., description="Display name")
    email: Optional[str] = Field(None, description="Email address")

    model_config = ConfigDict(frozen=True)


class Message(BaseModel):
    """Represents a Teams message.

    Attributes:
        id: Unique message identifier
        sender_id: MRI of the message sender
        sender_name: Display name of the sender
        content: Message content/text
        timestamp: When the message was sent
        conversation_id: ID of the parent conversation
        is_unread: Whether the message has been read by the user
    """

    id: str = Field(..., description="Message ID")
    sender_id: str = Field(..., description="Sender MRI")
    sender_name: str = Field(..., description="Sender display name")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(..., description="Message timestamp")
    conversation_id: str = Field(..., description="Parent conversation ID")
    is_unread: bool = Field(False, description="Whether message is unread")

    model_config = ConfigDict(frozen=True)


class Conversation(BaseModel):
    """Represents a Teams conversation (chat or channel).

    Attributes:
        id: Unique conversation identifier
        title: Display title of the conversation
        last_message_time: Timestamp of the most recent message
        messages: List of messages in the conversation
        unread_count: Number of unread messages
        is_read_metadata: Whether the conversation is marked as read in metadata
        hidden: Whether the conversation is hidden/archived
        thread_type: Type of conversation (Chat, Topic, Meeting)
    """

    id: str = Field(..., description="Conversation ID")
    title: str = Field(..., description="Conversation title")
    last_message_time: datetime = Field(..., description="Last message timestamp")
    messages: List[Message] = Field(default_factory=list, description="Messages")
    unread_count: int = Field(0, description="Number of unread messages", ge=0)
    is_read_metadata: bool = Field(True, description="Read status from metadata")
    hidden: bool = Field(False, description="Whether conversation is hidden")
    thread_type: ThreadType = Field(ThreadType.UNKNOWN, description="Thread type")

    @field_validator("thread_type", mode="before")
    @classmethod
    def validate_thread_type(cls, v: Union[str, ThreadType], info: Any) -> ThreadType:
        """Convert string thread types to enum, with ID pattern fallback."""
        if isinstance(v, ThreadType):
            return v

        v_str = str(v).lower() if v else ""

        # Direct type string matching
        if v_str == "chat":
            return ThreadType.CHAT
        elif v_str == "topic":
            return ThreadType.TOPIC
        elif v_str == "meeting":
            return ThreadType.MEETING

        # If thread_type is "unknown" or empty, try to infer from conversation ID
        if v_str in ("unknown", ""):
            # Get the conversation ID from other field data if available
            data = info.data if hasattr(info, "data") else {}
            conv_id = data.get("id", "")

            # Infer from conversation ID patterns
            if "@thread.tacv2" in conv_id or "@thread.v2" in conv_id:
                return ThreadType.TOPIC
            elif "meeting_" in conv_id.lower():
                return ThreadType.MEETING
            elif conv_id and "@" not in conv_id:
                # Personal chats often have simpler IDs
                return ThreadType.CHAT

        return ThreadType.UNKNOWN

    @property
    def is_chat(self) -> bool:
        """Check if this is a 1:1 or group chat."""
        return self.thread_type == ThreadType.CHAT

    @property
    def is_channel(self) -> bool:
        """Check if this is a channel/topic conversation."""
        return self.thread_type == ThreadType.TOPIC

    @property
    def is_meeting(self) -> bool:
        """Check if this is a meeting conversation."""
        return self.thread_type == ThreadType.MEETING

    @property
    def has_unread(self) -> bool:
        """Check if conversation has unread messages."""
        return self.unread_count > 0

    model_config = ConfigDict(frozen=True)


class ConsumptionHorizon(BaseModel):
    """Represents a consumption horizon (read marker) for a conversation.

    Attributes:
        conversation_id: The conversation ID
        timestamp: The timestamp of the last read message
    """

    conversation_id: str = Field(..., description="Conversation ID")
    timestamp: float = Field(..., description="Last read timestamp")

    model_config = ConfigDict(frozen=True)


class RawConversationData(BaseModel):
    """Raw conversation data from the database before processing.

    This is used internally during extraction to handle deduplication
    and version management.
    """

    id: str
    version: float = 0.0
    data: Dict[
        str,
        Union[
            str, int, float, bool, None, Dict[str, Union[str, int, float, bool, None]]
        ],
    ] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)
