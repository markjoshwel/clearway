"""Tests for libteamsdb models.

These tests use synthetic Pydantic models to test functions
that operate on Conversation, Message, and UserProfile objects.
"""

from datetime import datetime
from typing import List

import pytest

from libteamsdb import (
    Conversation,
    Message,
    ThreadType,
    UserProfile,
)


class TestUserProfile:
    """Tests for UserProfile model."""

    def test_create_basic_profile(self) -> None:
        """Test creating a basic user profile."""
        profile = UserProfile(
            id="8:orgid:test-user-001",
            display_name="Test User",
            email="test@example.com",
        )

        assert profile.id == "8:orgid:test-user-001"
        assert profile.display_name == "Test User"
        assert profile.email == "test@example.com"

    def test_profile_without_email(self) -> None:
        """Test creating a profile without email."""
        profile = UserProfile(
            id="8:orgid:test-user-002",
            display_name="Anonymous User",
        )

        assert profile.email is None

    def test_profile_immutable(self) -> None:
        """Test that profiles are frozen/immutable."""
        profile = UserProfile(
            id="8:orgid:test-user-003",
            display_name="Immutable User",
        )

        # Attempting to modify should raise error
        with pytest.raises(Exception):  # pydantic will raise
            profile.display_name = "New Name"


class TestMessage:
    """Tests for Message model."""

    def test_create_basic_message(self) -> None:
        """Test creating a basic message."""
        msg = Message(
            id="msg-001",
            sender_id="8:orgid:sender-001",
            sender_name="Sender Name",
            content="Hello, world!",
            timestamp=datetime(2024, 1, 15, 10, 30),
            conversation_id="conv-001",
            is_unread=False,
        )

        assert msg.id == "msg-001"
        assert msg.content == "Hello, world!"
        assert not msg.is_unread

    def test_create_unread_message(self) -> None:
        """Test creating an unread message."""
        msg = Message(
            id="msg-002",
            sender_id="8:orgid:sender-002",
            sender_name="Another Sender",
            content="Unread message",
            timestamp=datetime(2024, 1, 15, 11, 0),
            conversation_id="conv-001",
            is_unread=True,
        )

        assert msg.is_unread

    def test_message_default_unread_false(self) -> None:
        """Test that messages default to not unread."""
        msg = Message(
            id="msg-003",
            sender_id="8:orgid:sender-003",
            sender_name="Default Sender",
            content="Test message",
            timestamp=datetime.now(),
            conversation_id="conv-001",
        )

        assert not msg.is_unread


class TestConversation:
    """Tests for Conversation model."""

    def test_create_basic_conversation(self) -> None:
        """Test creating a basic conversation."""
        conv = Conversation(
            id="conv-001",
            title="Test Chat",
            last_message_time=datetime.now(),
            messages=[],
        )

        assert conv.id == "conv-001"
        assert conv.title == "Test Chat"
        assert conv.unread_count == 0

    def test_conversation_with_messages(self) -> None:
        """Test creating a conversation with messages."""
        messages: List[Message] = [
            Message(
                id="msg-001",
                sender_id="8:orgid:user-001",
                sender_name="User One",
                content="First message",
                timestamp=datetime(2024, 1, 15, 10, 0),
                conversation_id="conv-002",
                is_unread=False,
            ),
            Message(
                id="msg-002",
                sender_id="8:orgid:user-002",
                sender_name="User Two",
                content="Second message",
                timestamp=datetime(2024, 1, 15, 10, 5),
                conversation_id="conv-002",
                is_unread=True,
            ),
        ]

        conv = Conversation(
            id="conv-002",
            title="Chat with Messages",
            last_message_time=datetime(2024, 1, 15, 10, 5),
            messages=messages,
            unread_count=1,
        )

        assert len(conv.messages) == 2
        assert conv.unread_count == 1
        assert conv.has_unread

    def test_thread_type_chat(self) -> None:
        """Test chat thread type detection."""
        conv = Conversation(
            id="conv-003",
            title="Direct Chat",
            last_message_time=datetime.now(),
            messages=[],
            thread_type="Chat",
        )

        assert conv.thread_type == ThreadType.CHAT
        assert conv.is_chat
        assert not conv.is_channel

    def test_thread_type_topic(self) -> None:
        """Test topic/channel thread type detection."""
        conv = Conversation(
            id="19:channel@thread.tacv2",
            title="Team Channel",
            last_message_time=datetime.now(),
            messages=[],
            thread_type="Topic",
        )

        assert conv.thread_type == ThreadType.TOPIC
        assert conv.is_channel
        assert not conv.is_chat

    def test_thread_type_from_id_pattern(self) -> None:
        """Test thread type inference from conversation ID."""
        # Should detect as Topic from ID pattern
        conv = Conversation(
            id="19:somechannel@thread.v2",
            title="Channel",
            last_message_time=datetime.now(),
            messages=[],
            thread_type="Unknown",
        )

        assert conv.thread_type == ThreadType.TOPIC

    def test_unread_count_validation(self) -> None:
        """Test that unread count must be non-negative."""
        with pytest.raises(Exception):  # pydantic will validate
            Conversation(
                id="conv-004",
                title="Invalid",
                last_message_time=datetime.now(),
                messages=[],
                unread_count=-1,  # Invalid
            )


