# Implementation Plan & Reverse Engineering Notes

## Goal
Create a read-only, unidirectional bridge to read Microsoft Teams (Work/School, "New Teams") conversation history and messages from the local database.

## Reverse Engineering Context

### Target Application
- **Name**: Microsoft Teams (New / V2)
- **Type**: Windows Store App / MSIX (WebView2 / Edge based)
- **Package Name**: `MSTeams_8wekyb3d8bbwe`
- **Primary Data Path**: `C:\Users\mark\AppData\Local\Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\EBWebView\WV2Profile_tfw\IndexedDB\https_teams.microsoft.com_0.indexeddb.leveldb`

### Database Schema (IndexedDB)
Research has identified the following critical databases and stores:

| Data Type | Database Name Snippet | Store Name |
| :--- | :--- | :--- |
| **Conversations** | `Teams:conversation-manager` | `conversations` |
| **Messages** | `Teams:replychain-manager` | `replychains` |
| **User Profiles** | `Teams:profiles` | `profiles` |
| **Sync State** | `Teams:syncstate-manager` | `syncstates` |

*Note: Database names include UUIDs and locale strings (e.g., `en-us`). Extraction must use fuzzy matching or iterate all databases to find the correct IDs.*

### Data Storage
- **Format**: LevelDB (via Chromium IndexedDB)
- **Structure**:
    - Chromium IndexedDB stores data in LevelDB.
    - Keys are complex, often containing store ID, index ID, and serialized keys.
    - Values are typically V8 serialized objects or similar binary formats.
    - We need to decode the specific "ObjectStores" used by Teams (e.g., `reply_chain`, `conversations`, `messages`).

### Challenges
1.  **File Locking**: LevelDB locks the database when open. The Teams client will likely hold a lock.
    - *Solution*: Copy the entire database directory to a temporary location before reading.
2.  **Decoding**: The keys and values are binary encoded.
    - We need to identify the correct object store IDs.
    - We need to decode the V8 serialized values (or whatever serialization Teams uses - possibly JSON or Protobuf inside the V8 wrapper).

## Proposed Architecture

### Core Script (`read_teams.py`)
1.  **Snapshot**: Copy the LevelDB folder to a temp dir.
2.  **Read**: Open the copy using a LevelDB library (`plyvel` or similar).
3.  **Iterate**: Walk through keys.
    - Filter for relevant object stores (need to reverse engineer which IDs correspond to "messages").
    - Heuristic: Look for JSON-like structures containing "content", "messageBody", "conversationId".
4.  **Parse**: Extract timestamp, sender, content, thread ID.
5.  **Output**: Print or return typed Python objects.

## Dependencies
- `plyvel` (or `plyvel-wheels` for easier Windows install)
- `typing` (standard)
- `shutil` (standard)

## User Review Required
- **Privacy**: This script accesses sensitive conversation data.
- **Stability**: Reading internal DB formats is brittle and may break with Teams updates.

## Next Steps
1.  Create a prototype script to dump raw keys/values to identify the structure.
2.  Refine the script to parse the specific message schema.
