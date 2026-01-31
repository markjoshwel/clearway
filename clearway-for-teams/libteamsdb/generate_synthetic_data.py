"""Generate synthetic Teams IndexedDB data for testing.

This script provides tools to:
1. Load real Teams databases and create anonymized copies for testing
2. Generate completely synthetic test data
3. Export databases to JSON for inspection
4. Validate database structure against expected schemas

Usage:
    # Create anonymized copy of real database
    python generate_synthetic_data.py --from-real /path/to/real/db --output ./test_data/anonymized

    # Generate completely synthetic data
    python generate_synthetic_data.py --generate --output ./test_data/synthetic --conversations 20

    # Export to JSON for inspection
    python generate_synthetic_data.py --from-real /path/to/real/db --json-output ./test_data/export.json

    # Validate a database structure
    python generate_synthetic_data.py --validate /path/to/db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import NoReturn, Optional

from libteamsdb import DatabaseNotFoundError, TeamsDatabaseDiscovery
from libteamsdb.synthetic import TeamsIndexedDB, load_real_db_anonymize


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic Teams IndexedDB data for testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Anonymize real database
  %(prog)s --from-real /path/to/real/db --output ./test_data/anonymized

  # Generate synthetic data
  %(prog)s --generate --output ./test_data/synthetic --conversations 20

  # Export to JSON
  %(prog)s --from-real /path/to/db --json-output ./export.json

  # Validate database
  %(prog)s --validate /path/to/db
        """,
    )

    # Source options
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--from-real",
        type=Path,
        metavar="PATH",
        help="Load and anonymize a real Teams database",
    )
    source_group.add_argument(
        "--generate",
        action="store_true",
        help="Generate completely synthetic test data",
    )
    source_group.add_argument(
        "--validate",
        type=Path,
        metavar="PATH",
        help="Validate a database structure",
    )
    source_group.add_argument(
        "--discover",
        action="store_true",
        help="Discover and list available database locations",
    )

    # Output options
    parser.add_argument(
        "--output",
        type=Path,
        metavar="PATH",
        help="Output path for LevelDB database",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        metavar="PATH",
        help="Export to JSON format for inspection",
    )

    # Generation options
    parser.add_argument(
        "--conversations",
        type=int,
        default=10,
        metavar="N",
        help="Number of conversations to generate (default: 10)",
    )
    parser.add_argument(
        "--min-messages",
        type=int,
        default=5,
        metavar="N",
        help="Minimum messages per conversation (default: 5)",
    )
    parser.add_argument(
        "--max-messages",
        type=int,
        default=20,
        metavar="N",
        help="Maximum messages per conversation (default: 20)",
    )
    parser.add_argument(
        "--users",
        type=int,
        default=5,
        metavar="N",
        help="Number of synthetic users (default: 5)",
    )

    # Anonymization options
    parser.add_argument(
        "--no-anonymize",
        action="store_true",
        help="Skip anonymization when copying real database",
    )

    return parser.parse_args()


def discover_databases() -> int:
    """Discover and list available database locations."""
    print("Discovering Teams database locations...\n")

    try:
        discovery = TeamsDatabaseDiscovery()
        locations = discovery.discover()

        print(f"Found {len(locations)} database location(s):\n")

        for idx, loc in enumerate(locations, 1):
            valid = discovery.validate_location(loc)
            status = "✓ Valid" if valid else "✗ Invalid"
            print(f"{idx}. {loc.source}")
            print(f"   Platform: {loc.platform}")
            print(f"   Priority: {loc.priority}")
            print(f"   Path: {loc.path}")
            print(f"   Status: {status}\n")

        return 0

    except DatabaseNotFoundError as e:
        print(f"No databases found: {e}")
        return 1


