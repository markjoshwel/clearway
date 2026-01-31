"""Cross-platform Teams database discovery.

This module handles finding Microsoft Teams IndexedDB databases
across Windows, macOS, and Linux for various Teams installations.
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set
import logging

from .exceptions import DatabaseNotFoundError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DatabaseLocation:
    """Represents a discovered database location.

    Attributes:
        path: Path to the database directory
        source: Description of the source (e.g., "Teams 2.x", "Classic Teams")
        platform: The platform this location is for
        priority: Priority for ordering (lower = more preferred)
    """

    path: Path
    source: str
    platform: str
    priority: int = 0


class TeamsDatabaseDiscovery:
    """Discovers Microsoft Teams IndexedDB locations across platforms.

    This class implements a robust discovery mechanism that searches for
    Teams databases on Windows, macOS, and Linux across various installation
    types (Classic Teams 1.x, New Teams 2.x, Browser-based, etc.).
    """

    # Database name pattern to look for
    DB_NAME_PATTERN = "https_teams.microsoft.com_0.indexeddb.leveldb"

    def __init__(self) -> None:
        """Initialize the discovery instance."""
        self._system = platform.system()
        self._platform = platform.platform()

    def discover(self) -> List[DatabaseLocation]:
        """Discover all available Teams database locations.

        Returns:
            List of DatabaseLocation objects, ordered by priority

        Raises:
            DatabaseNotFoundError: If no databases are found
        """
        locations: Set[DatabaseLocation] = set()

        if self._system == "Windows":
            locations.update(self._discover_windows())
        elif self._system == "Darwin":
            locations.update(self._discover_macos())
        elif self._system == "Linux":
            locations.update(self._discover_linux())

        # Always try browser-based locations on all platforms
        locations.update(self._discover_browsers())

        if not locations:
            raise DatabaseNotFoundError(
                f"No Teams databases found on {self._system}. "
                "Please ensure Teams is installed and has been run at least once."
            )

        # Sort by priority (lower = more preferred)
        return sorted(locations, key=lambda loc: loc.priority)

    def find_first(self) -> DatabaseLocation:
        """Find the highest priority (most preferred) database location.

        Returns:
            The DatabaseLocation with the lowest priority number

        Raises:
            DatabaseNotFoundError: If no databases are found
        """
        locations = self.discover()
        return locations[0]

    def _discover_windows(self) -> Set[DatabaseLocation]:
        """Discover Teams databases on Windows."""
        locations: Set[DatabaseLocation] = set()

        # Get environment variables with fallbacks
        local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
        app_data = Path(os.environ.get("APPDATA", ""))

        # Classic Teams 1.x
        classic_path = (
            app_data / "Microsoft" / "Teams" / "IndexedDB" / self.DB_NAME_PATTERN
        )
        if classic_path.exists():
            locations.add(
                DatabaseLocation(
                    path=classic_path,
                    source="Teams Classic 1.x",
                    platform="Windows",
                    priority=2,
                )
            )

        # New Teams 2.x - Earlier variant (2023/2024)
        new_teams_early = (
            local_app_data
            / "Packages"
            / "MicrosoftTeams_8wekyb3d8bbwe"
            / "LocalCache"
            / "Microsoft"
            / "MSTeams"
            / "EBWebView"
            / "Default"
            / "IndexedDB"
            / self.DB_NAME_PATTERN
        )
        if new_teams_early.exists():
            locations.add(
                DatabaseLocation(
                    path=new_teams_early,
                    source="Teams 2.x (Early)",
                    platform="Windows",
                    priority=3,
                )
            )

        # New Teams 2.x - Current variant (2025/2026)
        new_teams_current = (
            local_app_data
            / "Packages"
            / "MSTeams_8wekyb3d8bbwe"
            / "LocalCache"
            / "Microsoft"
            / "MSTeams"
            / "EBWebView"
            / "WV2Profile_tfw"
            / "IndexedDB"
            / self.DB_NAME_PATTERN
        )
        if new_teams_current.exists():
            locations.add(
                DatabaseLocation(
                    path=new_teams_current,
                    source="Teams 2.x (Current)",
                    platform="Windows",
                    priority=1,
                )
            )

        return locations

    def _discover_macos(self) -> Set[DatabaseLocation]:
        """Discover Teams databases on macOS."""
        locations: Set[DatabaseLocation] = set()

        home = Path.home()

        # Classic Teams 1.x / New Teams 2.x Classic path
        classic_path = (
            home
            / "Library"
            / "Application Support"
            / "Microsoft"
            / "Teams"
            / "IndexedDB"
            / self.DB_NAME_PATTERN
        )
        if classic_path.exists():
            locations.add(
                DatabaseLocation(
                    path=classic_path,
                    source="Teams Classic",
                    platform="macOS",
                    priority=1,
                )
            )

        # New Teams 2.x - Containerized (work/school app)
        container_paths = [
            home
            / "Library"
            / "Containers"
            / "com.microsoft.teams2"
            / "Data"
            / "Library"
            / "Application Support"
            / "Microsoft"
            / "Teams"
            / "IndexedDB"
            / self.DB_NAME_PATTERN,
            home
            / "Library"
            / "Group Containers"
            / "UBF8T346G9.com.microsoft.teams"
            / "Library"
            / "Application Support"
            / "Microsoft"
            / "Teams"
            / "IndexedDB"
            / self.DB_NAME_PATTERN,
        ]

        for idx, path in enumerate(container_paths):
            if path.exists():
                locations.add(
                    DatabaseLocation(
                        path=path,
                        source=f"Teams 2.x Container ({idx + 1})",
                        platform="macOS",
                        priority=2 + idx,
                    )
                )

        return locations

    def _discover_linux(self) -> Set[DatabaseLocation]:
        """Discover Teams databases on Linux."""
        locations: Set[DatabaseLocation] = set()

        home = Path.home()

        # Native Classic Teams
        native_path = (
            home
            / ".config"
            / "Microsoft"
            / "Microsoft Teams"
            / "IndexedDB"
            / self.DB_NAME_PATTERN
        )
        if native_path.exists():
            locations.add(
                DatabaseLocation(
                    path=native_path,
                    source="Teams Native Classic",
                    platform="Linux",
                    priority=1,
                )
            )

        # teams-for-linux (Snap installation)
        snap_path = (
            home
            / "snap"
            / "teams-for-linux"
            / "current"
            / ".config"
            / "teams-for-linux"
            / self.DB_NAME_PATTERN
        )
        if snap_path.exists():
            locations.add(
                DatabaseLocation(
                    path=snap_path,
                    source="teams-for-linux (Snap)",
                    platform="Linux",
                    priority=2,
                )
            )

        # Alternative teams-for-linux location
        snap_path_alt = (
            home
            / "snap"
            / "teams-for-linux"
            / "current"
            / ".config"
            / "teams-for-linux"
            / "https_teams.live.com_0.indexeddb.leveldb"
        )
        if snap_path_alt.exists():
            locations.add(
                DatabaseLocation(
                    path=snap_path_alt,
                    source="teams-for-linux Live (Snap)",
                    platform="Linux",
                    priority=3,
                )
            )

        return locations

    def _discover_browsers(self) -> Set[DatabaseLocation]:
        """Discover browser-based Teams databases."""
        locations: Set[DatabaseLocation] = set()

        home = Path.home()

        if self._system == "Windows":
            local_app_data = Path(os.environ.get("LOCALAPPDATA", ""))
            app_data = Path(os.environ.get("APPDATA", ""))

            # Chrome/Chromium
            chrome_path = (
                local_app_data
                / "Google"
                / "Chrome"
                / "User Data"
                / "Default"
                / "Storage"
                / "leveldb"
            )
            if chrome_path.exists():
                locations.add(
                    DatabaseLocation(
                        path=chrome_path,
                        source="Chrome (Browser)",
                        platform="Windows",
                        priority=10,
                    )
                )

            # Microsoft Edge
            edge_path = (
                local_app_data
                / "Microsoft"
                / "Edge"
                / "User Data"
                / "Default"
                / "Storage"
                / "leveldb"
            )
            if edge_path.exists():
                locations.add(
                    DatabaseLocation(
                        path=edge_path,
                        source="Edge (Browser)",
                        platform="Windows",
                        priority=10,
                    )
                )

            # Firefox - needs profile detection
            firefox_profiles = app_data / "Mozilla" / "Firefox" / "Profiles"
            if firefox_profiles.exists():
                for profile_dir in firefox_profiles.iterdir():
                    if profile_dir.is_dir():
                        teams_storage = (
                            profile_dir
                            / "storage"
                            / "default"
                            / "https+++teams.microsoft.com"
                            / "idb"
                        )
                        if teams_storage.exists():
                            locations.add(
                                DatabaseLocation(
                                    path=teams_storage,
                                    source=f"Firefox - {profile_dir.name}",
                                    platform="Windows",
                                    priority=11,
                                )
                            )

        elif self._system == "Darwin":
            # Chrome/Chromium
            chrome_path = (
                home
                / "Library"
                / "Application Support"
                / "Google"
                / "Chrome"
                / "Default"
                / "Storage"
                / "leveldb"
            )
            if chrome_path.exists():
                locations.add(
                    DatabaseLocation(
                        path=chrome_path,
                        source="Chrome (Browser)",
                        platform="macOS",
                        priority=10,
                    )
                )

            # Microsoft Edge
            edge_path = (
                home
                / "Library"
                / "Application Support"
                / "Microsoft Edge"
                / "Default"
                / "Storage"
                / "leveldb"
            )
            if edge_path.exists():
                locations.add(
                    DatabaseLocation(
                        path=edge_path,
                        source="Edge (Browser)",
                        platform="macOS",
                        priority=10,
                    )
                )

        elif self._system == "Linux":
            # Chrome/Chromium
            chrome_path = (
                home / ".config" / "google-chrome" / "Default" / "Storage" / "leveldb"
            )
            if chrome_path.exists():
                locations.add(
                    DatabaseLocation(
                        path=chrome_path,
                        source="Chrome (Browser)",
                        platform="Linux",
                        priority=10,
                    )
                )

        return locations

    def validate_location(self, location: DatabaseLocation) -> bool:
        """Validate that a database location is accessible and valid.

        Args:
            location: The DatabaseLocation to validate

        Returns:
            True if the location is valid and accessible
        """
        path = location.path

        # Check if path exists
        if not path.exists():
            return False

        # Check if it's a directory (LevelDB is a directory-based database)
        if not path.is_dir():
            return False

        # Check for required LevelDB files
        required_files = ["CURRENT", "MANIFEST-"]
        has_manifest = False

        try:
            for item in path.iterdir():
                if item.name == "CURRENT":
                    return True
                if item.name.startswith("MANIFEST-"):
                    has_manifest = True
        except (PermissionError, OSError):
            return False

        return has_manifest
