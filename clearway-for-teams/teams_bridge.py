import os
import shutil
import tempfile
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from datetime import datetime
from ccl_chromium_reader import ccl_chromium_indexeddb # type: ignore

# --- Data Models ---

@dataclass
class UserProfile:
    id: str  # MRI, e.g., 8:orgid:...
    display_name: str
    email: Optional[str]

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
    is_read_metadata: bool = True # From threadProperties.isRead
    hidden: bool = False # From threadProperties.hidden
    thread_type: str = "Chat" # Chat or Topic

# --- Extractor Class ---

class TeamsExtractor:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.temp_path: Optional[Path] = None
        self.db: Optional[ccl_chromium_indexeddb.IndexedDb] = None
        self.profiles: Dict[str, UserProfile] = {}
        self.consumption_horizons: Dict[str, float] = {} # conv_id -> timestamp
        self.conversation_read_status: Dict[str, bool] = {} # conv_id -> isRead

    def __enter__(self):
        self.temp_path = self._copy_db()
        self.db = ccl_chromium_indexeddb.IndexedDb(self.temp_path)
        self._load_profiles()
        self._load_consumption_horizons()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
        if self.temp_path and self.temp_path.exists():
            shutil.rmtree(self.temp_path.parent, ignore_errors=True)

    def _copy_db(self) -> Path:
        temp_dir = Path(tempfile.mkdtemp(prefix="teams_bridge_"))
        target_path = temp_dir / self.db_path.name
        shutil.copytree(self.db_path, target_path, ignore=shutil.ignore_patterns("LOCK"))
        return target_path

    def _find_db_by_name(self, snippet: str) -> Optional[int]:
        if not self.db: return None
        for db_id in self.db.global_metadata.db_ids:
            if snippet in db_id.name:
                return db_id.dbid_no
        return None

    def _load_profiles(self):
        db_id = self._find_db_by_name("Teams:profiles")
        if db_id is None: return
        
        # Store 1 is 'profiles'
        for record in self.db.iterate_records(db_id, 1):
            val = record.value
            if not val: continue
            
            mri = val.get("mri") or str(record.key.value)
            name = val.get("displayName", "Unknown")
            email = val.get("mail")
            
            self.profiles[mri] = UserProfile(id=mri, display_name=name, email=email)

    def _load_consumption_horizons(self):
        db_id = self._find_db_by_name("Teams:replychain-metadata-manager")
        if db_id is None: return
        
        # Store 1 is 'replychainmetadata'
        for record in self.db.iterate_records(db_id, 1):
            val = record.value
            if not val: continue
            
            conv_id = val.get("conversationId")
            # This is the timestamp of the last READ message
            # Semicolon separated list, we should take the max valid one
            horizon_raw = val.get("consumptionHorizon")
            if conv_id and horizon_raw:
                try:
                    parts = str(horizon_raw).split(';')
                    max_h = 0.0
                    for p in parts:
                        try:
                            val_f = float(p.strip())
                            if val_f > max_h:
                                max_h = val_f
                        except (ValueError, TypeError):
                            continue
                    if max_h > 0:
                        self.consumption_horizons[conv_id] = max_h
                except (ValueError, TypeError):
                    pass

    def get_conversations(self) -> List[Conversation]:
        conv_db_id = self._find_db_by_name("Teams:conversation-manager")
        reply_db_id = self._find_db_by_name("Teams:replychain-manager")
        
        if conv_db_id is None or reply_db_id is None:
            print("Warning: Could not find conversation or reply databases.")
            return []

        conversations = []
        
        # 1. Get Conversation Metadata
        # Store 1 is 'conversations'
        # We deduplicate by ID, source, and version to find the most "real" one
        temp_conversations: Dict[str, dict] = {}
        for record in self.db.iterate_records(conv_db_id, 1):
            val = record.value
            if not val: continue
            cid = val.get("id")
            if not cid: continue
            
            # Use version as the primary key for "latest"
            ver = float(val.get("version") or val.get("detailsVersion") or 0)
            
            existing = temp_conversations.get(cid)
            if not existing:
                temp_conversations[cid] = val
            else:
                existing_ver = float(existing.get("version") or existing.get("detailsVersion") or 0)
                # If newer version, replace. 
                # If same version, prefer the one that is UNREAD (isRead: False)
                if ver > existing_ver:
                    temp_conversations[cid] = val
                elif ver == existing_ver:
                    if existing.get("threadProperties", {}).get("isRead", True) is True and \
                       val.get("threadProperties", {}).get("isRead", True) is False:
                        temp_conversations[cid] = val

        raw_conversations = list(temp_conversations.values())

        # 2. Get Messages (Reply Chains)
        # Store 1 is 'replychains'
        # Map conversation_id -> List[Message]
        messages_by_conv: Dict[str, List[Message]] = {}
        for record in self.db.iterate_records(reply_db_id, 1):
            val = record.value
            if not val: continue
            
            conv_id = val.get("conversationId")
            msg_map = val.get("messageMap", {})
            
            if conv_id not in messages_by_conv:
                messages_by_conv[conv_id] = []
                
            for msg_id, msg_data in msg_map.items():
                # Extract content - Teams stores it in various fields depending on type
                content = msg_data.get("content", "")
                if not content and "messageBody" in msg_data:
                    content = msg_data["messageBody"].get("content", "")
                
                sender_mri = msg_data.get("from")
                sender_name = "Unknown"
                if sender_mri in self.profiles:
                    sender_name = self.profiles[sender_mri].display_name
                elif "imDisplayName" in msg_data:
                    sender_name = msg_data["imDisplayName"]

                ts_raw = msg_data.get("originalArrivalTimestamp", 0)
                try:
                    # Teams timestamps are often ms. If it's too large, try treating as seconds or just clamp.
                    if ts_raw > 1e12: # Likely milliseconds
                        ts = datetime.fromtimestamp(ts_raw / 1000.0)
                    elif ts_raw > 0:
                        ts = datetime.fromtimestamp(ts_raw)
                    else:
                        ts = datetime.now()
                except (OSError, ValueError, OverflowError):
                    # Fallback for invalid timestamps
                    ts = datetime.now()

            # Determine if unread
            is_unread = False
            horizon = self.consumption_horizons.get(conv_id, 0)
            # Teams timestamps might be string in metadata but int here
            try:
                if ts_raw > horizon:
                    is_unread = True
            except (TypeError, ValueError):
                pass

                messages_by_conv[conv_id].append(Message(
                    id=msg_id,
                    sender_id=sender_mri or "unknown",
                    sender_name=sender_name,
                    content=str(content),
                    timestamp=ts,
                    conversation_id=conv_id,
                    is_unread=is_unread
                ))

        # 3. Assemble
        for raw_conv in raw_conversations:
            # Improved Thread Type detection
            thread_type = raw_conv.get("threadType")
            cid = raw_conv.get("id", "")
            
            if not thread_type:
                if "@thread.tacv2" in cid or "@thread.v2" in cid:
                    thread_type = "Topic"
                elif "meeting_" in cid:
                    thread_type = "Meeting"
                else:
                    thread_type = "Chat"

            thread_props = raw_conv.get("threadProperties", {})
            title = raw_conv.get("displayName") or raw_conv.get("topic") or cid
            
            # For Channels (Topics) or Spaces (Teams)
            is_space = raw_conv.get("type") == "Space"
            if thread_type == "Topic" or is_space:
                # Try to get the Team name from diversos fields
                team_name = raw_conv.get("displayName") or \
                            thread_props.get("spaceThreadTopic") or \
                            thread_props.get("description")
                
                channel_name = raw_conv.get("topic")
                
                if team_name and channel_name and team_name != channel_name:
                    title = f"{team_name} > {channel_name}"
                elif channel_name:
                    title = channel_name
                elif team_name:
                    title = team_name
            
            # Teams uses "isRead" which is True if read, but sometimes it's missing or "isRead": False
            # We want to be careful: if missing, assume read unless we find unread messages
            is_read_meta = thread_props.get("isRead", True)
            if isinstance(is_read_meta, str):
                is_read_meta = is_read_meta.lower() == "true"
            
            last_ts_raw = raw_conv.get("lastMessageTimeUtc", 0)
            try:
                if last_ts_raw > 1e12:
                    last_ts = datetime.fromtimestamp(last_ts_raw / 1000.0)
                elif last_ts_raw > 0:
                    last_ts = datetime.fromtimestamp(last_ts_raw)
                else:
                    last_ts = datetime.now()
            except (OSError, ValueError, OverflowError):
                last_ts = datetime.now()
            
            # Extract hidden status
            is_hidden = thread_props.get("hidden", False)
            if isinstance(is_hidden, str):
                is_hidden = is_hidden.lower() == "true"

            # Determine if unread using both horizon and isRead metadata
            horizon = self.consumption_horizons.get(cid, 0)
            
            # Additional consumption horizon check from conversation record itself
            conv_props = raw_conv.get("properties", {})
            conv_horizon_raw = conv_props.get("consumptionhorizon")
            if conv_horizon_raw:
                try:
                    for p in str(conv_horizon_raw).split(';'):
                        try:
                            val_f = float(p.strip())
                            if val_f > horizon:
                                horizon = val_f
                        except: continue
                except:
                    pass

            msgs = sorted(messages_by_conv.get(cid, []), key=lambda x: x.timestamp)
            unread_count = sum(1 for m in msgs if m.is_unread)
            
            # Heuristic: If last message is after the latest read horizon, it's unread
            if last_ts_raw > horizon:
                # We prioritize the calculated unread count, but if it's 0 
                # (due to missing local messages) and last_ts > horizon, 
                # we force it to at least 1 to show it's unread.
                if unread_count == 0:
                   unread_count = 1
            
            # If metadata says unread but we found 0 unread messages (horizon issue), 
            # we should still treat it as unread.
            if not is_read_meta and unread_count == 0:
                unread_count = 1

            # If it's too old (like the Zeb chat from Oct 2025), and user only sees "two",
            # we should probably trust the metadata more but maybe one of them is "archived"
            # We'll keep the unread_count but unread.py will filter by recency to match user report.
            
            conversations.append(Conversation(
                id=cid,
                title=title,
                last_message_time=last_ts,
                messages=msgs,
                unread_count=unread_count,
                is_read_metadata=is_read_meta,
                hidden=is_hidden,
                thread_type=thread_type
            ))

        return sorted(conversations, key=lambda x: x.last_message_time, reverse=True)

# --- Execution ---

def main():
    app_data = os.environ.get("LOCALAPPDATA", "")
    db_path = Path(app_data) / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb"

    print(f"Initializing Teams Message Bridge...")
    try:
        with TeamsExtractor(db_path) as extractor:
            conversations = extractor.get_conversations()
            
            print(f"\nFound {len(conversations)} conversations.\n")
            print("=" * 60)
            
            for conv in conversations[:10]: # Show top 10
                print(f"CONVERSATION: {conv.title}")
                print(f"ID: {conv.id}")
                print(f"Last Active: {conv.last_message_time}")
                print(f"Messages Saved Locally: {len(conv.messages)}")
                print("-" * 30)
                
                # Show last 3 messages
                for msg in conv.messages[-3:]:
                    print(f"[{msg.timestamp.strftime('%Y-%m-%d %H:%M')}] {msg.sender_name}: {msg.content[:100]}...")
                
                print("=" * 60)

    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
