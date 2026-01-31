# Oversight Clearway Bridge for ProtonMail

Implementation built around
[emersion's hydroxide](https://github.com/emersion/hydroxide), a third-party,
open-source ProtonMail CardDAV, IMAP and SMTP bridge built in Go.

## Implementation Status

| Component                                 | Status                  | Degree |
| ----------------------------------------- | ----------------------- | ------ |
| 1. Get Conversation List                  | **Implemented**         | Basic  |
| 2. Get Unread Conversation List           | **Implemented**         | Basic  |
| 3. Get Recent Conversation Communications | **Implemented**         | Basic  |
| 4. Notify Hook of New Communication       | **Implemented**         | Basic  |
| 5. Send Communication to Conversation     | Will Not Be Implemented | -      |

## Usage

### Prerequisites

1. Build hydroxide from `resources/hydroxide/`
2. Run `hydroxide auth <your-email>` to authenticate
3. Set up `.env` file with credentials:
   ```
   PROTONMAIL_USER=<bridge-username>
   PROTONMAIL_PASSWORD=<bridge-password>
   PROTONMAIL_WEBHOOK_URL=<optional-webhook-url>
   ```

### Commands

```bash
# Component 1: Get Conversation List
python protonmail_bridge.py get-conversation-list

# Component 2: Get Unread Conversation List
python protonmail_bridge.py get-unread-conversation-list

# Component 3: Get Recent Conversation Communications (last 24 hours by default)
python protonmail_bridge.py get-recent-conversation-communications [hours]

# Component 4: Notify Hook of New Communication
python protonmail_bridge.py notify-hook-of-new-communication

# Monitor mode (continuously checks every 60 seconds)
python protonmail_bridge.py monitor
```

## Features

- **IMAP Integration**: Connects to ProtonMail via hydroxide IMAP bridge
- **Unread Tracking**: Lists only unread emails
- **Notification Hooks**: 
  - Console notifications by default
  - Optional webhook support via `PROTONMAIL_WEBHOOK_URL`
  - Deduplication to prevent spam
  - State persistence across runs
- **Monitor Mode**: Continuously checks for new emails
- **Unicode Support**: Handles international characters in emails
