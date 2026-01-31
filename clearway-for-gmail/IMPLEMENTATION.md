# Gmail Bridge: Google API Implementation Details

## Implementation Details

### Library

- **Google API Python Client**: Official client for interacting with Google Workspace services.
- **google-auth-oauthlib**: Handles the OAuth2 flow for user authentication.

### Authentication

- **OAuth2**: Requires a `credentials.json` file from the Google Cloud Console.
- **Token Persistence**: Stores authorized user credentials in `token.json` to avoid re-authentication.
- **Scope**: Uses `gmail.readonly` to minimize permission footprint.

### Data Model Mapping

- **Conversations**: Maps to Gmail `Threads`. Gmail naturally groups related messages into threads, which aligns perfectly with the Clearway `Conversation` model.
- **Messages**: Maps to Gmail `Messages`.
- **Unread Logic**: Uses Gmail labels. A thread is considered unread if any message within it has the `UNREAD` label.

### Technical Challenges

1. **Rate Limiting**: The Gmail API has per-user and per-project quotas. The bridge uses optimized list/get operations to minimize quota consumption.
2. **OAuth Setup**: Requires the user to manually create a project in Google Cloud and download credentials, which is a hurdle compared to simple login-based bridges.

## Project Architecture

- `gmail_bridge.py`: Core `GmailExtractor` class. Handles OAuth flow, thread iteration, and message extraction.
- `pyproject.toml`: Managed by `uv`.

## Dependencies

- `google-api-python-client`: Official SDK.
- `google-auth-oauthlib`: OAuth support.
- `python-dotenv`: For configuration.

## Known Limitations

- **Polling Interval**: Designed for snapshot extraction. Frequent polling might hit API rate limits if not carefully managed.
- **Metadata Only**: By default, focuses on snippets and headers to remain lightweight.