def anonymize_database(
    db_path: Path,
    output_path: Path,
    anonymize: bool,
    json_output: Optional[Path],
) -> int:
    """Load real database and create anonymized copy.

    Args:
        db_path: Path to real database
        output_path: Path for output database
        anonymize: Whether to anonymize data
        json_output: Optional JSON export path

    Returns:
        Exit code
    """
    print(f"Loading database from: {db_path}")

    try:
        db = TeamsIndexedDB()
        db.load_from_leveldb(db_path)

        print(f"Loaded {len(db.databases)} database(s)")
        for db_id, indexed_db in db.databases.items():
            print(f"  Database {db_id}: {indexed_db.name}")
            print(f"    Stores: {len(indexed_db.stores)}")
            for store_id, store in indexed_db.stores.items():
                print(f"      Store {store_id}: {len(store.records)} records")

        # Export to JSON if requested
        if json_output:
            print(f"\nExporting to JSON: {json_output}")
            export_to_json(db, json_output)

        # Dump to LevelDB if requested
        if output_path:
            print(f"\nWriting to LevelDB: {output_path}")
            db.dump_to_leveldb(output_path, anonymize=anonymize)
            print(f"Database written successfully (anonymized={anonymize})")

        return 0

    except FileNotFoundError as e:
        print(f"Error: Database not found - {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        print(f"Error: Required library not installed - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def generate_synthetic_data(
    output_path: Path,
    num_conversations: int,
    min_messages: int,
    max_messages: int,
    num_users: int,
    json_output: Optional[Path],
) -> int:
    """Generate completely synthetic test data.

    Args:
        output_path: Path for output database
        num_conversations: Number of conversations
        min_messages: Minimum messages per conversation
        max_messages: Maximum messages per conversation
        num_users: Number of users
        json_output: Optional JSON export path

    Returns:
        Exit code
    """
    print(f"Generating synthetic data:")
    print(f"  Conversations: {num_conversations}")
    print(f"  Messages per conv: {min_messages}-{max_messages}")
    print(f"  Users: {num_users}")

    try:
        db = TeamsIndexedDB()
        db.generate_synthetic(
            num_conversations=num_conversations,
            messages_per_conv=(min_messages, max_messages),
            num_users=num_users,
        )

        print(f"\nGenerated {len(db.databases)} database(s)")

        # Export to JSON if requested
        if json_output:
            print(f"\nExporting to JSON: {json_output}")
            export_to_json(db, json_output)

        # Dump to LevelDB if requested
        if output_path:
            print(f"\nWriting to LevelDB: {output_path}")
            db.dump_to_leveldb(output_path, anonymize=False)
            print("Database written successfully")

        return 0

    except ImportError as e:
        print(f"Error: Required library not installed - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def validate_database(db_path: Path) -> int:
    """Validate a database structure.

    Args:
        db_path: Path to database

    Returns:
        Exit code
    """
    print(f"Validating database: {db_path}")

    try:
        db = TeamsIndexedDB()
        db.load_from_leveldb(db_path)

        print("\n✓ Database loaded successfully")
        print(f"\nStructure:")
        print(f"  Total databases: {len(db.databases)}")

        # Check for expected databases
        expected_dbs = [
            ("Teams:profiles", "User profiles"),
            ("Teams:conversation-manager", "Conversations"),
            ("Teams:replychain-manager", "Messages"),
            ("Teams:replychain-metadata-manager", "Metadata"),
        ]

        print("\nExpected databases:")
        for name, desc in expected_dbs:
            found_db = db.find_database_by_name(name)
            if found_db:
                print(f"  ✓ {desc} ({name}): ID {found_db.db_id}")
                print(f"      Stores: {len(found_db.stores)}")
                for store_id, store in found_db.stores.items():
                    print(f"        Store {store_id}: {len(store.records)} records")
            else:
                print(f"  ✗ {desc} ({name}): NOT FOUND")

        return 0

    except FileNotFoundError as e:
        print(f"\n✗ Database not found: {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        print(f"\n✗ Required library not installed: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n✗ Validation error: {e}", file=sys.stderr)
        return 1


def export_to_json(db: TeamsIndexedDB, output_path: Path) -> None:
    """Export database to JSON for inspection.

    Args:
        db: Database to export
        output_path: Output file path
    """
    export_data = {
        "metadata": {
            "source_path": str(db.source_path) if db.source_path else None,
            "loaded_at": db.loaded_at.isoformat(),
            "num_databases": len(db.databases),
        },
        "databases": {},
    }

    for db_id, indexed_db in db.databases.items():
        db_data = {
            "name": indexed_db.name,
            "stores": {},
        }

        for store_id, store in indexed_db.stores.items():
            db_data["stores"][store_id] = {
                "name": store.name,
                "num_records": len(store.records),
                "records": [
                    {
                        "key": str(record.key),
                        "value": record.value,
                    }
                    for record in store.records[:100]  # Limit to first 100 per store
                ],
            }

        export_data["databases"][db_id] = db_data

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_data, f, indent=2, default=str)

    print(f"Exported to: {output_path}")


def main() -> NoReturn:
    """Main entry point."""
    args = parse_args()

    # Discover mode
    if args.discover:
        exit_code = discover_databases()
        sys.exit(exit_code)

    # Validate mode
    if args.validate:
        exit_code = validate_database(args.validate)
        sys.exit(exit_code)

    # Anonymize mode
    if args.from_real:
        if not args.output and not args.json_output:
            print("Error: --output or --json-output required", file=sys.stderr)
            sys.exit(1)

        exit_code = anonymize_database(
            db_path=args.from_real,
            output_path=args.output,
            anonymize=not args.no_anonymize,
            json_output=args.json_output,
        )
        sys.exit(exit_code)

    # Generate mode
    if args.generate:
        if not args.output and not args.json_output:
            print("Error: --output or --json-output required", file=sys.stderr)
            sys.exit(1)

        exit_code = generate_synthetic_data(
            output_path=args.output,
            num_conversations=args.conversations,
            min_messages=args.min_messages,
            max_messages=args.max_messages,
            num_users=args.users,
            json_output=args.json_output,
        )
        sys.exit(exit_code)

    # No action specified
    print(
        "Error: No action specified. Use --from-real, --generate, --validate, or --discover"
    )
    print("Run with --help for usage information")
    sys.exit(1)


if __name__ == "__main__":
    main()
