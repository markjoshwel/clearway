# Telegram Bridge: Telethon Implementation Details

## Implementation Details

### Library

- **Telethon**: A pure Python 3 MTProto client library for Telegram. Used for its robust async support and comprehensive coverage of the Telegram API.

### Authentication

- Uses `api_id` and `api_hash` obtained from [my.telegram.org](https://my.telegram.org).
- Supports session-based persistence using `.session` files stored in a local `sessions/` directory.
- First-run requires phone number and code entry via the terminal (handled by `client.start()`).

### Data Model Mapping

- **Conversations**: Maps to Telethon `Dialog` objects.
- **Messages**: Maps to Telethon `Message` objects.
- **Unread Logic**:
  - Uses `dialog.unread_count` for the total unread count.
  - Individual message unread status is determined by comparing `msg.id` with `dialog.read_inbox_max_id`.

### Technical Challenges

1. **Async Context**: Unlike the Teams bridge (which is synchronous), the Telegram bridge is fully asynchronous to handle real-time updates and efficient API calls.
2. **Entity Resolution**: Telethon requires "entities" to interact with chats. The bridge caches `UserProfile` data to minimize redundant entity lookups for sender names.

## Project Architecture

- `telegram_bridge.py`: Core `TelegramExtractor` class. Handles connection, dialog iteration, and message parsing.
- `pyproject.toml`: Managed by `uv`.

## Dependencies

- `telethon`: Core Telegram client.
- `python-dotenv`: For managing API credentials.

## Known Limitations

- **Rate Limiting**: Telegram enforces strict flood limits. The bridge uses `iter_dialogs` and `iter_messages` with sensible limits to avoid bans.
- **Read-Only**: Designed for listing unread content; does not support marking messages as read or sending replies.
