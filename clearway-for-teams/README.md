# Oversight Clearway Bridge for Microsoft Teams

Implementation based off reading Teams' IndexedDB and LevelDB

## Implementation Status

| Component                                 | Status                  | Degree |
| ----------------------------------------- | ----------------------- | ------ |
| 1. Get Conversation List                  | **Implemented**         | Naive  |
| 2. Get Unread Conversation List           | **Implemented**         | Naive  |
| 3. Get Recent Conversation Communications | **Implemented**         | Naive  |
| 4. Notify Hook of New Communication       | Not Implemented Yet     | Naive  |
| 5. Send Communication to Conversation     | Will Not Be Implemented | -      |

## Usage

### Commands

```bash
# Component 1: Get Conversation List
python teams_bridge.py get-conversation-list

# Component 2: Get Unread Conversation List
python teams_bridge.py get-unread-conversation-list

# Component 3: Get Recent Conversation Communications (last 24 hours by default)
python teams_bridge.py get-recent-conversation-communications [hours]

# Show help
python teams_bridge.py help
```

### Type Safety

This project uses strict type checking with both mypy and basedpyright:

```bash
# Run type checkers
uv run mypy --strict teams_bridge.py
uv run basedpyright teams_bridge.py
```

### Testing

```bash
# Run libteamsdb tests
uv run pytest libteamsdb/tests/ -v
```
