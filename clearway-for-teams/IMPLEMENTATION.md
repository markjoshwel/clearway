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
| **Conversations** | `Teams:conversation-manager` | 1 | `conversations` | `id`, `threadProperties`, `version`, `source` |
| **Messages Cache** | `Teams:replychain-manager` | 1 | `replychains` | `conversationId`, `originalArrivalTimestamp`, `content`, `creatorMri` |
| **Read Markers** | `Teams:replychain-metadata-manager` | 1 | `replychainmetadata` | `conversationId`, `consumptionHorizon` |
| **User Profiles** | `Teams:profiles` | 1 | `profiles` | `mri`, `displayName`, `mail` |
| **Unread Summary** | `Teams:messaging-slice-manager` | 2 | `threads-internal-items` | `unreadCount`, `totalCount` (Summary only) |

### Technical Challenges & Logic

#### 1. Database Locking
Chromium DBs are locked when Teams is running. 
- **Solution**: The bridge copies the entire `.leveldb` folder to `%TEMP%` before opening. The `LOCK` file is ignored during copy.

#### 2. Deduplication & Conflicts
Teams stores multiple records for the same conversation ID across different "sources" (e.g., Sources 4, 5, 6).
- **Rule**: Sort by `version` or `detailsVersion` descending.
- **Source Conflict**: If versions are identical, the record with `isRead: False` in `threadProperties` is preferred to ensure unread messages are surfaced.

#### 3. Unread Detection (Heuristic Approach)
The "Unread" count in the Teams UI is complex. The bridge uses a multi-layered detection:
1.  **Consumption Horizon**: If `originalArrivalTimestamp > consumptionHorizon`, the message is considered unread.
2.  **Metadata Flag**: `threadProperties.isRead` (Boolean) provides a direct indicator from the conversation manager.
3.  **Recency Filter**: To match the user's "Active" view, the bridge applies a 7-day recency window and filters out `threadType: meeting` or hidden chats.

#### 4. Message Enrichment
Messages in `replychains` contain MRIs (e.g., `8:orgid:uuid`). The bridge joins these with the `profiles` database to display human-readable names.

## Project Architecture

- `teams_bridge.py`: Core `TeamsExtractor` class. Handles snapshotting, DB iteration via `ccl-chromium-reader`, schema mapping, and deduplication.
- `viewer.py`: Textual-based TUI. Displays a list of conversations with unread counts and a message pane.
- `unread.py`: CLI utility for quick unread summaries, focusing on active direct chats.

## Dependencies

- `ccl-chromium-reader`: Essential for parsing the Chromium IndexedDB structure without C++ compilers.
- `textual`: Modern TUI framework.
- `pydantic` / `dataclasses`: For strict data modeling.

## Known Limitations
- **Read-Only**: No ability to send messages or mark them as read in the official DB (requires API interaction).
- **Local Cache**: Only displays messages cached locally by the Teams client.
- **Schema Volatility**: Microsoft changes internal store structures frequently.
