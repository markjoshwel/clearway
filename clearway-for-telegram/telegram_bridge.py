import os
import asyncio
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
from telethon import TelegramClient, events, utils
from telethon.tl.types import Channel, Chat, User, Message as TelethonMessage
from dotenv import load_dotenv

load_dotenv()

# --- Data Models ---

@dataclass
class UserProfile:
    id: str
    display_name: str
    username: Optional[str]
    phone: Optional[str]

@dataclass
class Message:
    id: str
    sender_id: str
    sender_name: str
    content: str
    timestamp: datetime
    conversation_id: str
    is_unread: bool = False

@dataclass
class Conversation:
    id: str
    title: str
    last_message_time: datetime
    messages: List[Message]
    unread_count: int = 0
    thread_type: str = "Chat" # Chat, Group, Channel

# --- Extractor Class ---

class TelegramExtractor:
    def __init__(self, api_id: int, api_hash: str, session_name: str = "clearway_telegram"):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_path = Path("sessions") / session_name
        self.session_path.parent.mkdir(exist_ok=True)
        self.client = TelegramClient(str(self.session_path), api_id, api_hash)
        self.profiles: Dict[int, UserProfile] = {}

    async def __aenter__(self):
        await self.client.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.disconnect()

    async def _get_sender_name(self, sender_id: int) -> str:
        if sender_id in self.profiles:
            return self.profiles[sender_id].display_name
        
        try:
            entity = await self.client.get_entity(sender_id)
            name = utils.get_display_name(entity)
            self.profiles[sender_id] = UserProfile(
                id=str(sender_id),
                display_name=name,
                username=getattr(entity, 'username', None),
                phone=getattr(entity, 'phone', None)
            )
            return name
        except Exception:
            return "Unknown"

    async def get_conversations(self, limit: int = 20) -> List[Conversation]:
        conversations = []
        async for dialog in self.client.iter_dialogs(limit=limit):
            entity = dialog.entity
            cid = str(dialog.id)
            title = dialog.name
            
            thread_type = "Chat"
            if isinstance(entity, Channel):
                thread_type = "Channel" if entity.broadcast else "Group"
            elif isinstance(entity, Chat):
                thread_type = "Group"

            messages = []
            async for msg in self.client.iter_messages(entity, limit=5):
                if not isinstance(msg, TelethonMessage):
                    continue
                
                sender_id = msg.from_id.user_id if hasattr(msg.from_id, 'user_id') else (msg.peer_id.user_id if hasattr(msg.peer_id, 'user_id') else 0)
                sender_name = await self._get_sender_name(sender_id)
                
                messages.append(Message(
                    id=str(msg.id),
                    sender_id=str(sender_id),
                    sender_name=sender_name,
                    content=msg.text or "[Media/Non-text]",
                    timestamp=msg.date,
                    conversation_id=cid,
                    is_unread=msg.id > dialog.read_inbox_max_id if hasattr(dialog, 'read_inbox_max_id') else False
                ))

            conversations.append(Conversation(
                id=cid,
                title=title,
                last_message_time=dialog.date,
                messages=messages,
                unread_count=dialog.unread_count,
                thread_type=thread_type
            ))

        return sorted(conversations, key=lambda x: x.last_message_time, reverse=True)

# --- Execution ---

async def main():
    api_id = os.environ.get("TELEGRAM_API_ID")
    api_hash = os.environ.get("TELEGRAM_API_HASH")

    if not api_id or not api_hash:
        print("Error: TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables must be set.")
        return

    print(f"Initializing Telegram Message Bridge...")
    try:
        async with TelegramExtractor(int(api_id), api_hash) as extractor:
            conversations = await extractor.get_conversations()
            
            print(f"\nFound {len(conversations)} conversations.\n")
            print("=" * 60)
            
            for conv in conversations:
                if conv.unread_count > 0:
                    print(f"CONVERSATION: {conv.title} ({conv.unread_count} UNREAD)")
                else:
                    print(f"CONVERSATION: {conv.title}")
                    
                print(f"ID: {conv.id}")
                print(f"Type: {conv.thread_type}")
                print(f"Last Active: {conv.last_message_time}")
                print("-" * 30)
                
                # Show last 3 messages
                for msg in conv.messages[:3]:
                    print(f"[{msg.timestamp.strftime('%Y-%m-%d %H:%M')}] {msg.sender_name}: {msg.content[:100]}...")
                
                print("=" * 60)

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
