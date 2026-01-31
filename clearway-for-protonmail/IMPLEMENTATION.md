# Protonmail Bridge: Hydroxide Implementation Details

## Implementation Details

### Library / Tool

- **Hydroxide**: A third-party ProtonMail bridge.
- **Rationale**: ProtonMail's end-to-end encryption makes direct API access difficult. Hydroxide handles the complex SRP (Secure Remote Password) authentication and message decryption.

### Protocol Choice (SMTP vs IMAP)

- **Constraint**: The `hydroxide` documentation warns that IMAP support is experimental ("here be dragons").
- **Approach**: While SMTP is primarily for sending, the bridge focuses on listing unread messages.
- **Revised Method**: Instead of relying on the experimental IMAP server, the bridge can utilize the internal `protonmail` Go package logic or a CLI-based export mechanism to fetch unread message metadata.

### Data Model Mapping

- **Conversations**: Maps to ProtonMail `Conversation` objects (grouped by subject/participants).
- **Messages**: Maps to ProtonMail `Message` objects.
- **Unread Logic**: Uses the `Unread` filter in the internal `ListMessages` request or the `UNSEEN` status in the bridge.

### Technical Challenges

1. **End-to-End Encryption**: All message bodies must be decrypted locally. Hydroxide manages the PGP keys and decryption process.
2. **Bridge Persistence**: Hydroxide must be running and authenticated for the bridge to fetch data.
3. **Draft-Based Interaction**: Protonmail interaction often involves creating drafts.

## Project Architecture

- `protonmail_bridge.py`: Core `ProtonmailExtractor` class.
- `pyproject.toml`: Managed by `uv`.

## Dependencies

- `hydroxide`: Core engine (external Go binary).
- `python-dotenv`: For configuration.

## Known Limitations

- **IMAP Stability**: As noted in the documentation, the IMAP interface may be unstable.
- **Polling Latency**: Fetching and decrypting messages via a third-party bridge introduces some overhead.
