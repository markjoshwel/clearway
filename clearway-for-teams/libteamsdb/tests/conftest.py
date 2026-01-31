# conftest.py - pytest configuration and fixtures

"""Pytest configuration for libteamsdb tests."""

import pytest
from pathlib import Path
from datetime import datetime
from typing import List

from libteamsdb import Conversation, Message, ThreadType, UserProfile


@pytest.fixture
def sample_users() -> List[UserProfile]:
    """Create sample user profiles for testing."""
    return [
        UserProfile(
            id="8:orgid:user-001",
            display_name="Alice Smith",
            email="alice@example.com",
        ),
        UserProfile(
            id="8:orgid:user-002",
            display_name="Bob Jones",
            email="bob@example.com",
        ),
        UserProfile(
            id="8:orgid:user-003",
            display_name="Charlie Brown",
        ),
    ]


@pytest.fixture
def sample_conversations() -> List[Conversation]:
    """Create sample conversations for testing."""
    return [
        Conversation(
            id="conv-chat-001",
            title="Direct Chat",
            last_message_time=datetime(2024, 1, 15, 10, 30),
            messages=[
                Message(
                    id="msg-001",
                    sender_id="8:orgid:user-001",
                    sender_name="Alice",
                    content="Hello!",
                    timestamp=datetime(2024, 1, 15, 10, 0),
                    conversation_id="conv-chat-001",
                    is_unread=False,
                ),
                Message(
                    id="msg-002",
                    sender_id="8:orgid:user-002",
                    sender_name="Bob",
                    content="Hi there!",
                    timestamp=datetime(2024, 1, 15, 10, 30),
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
            last_message_time=datetime(2024, 1, 15, 9, 0),
            messages=[
                Message(
                    id="msg-003",
                    sender_id="8:orgid:user-003",
                    sender_name="Charlie",
                    content="Team update",
                    timestamp=datetime(2024, 1, 15, 9, 0),
                    conversation_id="19:general@thread.tacv2",
                    is_unread=False,
                ),
            ],
            unread_count=0,
            thread_type=ThreadType.TOPIC,
        ),
    ]
