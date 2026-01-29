# Goal

Implement a Gmail “inbox poller” that (a) lists messages in INBOX, (b) lists unread in INBOX, (c) fetches recent message details, and (d) detects new mail every 15 minutes efficiently using incremental sync. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)

## Required setup (one-time)

- Use OAuth 2.0 to access Google APIs and store the resulting authorization on disk so subsequent runs don’t re-prompt. [developers.google](https://developers.google.com/workspace/gmail/api/quickstart/python)
- Install and use Google’s Python client (`google-api-python-client`) or call the same REST endpoints with `requests`; either way you’ll be calling `https://gmail.googleapis.com/gmail/v1/...` endpoints. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)

## Data model (persist these)

Persist the following locally:

- `last_history_id`: last known mailbox `historyId` you’ve synced up to (string/integer). [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
- `seen_message_ids`: set/table of Gmail `message.id` values you’ve already processed (used for dedupe). [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)

## API primitives (fact-checked endpoints)

All endpoints below use `userId=me` for “the authenticated user”. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)

### 1) List messages in INBOX (your “conversation list = inbox”)

Use `users.messages.list`: `GET https://gmail.googleapis.com/gmail/v1/users/{userId}/messages` with `labelIds=INBOX` and optional pagination. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)

Useful parameters:

- `labelIds[]`: filter by labels like `INBOX` and `UNREAD`. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- `maxResults`, `pageToken`: page through results. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)

### 2) List unread messages in INBOX

Option A (label filter): call `users.messages.list` with `labelIds=INBOX` and `labelIds=UNREAD`. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
Option B (query): call `users.messages.list` with `q="in:inbox is:unread"` (the API supports `q`). [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)

### 3) Fetch details for a message (for “recent communications”)

Use `users.messages.get`: `GET https://gmail.googleapis.com/gmail/v1/users/{userId}/messages/{id}`. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)
Use the `format` query parameter to choose the response shape (e.g., `metadata` for headers-only vs `full`), and `metadataHeaders[]` if you only want certain headers. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)

## Efficient 15-minute polling (incremental sync)

Google’s recommended approach for clients is: do an initial sync, then incremental sync using `history.list` starting from a stored `historyId`. [developers.google](https://developers.google.com/workspace/gmail/api/guides/sync)

### Initial sync (run once, then store checkpoint)

1. List recent messages from INBOX via `users.messages.list` (e.g., last 50–200 message IDs). [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
2. For each message ID you care about, call `users.messages.get` to fetch metadata you want to store/display. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)
3. Record a `historyId` checkpoint for the mailbox state you just synced (you’ll use it as `startHistoryId` later). [developers.google](https://developers.google.com/workspace/gmail/api/guides/sync)

### Incremental poll tick (every 15 minutes)

1. Call `users.history.list`: `GET https://gmail.googleapis.com/gmail/v1/users/{userId}/history` with required `startHistoryId=last_history_id`. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
2. Page through results using `pageToken` until exhausted, applying changes (new messages, label changes, deletes) based on what the history response contains. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)
3. Update `last_history_id` to the latest history ID you observed for next poll. [developers.google](https://developers.google.com/workspace/gmail/api/guides/sync)

### Required error handling

Gmail history is “typically available for at least one week” but can be shorter; if your `startHistoryId` is too old, the API returns HTTP 404 and you must do a full sync again (then store a fresh checkpoint). [developers.google](https://developers.google.com/workspace/gmail/api/guides/sync)

## Minimal Python implementation options

- **Google client library**: recommended path for speed of implementation; Google’s Python quickstart demonstrates that the first run prompts you to authorize, then stores authorization info on the filesystem for reuse. [developers.google](https://developers.google.com/workspace/gmail/api/quickstart/python)
- **Raw HTTP**: implement the same REST calls (`users.messages.list`, `users.messages.get`, `users.history.list`) with `requests` and an OAuth access token; the HTTP method + URL formats are specified in the REST reference (example: `users.messages.get` is a `GET` to `https://gmail.googleapis.com/gmail/v1/users/{userId}/messages/{id}`). [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)

## Suggested minimal workflow (LLM-friendly)

- Implement `list_inbox_message_ids(page_token=None, max_results=100)` using `users.messages.list` + `labelIds=INBOX`. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- Implement `get_message(id, format="metadata", metadata_headers=[...])` using `users.messages.get`. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)
- Implement `list_unread_inbox()` using `users.messages.list` + `labelIds=INBOX,UNREAD` (or `q`). [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- Implement `poll_changes(start_history_id)` using `users.history.list` + paging; on 404, trigger `full_resync()`. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.history/list)

If you tell me whether you want to store “email body” or only headers/snippet, I can constrain the exact `users.messages.get format` and fields to request. [developers.google](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/get)
