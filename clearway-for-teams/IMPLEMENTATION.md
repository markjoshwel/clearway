# Teams Bridge: Reverse Engineering & Implementation Details

## Reverse Engineering Findings

### Database Location

Teams stores its data in Chromium's IndexedDB format using LevelDB as the underlying storage engine:

**Windows (Teams 2.x - Current)**:
```
%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\WV2Profile_tfw\IndexedDB\https_teams.microsoft.com_0.indexeddb.leveldb
```

**Format**: Chromium IndexedDB (LevelDB backend). The database consists of multiple `.ldb` files containing binary protobuf data, plus metadata files (`MANIFEST`, `CURRENT`, etc.).

### Database & Store Mapping

Teams spreads data across numerous IndexedDB databases, each identified by a unique database ID. The naming convention includes the database purpose plus user-specific identifiers:

| Content Type | Database Name Pattern | Store ID | Key Fields |
| :--- | :--- | :--- | :--- |
| **Conversations** | `Teams:conversation-manager:{client}:{user-id}:{locale}` | 1 | `id`, `threadProperties`, `threadType`, `chatTitle`, `lastMessage` |
| **Messages/Replies** | `Teams:replychain-manager:{client}:{user-id}:{locale}` | 1 | `conversationId`, `replyChainId`, `messageMap`, `consumptionHorizon` |
| **Read Markers (Legacy)** | `Teams:replychain-metadata-manager:{client}:{user-id}:{locale}` | 1 | `conversationId`, `consumptionHorizon` |
| **User Profiles** | `Teams:profiles:{client}:{user-id}:{locale}` | 1 | `mri`, `displayName`, `mail` |

**Key Discovery**: Each database name includes dynamic components (client type, user ID, locale), so the code searches for databases by name snippet (e.g., `Teams:conversation-manager`) rather than exact match.

### Data Structure Deep Dive

#### Conversation Records (`Teams:conversation-manager`)

Each conversation record contains:

```python
{
  "id": "19:uuid_uuid@unq.gbl.spaces",  # Conversation ID
  "type": "Chat",  # or "Topic" for channels
  "threadType": "Chat",
  "threadProperties": {
    "isRead": "false",  # Unread indicator
    "hidden": "false",  # Archive/hidden status
    # ... other properties
  },
  "chatTitle": {  # For 1:1 and group chats
    "shortTitle": "John Doe",  # Other person's name
    "longTitle": "John Doe, Jane Smith /IM",  # All participants
    "avatarUsersInfo": [...]  # User details
  },
  "lastMessage": {
    "content": b'Hello World',  # Raw bytes, often UTF-8
    "originalArrivalTime": 1769563301037.0  # Unix timestamp (milliseconds)
  },
  "lastMessageTimeUtc": 1769563301037.0,
  "version": 1769563301222.0,  # For deduplication
  "detailsVersion": 1714382842699.0
}
```

**Key Finding**: The `chatTitle` field (not `displayName` or `topic`) contains the human-readable conversation title for direct chats. For channels, `displayName` or `topic` is used.

#### Reply Chain Records (`Teams:replychain-manager`)

Messages are organized in reply chains (threads). Each record represents a reply chain within a conversation:

```python
{
  "conversationId": "19:uuid_uuid@unq.gbl.spaces",
  "replyChainId": "19:uuid_uuid@unq.gbl.spaces",  # Same as conv ID for simple chats
  "messageMap": {
    "message-id-1": {
      "id": "message-id-1",
      "content": "Hello!",  # or HTML: "<p>Hello!</p>"
      "contentType": "Text",  # or "Html"
      "from": "8:orgid:uuid",  # Sender MRI
      "imDisplayName": "John Doe",  # Sender name (fallback)
      "originalArrivalTime": 1769563301037.0,  # Milliseconds since epoch
      "originalArrivalTimestamp": 1769563301037.0,  # Alternative field
      "isSentByCurrentUser": False
    }
  },
  "consumptionHorizon": "1769563301037;0;0",  # Read marker (semicolon-separated)
  "consumptionHorizonBookmark": 1769563301037.0
}
```

**Critical Discovery**: In current Teams versions, the consumption horizon (read marker) is stored in the `Teams:replychain-manager` database within each reply chain record, NOT in a separate metadata database. The older `Teams:replychain-metadata-manager` database may be empty or unused in newer Teams versions.

