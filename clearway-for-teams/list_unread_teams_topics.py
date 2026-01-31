"""List unread Teams channel topics.

This script discovers the Teams database location and displays all
unread messages from Teams channels (topics).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn

from libteamsdb import (
    Conversation,
    DatabaseNotFoundError,
    ExtractionError,
    TeamsDatabaseDiscovery,
    TeamsDatabaseExtractor,
    ThreadType,
)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="List unread Teams channel topics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # List all unread channels
  %(prog)s --db-path /path    # Use specific database path
  %(prog)s --list-sources     # Show discovered database locations
        """,
    )

    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to Teams database (auto-discovered if not specified)",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List all discovered database sources and exit",
    )
    parser.add_argument(
        "--exclude-hidden",
        action="store_true",
        help="Exclude hidden/archived channels",
    )

    return parser.parse_args()


def list_sources() -> None:
    """Display all discovered database locations."""
    print("Discovering Teams database locations...\n")

    try:
        discovery = TeamsDatabaseDiscovery()
        locations = discovery.discover()

        print(f"Found {len(locations)} database location(s):\n")

        for idx, loc in enumerate(locations, 1):
            status = "✓ Valid" if discovery.validate_location(loc) else "✗ Invalid"
            print(f"{idx}. {loc.source}")
            print(f"   Platform: {loc.platform}")
            print(f"   Priority: {loc.priority}")
            print(f"   Path: {loc.path}")
            print(f"   Status: {status}\n")

    except DatabaseNotFoundError as e:
        print(f"No databases found: {e}")
        sys.exit(1)


def format_conversation(conv: Conversation) -> str:
    """Format a conversation for display.

    Args:
        conv: Conversation to format

    Returns:
        Formatted string representation
    """
    lines = []
    lines.append(f"{conv.title} ({conv.unread_count} unread)")

    # Show unread messages
    unread_msgs = [m for m in conv.messages if m.is_unread]
    for msg in unread_msgs:
        ts_str = msg.timestamp.strftime("%Y-%m-%d %H:%M")
        lines.append(f"  [{ts_str}] {msg.sender_name}: {msg.content}")

    return "\n".join(lines)


def list_unread_topics(
    db_path: Path | None,
    exclude_hidden: bool,
) -> int:
    """List unread channel topics from the Teams database.

    Args:
        db_path: Specific database path, or None to auto-discover
        exclude_hidden: Whether to exclude hidden channels

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    # Discover or use specified database
    if db_path is None:
        print("Discovering Teams database...")
        try:
            discovery = TeamsDatabaseDiscovery()
            location = discovery.find_first()
            db_path = location.path
            print(f"Found: {location.source} at {db_path}\n")
        except DatabaseNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
    else:
        print(f"Using database: {db_path}\n")

    # Extract and display unread channels
    try:
        with TeamsDatabaseExtractor(db_path) as extractor:
            conversations = extractor.get_conversations()

        unread_found = False
        unread_channels = []

        for conv in conversations:
            # Filter for topic/channel type only
            if conv.thread_type != ThreadType.TOPIC:
                continue

            # Skip hidden unless requested
            if conv.hidden and exclude_hidden:
                continue

            # Only show if there are unread messages
            if conv.unread_count > 0:
                unread_found = True
                unread_channels.append(conv)

        if not unread_found:
            print("No unread Teams Channels found.")
            return 0

        print(f"Unread Teams Channels ({len(unread_channels)} channel(s)):\n")

        for conv in unread_channels:
            print(format_conversation(conv))
            print()

        return 0

    except ExtractionError as e:
        print(f"Error extracting data: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def main() -> NoReturn:
    """Main entry point."""
    args = parse_args()

    if args.list_sources:
        list_sources()
        sys.exit(0)

    exit_code = list_unread_topics(
        db_path=args.db_path,
        exclude_hidden=args.exclude_hidden,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