class TestConversationFiltering:
    """Tests for conversation filtering operations."""

    @pytest.fixture
    def sample_conversations(self) -> List[Conversation]:
        """Create a list of sample conversations for testing."""
        return [
            Conversation(
                id="conv-chat-001",
                title="Direct Chat with Alice",
                last_message_time=datetime(2024, 1, 15, 10, 0),
                messages=[
                    Message(
                        id="msg-001",
                        sender_id="8:orgid:alice",
                        sender_name="Alice",
                        content="Hello!",
                        timestamp=datetime(2024, 1, 15, 10, 0),
                        conversation_id="conv-chat-001",
                        is_unread=True,
                    ),
                ],
                unread_count=1,
                thread_type=ThreadType.CHAT,
            ),
            Conversation(
                id="19:general@thread.tacv2",
                title="General Channel",
                last_message_time=datetime(2024, 1, 15, 9, 30),
                messages=[
                    Message(
                        id="msg-002",
                        sender_id="8:orgid:bob",
                        sender_name="Bob",
                        content="Team meeting at 3",
                        timestamp=datetime(2024, 1, 15, 9, 30),
                        conversation_id="19:general@thread.tacv2",
                        is_unread=False,
                    ),
                ],
                unread_count=0,
                thread_type=ThreadType.TOPIC,
            ),
            Conversation(
                id="conv-meeting-001",
                title="Meeting Chat",
                last_message_time=datetime(2024, 1, 15, 8, 0),
                messages=[],
                unread_count=0,
                thread_type=ThreadType.MEETING,
                hidden=True,
            ),
        ]

    def test_filter_by_thread_type(
        self, sample_conversations: List[Conversation]
    ) -> None:
        """Test filtering conversations by thread type."""
        chats = [c for c in sample_conversations if c.thread_type == ThreadType.CHAT]
        channels = [
            c for c in sample_conversations if c.thread_type == ThreadType.TOPIC
        ]

        assert len(chats) == 1
        assert len(channels) == 1
        assert chats[0].title == "Direct Chat with Alice"

    def test_filter_unread_only(self, sample_conversations: List[Conversation]) -> None:
        """Test filtering for unread conversations only."""
        unread = [c for c in sample_conversations if c.unread_count > 0]

        assert len(unread) == 1
        assert unread[0].title == "Direct Chat with Alice"

    def test_filter_excluding_hidden(
        self, sample_conversations: List[Conversation]
    ) -> None:
        """Test filtering out hidden conversations."""
        visible = [c for c in sample_conversations if not c.hidden]

        assert len(visible) == 2
        assert all(not c.hidden for c in visible)

    def test_filter_excluding_meetings(
        self, sample_conversations: List[Conversation]
    ) -> None:
        """Test filtering out meeting conversations by ID pattern."""
        non_meetings = [
            c for c in sample_conversations if "meeting" not in c.id.lower()
        ]

        assert len(non_meetings) == 2


class TestMessageOperations:
    """Tests for message-level operations."""

    @pytest.fixture
    def conversation_with_messages(self) -> Conversation:
        """Create a conversation with mixed read/unread messages."""
        return Conversation(
            id="conv-005",
            title="Mixed Messages",
            last_message_time=datetime(2024, 1, 15, 12, 0),
            messages=[
                Message(
                    id="msg-old-001",
                    sender_id="8:orgid:user-001",
                    sender_name="User One",
                    content="Old read message",
                    timestamp=datetime(2024, 1, 15, 10, 0),
                    conversation_id="conv-005",
                    is_unread=False,
                ),
                Message(
                    id="msg-new-001",
                    sender_id="8:orgid:user-002",
                    sender_name="User Two",
                    content="New unread message 1",
                    timestamp=datetime(2024, 1, 15, 11, 0),
                    conversation_id="conv-005",
                    is_unread=True,
                ),
                Message(
                    id="msg-new-002",
                    sender_id="8:orgid:user-001",
                    sender_name="User One",
                    content="New unread message 2",
                    timestamp=datetime(2024, 1, 15, 12, 0),
                    conversation_id="conv-005",
                    is_unread=True,
                ),
            ],
            unread_count=2,
        )

    def test_count_unread_messages(
        self, conversation_with_messages: Conversation
    ) -> None:
        """Test counting unread messages."""
        unread = [m for m in conversation_with_messages.messages if m.is_unread]

        assert len(unread) == 2

    def test_get_message_senders(
        self, conversation_with_messages: Conversation
    ) -> None:
        """Test extracting unique message senders."""
        senders = set(m.sender_name for m in conversation_with_messages.messages)

        assert len(senders) == 2
        assert "User One" in senders
        assert "User Two" in senders

    def test_messages_sorted_by_time(
        self, conversation_with_messages: Conversation
    ) -> None:
        """Test that messages are sorted chronologically."""
        timestamps = [m.timestamp for m in conversation_with_messages.messages]

        assert timestamps == sorted(timestamps)
