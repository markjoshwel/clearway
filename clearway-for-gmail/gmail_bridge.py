import os.path
import base64
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from dotenv import load_dotenv

load_dotenv()

# --- Scopes ---
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# --- Data Models ---

@dataclass
class UserProfile:
    id: str  # Email address
    display_name: str

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
    thread_type: str = "Email"

class GmailExtractor:
    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None

    def __enter__(self):
        creds = None
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        self.service = build("gmail", "v1", credentials=creds)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.service:
            self.service.close()

    def get_conversations(self, limit: int = 20) -> List[Conversation]:
        if not self.service:
            return []

        try:
            # 1. Get List of Threads (Gmail groups by thread naturally)
            results = self.service.users().threads().list(userId="me", maxResults=limit).execute()
            threads = results.get("threads", [])

            conversations = []
            for thread_info in threads:
                tid = thread_info["id"]
                thread = self.service.users().threads().get(userId="me", id=tid).execute()
                
                messages = []
                unread_count = 0
                
                # Process messages in thread
                raw_msgs = thread.get("messages", [])
                for rm in raw_msgs:
                    payload = rm.get("payload", {})
                    headers = payload.get("headers", [])
                    
                    # Extract headers
                    subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
                    sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
                    date_str = next((h["value"] for h in headers if h["name"] == "Date"), None)
                    
                    try:
                        # Simple snippet for content
                        content = rm.get("snippet", "")
                        ts = datetime.fromtimestamp(int(rm["internalDate"]) / 1000.0)
                    except:
                        ts = datetime.now()

                    is_unread = "UNREAD" in rm.get("labelIds", [])
                    if is_unread:
                        unread_count += 1

                    messages.append(Message(
                        id=rm["id"],
                        sender_id=sender,
                        sender_name=sender,
                        content=content,
                        timestamp=ts,
                        conversation_id=tid,
                        is_unread=is_unread
                    ))

                # Use last message for conversation metadata
                last_msg = messages[-1] if messages else None
                if last_msg:
                    conversations.append(Conversation(
                        id=tid,
                        title=subject, # Title is usually the subject
                        last_message_time=last_msg.timestamp,
                        messages=messages,
                        unread_count=unread_count
                    ))

            return sorted(conversations, key=lambda x: x.last_message_time, reverse=True)

        except HttpError as error:
            print(f"An error occurred: {error}")
            return []

def main():
    print("Initializing Gmail Message Bridge...")
    try:
        with GmailExtractor() as extractor:
            conversations = extractor.get_conversations()
            
            print(f"\nFound {len(conversations)} threads.\n")
            print("=" * 60)
            
            for conv in conversations:
                status = f" ({conv.unread_count} UNREAD)" if conv.unread_count > 0 else ""
                print(f"THREAD: {conv.title}{status}")
                print(f"ID: {conv.id}")
                print(f"Last Active: {conv.last_message_time}")
                print("-" * 30)
                
                # Show last message
                if conv.messages:
                    msg = conv.messages[-1]
                    print(f"[{msg.timestamp.strftime('%Y-%m-%d %H:%M')}] {msg.sender_name}: {msg.content}...")
                
                print("=" * 60)

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