#### User Profiles (`Teams:profiles`)

```python
{
  "mri": "8:orgid:uuid",  # Machine-readable identifier
  "displayName": "John Doe",
  "mail": "john.doe@example.com"
}
```

### Technical Challenges & Logic

#### 1. Database Locking

Chromium locks the LevelDB files when Teams is running, preventing direct access.

**Solution**: Copy the entire `.leveldb` folder to a temporary location (`%TEMP%\teamsdb_*`) before opening. The `LOCK` file is excluded during copy to avoid file lock conflicts.

#### 2. Deduplication & Version Conflicts

Teams stores multiple versions of the same conversation record. Each record has version fields (`version`, `detailsVersion`, `threadVersion`) that increase with updates.

**Algorithm**:
1. Group records by `conversationId`
2. Keep the record with the highest `version` (or `detailsVersion` as fallback)
3. If versions are identical, prefer the record where `threadProperties.isRead == False` (unread state takes precedence)

#### 3. Unread Detection (Multi-Layer Heuristic)

Unread detection is complex because Teams uses multiple indicators:

**Layer 1: Consumption Horizon** (Primary)
- Parse `consumptionHorizon` from reply chain records (semicolon-separated: `timestamp;userId;other`)
- Use the maximum timestamp as the "read up to" point
- Messages with `originalArrivalTime > horizon` are unread

**Layer 2: Conversation Metadata** (Fallback)
- Check `threadProperties.isRead` field
- If `"false"`, conversation has unread messages

**Layer 3: Last Message Time** (Heuristic)
- If `lastMessageTimeUtc > max(consumptionHorizon)` and no unread messages detected, force unread count = 1

**Layer 4: Message Marking** (Display)
- When metadata says unread but no horizon exists, mark the most recent message as unread for display purposes

#### 4. Title Extraction Chain

Different conversation types store titles in different fields:

