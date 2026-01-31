# libteamsdb

A robust library for reading Microsoft Teams IndexedDB data with comprehensive type safety and testing support.

## Features

- **Cross-platform**: Works on Windows, macOS, and Linux with automatic database discovery
- **Type-safe**: Fully typed with Pydantic models and mypy strict mode compliance
- **Robust discovery**: Automatically finds Teams databases across different installations (Classic 1.x, New 2.x, browser-based)
- **Synthetic testing**: Generate test data for unit testing without accessing real databases
- **Anonymization**: Create anonymized copies of real databases for testing
- **No `# type: ignore`**: All external library interfaces properly typed with protocols

## Installation

```bash
# Using uv (recommended)
uv pip install -e libteamsdb/

# Using pip
pip install -e libteamsdb/
```

## Quick Start

### Basic Usage

```python
from libteamsdb import TeamsDatabaseDiscovery, TeamsDatabaseExtractor

# Auto-discover database
discovery = TeamsDatabaseDiscovery()
location = discovery.find_first()

# Extract conversations
with TeamsDatabaseExtractor(location.path) as extractor:
    conversations = extractor.get_conversations()
    
    for conv in conversations:
        print(f"{conv.title}: {conv.unread_count} unread")
        for msg in conv.messages:
            print(f"  [{msg.timestamp}] {msg.sender_name}: {msg.content}")
```

### Manual Database Path

```python
from pathlib import Path
from libteamsdb import TeamsDatabaseExtractor

db_path = Path("/path/to/https_teams.microsoft.com_0.indexeddb.leveldb")

with TeamsDatabaseExtractor(db_path) as extractor:
    conversations = extractor.get_conversations()
```

### Listing Database Locations

```python
from libteamsdb import TeamsDatabaseDiscovery

discovery = TeamsDatabaseDiscovery()
locations = discovery.discover()

for loc in locations:
    print(f"{loc.source}: {loc.path}")
```

## Testing with Synthetic Data

### Generate Synthetic Test Data

```python
from libteamsdb import TeamsIndexedDB

# Generate synthetic data
db = TeamsIndexedDB()
db.generate_synthetic(
    num_conversations=10,
    messages_per_conv=(5, 20),
    num_users=5
)

# Dump to LevelDB for testing
db.dump_to_leveldb(Path("./test_data/synthetic"), anonymize=False)
```

### Anonymize Real Database

```bash
python libteamsdb/generate_synthetic_data.py \
    --from-real /path/to/real/db \
    --output ./test_data/anonymized
```

### Generate from Command Line

```bash
# Generate synthetic data
python libteamsdb/generate_synthetic_data.py \
    --generate \
    --output ./test_data/synthetic \
    --conversations 20

# Export to JSON for inspection
python libteamsdb/generate_synthetic_data.py \
    --from-real /path/to/db \
    --json-output ./export.json

# Validate a database
python libteamsdb/generate_synthetic_data.py --validate /path/to/db

# Discover all databases
python libteamsdb/generate_synthetic_data.py --discover
```

## Architecture

### Core Components

- **TeamsDatabaseDiscovery**: Cross-platform database location discovery
- **TeamsDatabaseExtractor**: Main extraction engine with context manager support
- **Pydantic Models**: `Conversation`, `Message`, `UserProfile`, `ThreadType`
- **TeamsIndexedDB**: Synthetic data generation and database manipulation
- **Type Wrappers**: Typed interfaces to ccl_chromium_reader library

### Database Support

#### Windows
- Classic Teams 1.x: `%APPDATA%\Microsoft\Teams\IndexedDB\`
- New Teams 2.x: `%LOCALAPPDATA%\Packages\MSTeams_*\LocalCache\...`
- Chrome/Edge browser storage

#### macOS
- Classic Teams: `~/Library/Application Support/Microsoft/Teams/IndexedDB/`
- New Teams: `~/Library/Containers/com.microsoft.teams2/...`
- Chrome/Edge browser storage

#### Linux
- Native Classic: `~/.config/Microsoft/Microsoft Teams/IndexedDB/`
- teams-for-linux (Snap): `~/snap/teams-for-linux/current/.config/...`

## Testing

```bash
# Run tests with pytest
cd libteamsdb
pytest

# Run with coverage
pytest --cov=libteamsdb --cov-report=html
```

## Type Safety

This library uses mypy in strict mode with:
- Complete type coverage (no implicit Any)
- Protocol-based interfaces for external libraries
- Pydantic models for validation
- No `# type: ignore` comments

```bash
# Run type checking
mypy libteamsdb/
```

## Consumer Scripts

The following scripts use libteamsdb:

- **list_unread_chats.py**: List unread 1:1 and group chats
- **list_unread_teams_topics.py**: List unread channel conversations
- **viewer.py**: Interactive TUI for browsing conversations

## Schema Change Detection

The synthetic data infrastructure helps detect Teams IndexedDB schema changes:

1. Models capture expected structure
2. Real databases are validated against models
3. Schema changes cause validation failures
4. Tests identify which fields/structure changed

## License

MIT License - See LICENSE file for details

## Contributing

Contributions welcome! Please ensure:
- Type safety with mypy strict mode
- Tests for new functionality
- Synthetic data generators for testing
- No personal data in test fixtures
