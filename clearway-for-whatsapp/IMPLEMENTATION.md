# WhatsApp Bridge: Neonize (Whatsmeow) Implementation Details

## Implementation Details

### Library

- **Neonize**: Python bindings for [whatsmeow](https://github.com/tulir/whatsmeow), a Go library for the WhatsApp Web multidevice API.
- **Rationale**: WhatsApp's protocol is complex and binary (Protobuf/Websockets). `whatsmeow` is the most stable open-source implementation, and `neonize` allows us to consume it from Python.

### Authentication

- **Multidevice Pairing**: Requires scanning a QR code with the official WhatsApp mobile app.
- **Session Storage**: Neonize manages an internal SQLite database (`whatsapp.db`) for session tokens and encryption keys.

### Data Model Mapping

- **Conversations**: Mapped from the internal store of synced chats.
- **Messages**: Captured via event listeners or queried from the local store.
- **Unread Logic**: WhatsApp unread status is often determined by the Presence and Receipt events.

### Technical Challenges

1. **Go Sidecar**: Neonize runs a Go binary in the background. This requires the system to have compatible binaries or the ability to compile them.
2. **Event-Driven Architecture**: Unlike typical REST APIs, WhatsApp data arrives via an event stream. The bridge must wait for the "Connected" and "Synced" events before data is reliable.
3. **Database Locking**: Similar to Teams, the underlying SQLite DB might be locked if another process is accessing it.

## Project Architecture

- `whatsapp_bridge.py`: Core `WhatsAppExtractor` class. Handles client lifecycle and event registration.
- `pyproject.toml`: Managed by `uv`.

## Dependencies

- `neonize`: Core WhatsApp engine.
- `python-dotenv`: For configuration.

## Known Limitations

- **Pairing Requirement**: Cannot run headless without prior pairing via a QR code.
- **Sync Latency**: Upon connection, it may take several seconds to several minutes to sync the full conversation history.