**For Direct Chats (1:1)**:
1. `chatTitle.shortTitle` (preferred - other person's name)
2. `chatTitle.longTitle` (all participants)
3. `displayName` (rarely present)
4. `id` (fallback - conversation ID)

**For Group Chats**:
1. `chatTitle.longTitle` (all participants)
2. `chatTitle.shortTitle` (truncated)
3. `displayName` (if set by user)
4. `id` (fallback)

**For Channels (Topics)**:
1. `displayName` (team name)
2. `topic` (channel name)
3. Combine as `"Team Name > Channel Name"` if both present
4. `spaceThreadTopic` or `description` (fallbacks)

#### 5. Timestamp Handling

Teams uses multiple timestamp formats:
- **Milliseconds since epoch** (most common): `1769563301037.0`
- **ISO 8601 strings**: `"2026-01-28T01:21:41.037Z"`
- **Seconds since epoch** (rare): `1769563301`

**Parsing Strategy**:
- Values > 1e12 are treated as milliseconds (divide by 1000)
- String values are parsed as ISO 8601 or float
- Invalid/missing timestamps default to `datetime.now()`

#### 6. Content Format

Message content can be:
- **Plain text**: `"Hello World"`
- **HTML**: `"<p>Hello World</p>"`
- **Raw bytes**: `b'Hello World'` (UTF-8 encoded)
- **Rich content**: May contain mentions, formatting, etc.

The code handles all formats and leaves HTML as-is (consumer can strip tags if needed).

#### 7. ccl-chromium-reader Integration

The `ccl_chromium_reader` library provides low-level IndexedDB access:

```python
from ccl_chromium_reader import ccl_chromium_indexeddb

db = ccl_chromium_indexeddb.IndexedDb(db_path)

# Iterate databases
for db_id in db.global_metadata.db_ids:
    print(f"DB {db_id.dbid_no}: {db_id.name}")

# Iterate records in a store
for record in db.iterate_records(database_id, store_id):
    key = record.key.value  # Record key
    value = record.value    # Parsed dict or None
```

**Key Lesson**: The library returns `Undefined` objects for missing fields (not `None`), which must be handled carefully during parsing.

### Conversation ID Patterns

| Pattern | Type | Example |
| :--- | :--- | :--- |
| `19:...@unq.gbl.spaces` | Direct/Group Chat | `19:uuid_uuid@unq.gbl.spaces` |
| `19:...@thread.tacv2` | Channel (Team) | `19:base64@thread.tacv2` |
| `19:...@thread.v2` | Channel (New) | `19:hex@thread.v2` |
| `48:...` | System/Internal | `48:annotations`, `48:mentions` |
| `19:meeting_...@thread.v2` | Meeting | `19:meeting_base64@thread.v2` |

**Filtering Strategy**:
- Exclude `48:` prefix (system conversations)
- Exclude `meeting` in ID (meeting chats)
- Filter by `threadType` field: `Chat` vs `Topic`

## Project Architecture

The codebase is organized as a Python package with the following structure:

```
clearway-for-teams/
├── libteamsdb/                    # Core database extraction library
│   ├── libteamsdb/
│   │   ├── __init__.py           # Public API exports
│   │   ├── extractor.py          # TeamsDatabaseExtractor class
│   │   ├── discovery.py          # TeamsDatabaseDiscovery class
│   │   ├── models.py             # Pydantic models (Conversation, Message, etc.)
│   │   ├── types.py              # Type wrappers and utilities
│   │   └── exceptions.py         # Custom exceptions
│   └── tests/                    # Test suite
├── list_unread_chats.py          # CLI: List unread direct chats
├── list_unread_teams_topics.py   # CLI: List unread channel topics
├── viewer.py                     # Interactive TUI viewer
└── teams_bridge.py               # Legacy bridge implementation
```

### Key Components

**TeamsDatabaseDiscovery** (`discovery.py`):
- Auto-discovers Teams database location on Windows
- Validates database structure and accessibility
- Returns `DatabaseLocation` objects with metadata

**TeamsDatabaseExtractor** (`extractor.py`):
- Context manager for safe database access
- Copies database to temp location to avoid file locks
- Loads and deduplicates conversations
- Calculates unread counts using multi-layer heuristics
- Joins messages with user profiles for display names

**Data Models** (`models.py`):
- `Conversation`: Represents a chat/channel with metadata
- `Message`: Individual message with sender, content, timestamp
- `UserProfile`: User information (MRI, display name, email)
- `ThreadType`: Enum for Chat vs Topic vs Meeting

### Usage Examples

**Basic extraction**:
```python
from libteamsdb import TeamsDatabaseDiscovery, TeamsDatabaseExtractor

discovery = TeamsDatabaseDiscovery()
location = discovery.find_first()

with TeamsDatabaseExtractor(location.path) as extractor:
    conversations = extractor.get_conversations()
    for conv in conversations:
        if conv.unread_count > 0:
            print(f"{conv.title}: {conv.unread_count} unread")
```

**CLI utilities**:
```bash
# List unread direct messages
uv run list_unread_chats.py

# List unread channel topics
uv run list_unread_teams_topics.py

# Interactive viewer
uv run viewer.py
```

## Dependencies

- **ccl-chromium-reader**: Low-level Chromium IndexedDB parsing (from GitHub)
- **pydantic**: Data validation and serialization
- **textual**: Terminal UI framework (for viewer.py)
- **pytest**: Testing framework

## Development Notes

### Running Tests
```bash
uv run pytest libteamsdb/tests/
```

### Installing in Editable Mode
```bash
uv pip install -e ./libteamsdb
```

### Database Schema Changes
If Teams updates their database schema:
1. Use debug scripts to inspect new field names
2. Update field extraction logic in `extractor.py`
3. Update `IMPLEMENTATION.md` with new findings
4. Add regression tests for new fields

## Known Limitations

1. **Read-Only Access**: Cannot send messages or mark as read (would require Teams API access)
2. **Local Cache Only**: Only sees messages cached locally by Teams client (recent conversations)
3. **Schema Volatility**: Microsoft may change field names/structures without notice
4. **No Real-Time Updates**: Must re-read database to see new messages
5. **Hidden Conversations**: Some unread conversations may be marked `hidden: true` (archived)
6. **Windows Only**: Currently only supports Windows Teams 2.x database paths
7. **Consumption Horizon**: Some conversations may show as unread but have no consumption horizon (metadata-only unread)
