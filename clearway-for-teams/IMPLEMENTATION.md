# Teams Bridge: Reverse Engineering & Implementation Details

## Goal
Build a read-only bridge for "New Teams" (V2) to extract and display conversation history and unread status.

## Reverse Engineering Findings

### Database Location
- **Registry/Path**: `%LOCALAPPDATA%\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\WV2Profile_tfw\IndexedDB\https_teams.microsoft.com_0.indexeddb.leveldb`
- **Format**: Chromium IndexedDB (backed by LevelDB).

### Database & Store Mapping

The application spreads data across numerous IndexedDB databases. Key mappings identified:

| Content Type | Database Name Snippet | Store Index | Store Name | Key Fields |
| :--- | :--- | :--- | :--- | :--- |
| **Channels** | `Teams:conversation-manager` | 1 | `conversations` | `id`, `threadProperties`, `threadType: Topic` |
| **1:1 / Group Chats** | `Teams:conversation-manager` | 1 | `conversations` | `id`, `threadProperties`, `threadType: Chat` |
| **Messages Cache** | `Teams:replychain-manager` | 1 | `replychains` | `conversationId`, `originalArrivalTimestamp`, `content` |
| **Read Markers** | `Teams:replychain-metadata-manager` | 1 | `replychainmetadata` | `conversationId`, `consumptionHorizon` |
| **User Profiles** | `Teams:profiles` | 1 | `profiles` | `mri`, `displayName`, `mail` |

### Technical Challenges & Logic

#### 1. Database Locking
Chromium DBs are locked when Teams is running. 
- **Solution**: The bridge copies the entire `.leveldb` folder to `%TEMP%` before opening. The `LOCK` file is ignored during copy.

#### 2. Deduplication & Conflicts
Teams stores multiple records for the same conversation ID across different "sources" (e.g., Sources 1, 2, 4).
- **Rule**: Sort by `version`, `detailsVersion`, or `threadVersion` descending.
- **Source Conflict**: If versions are identical, the record with `isRead: False` in `threadProperties` is preferred to ensure unread messages are surfaced.

#### 3. Unread Detection (Heuristic Approach)
The "Unread" count in the Teams UI is complex. The bridge uses a multi-layered detection:
1.  **Multi-part Consumption Horizon**: `consumptionhorizon` is often a semicolon-separated string (e.g., `TS1;TS2;ID`). The bridge parses all segments and treats the maximum valid timestamp as the "read-up-to" threshold.
2.  **Last Message Correlation**: If `lastMessageTimeUtc > max(consumptionHorizon)`, the conversation is flagged as unread even if local message content is missing from the cache.
3.  **Metadata Flag**: `threadProperties.isRead` (Boolean) provides a direct indicator.
4.  **No Recency Filter**: We removed hardcoded recency filters (e.g., 7 days) because Teams UI persists unread status for very old conversations.

#### 4. Channel Title Discovery
For Teams (Spaces), the friendly name is often not in the root `displayName` field.
- **Solution**: The title extraction logic uses a fallback chain: `displayName > topic > description > spaceThreadTopic`. This ensures Channels like "IMP TM55 Oct 2023" are correctly identified.

#### 5. `ccl-chromium-reader` API Lessons
- **Metadata Type**: The `get_database_metadata` method requires `meta_type=1` (integer) to correctly list object stores. Using string constants or incorrect enums can cause execution failures.

#### 6. Message Enrichment
Messages in `replychains` contain MRIs (e.g., `8:orgid:uuid`). The bridge joins these with the `profiles` database to display human-readable names.

## Project Architecture

- `teams_bridge.py`: Core `TeamsExtractor` class. Handles snapshotting, DB iteration, schema mapping, and unread heuristics.
- `viewer.py`: Textual-based TUI. Displays a list of conversations with unread indicators.
- `list_unread_chats.py` / `list_unread_teams_topics.py`: Targeted CLI utilities for quick unread summaries.

## Dependencies

- `ccl-chromium-reader`: Essential for parsing Chromium IndexedDB structure.
- `textual`: Modern TUI framework.
- `pydantic` / `dataclasses`: For data modeling.

## Known Limitations
- **Read-Only**: No ability to send messages or mark them as read.
- **Local Cache**: Only displays messages cached locally by the Teams client.
- **Schema Volatility**: Microsoft internal store structures are subject to change without notice.
