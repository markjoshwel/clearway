import os
import shutil
import tempfile
import plyvel # type: ignore
from pathlib import Path
from typing import Generator, Tuple, Optional

# Constants
TEAMS_PACKAGE_NAME = "MSTeams_8wekyb3d8bbwe"
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", "")
TEAMS_ROOT = Path(LOCAL_APP_DATA) / "Packages" / TEAMS_PACKAGE_NAME

def find_teams_databases(root: Path) -> Generator[Path, None, None]:
    """Recursively find LevelDB directories within the Teams package."""
    # Heuristic: Look for directories containing .ldb files
    for path in root.rglob("*.ldb"):
        # The parent of the .ldb file is usually the database directory
        db_dir = path.parent
        # Avoid duplicates
        yield db_dir

def copy_db_to_temp(db_path: Path) -> Path:
    """Copy the database to a temporary directory to avoid locking issues."""
    temp_dir = Path(tempfile.mkdtemp(prefix="teams_db_copy_"))
    # We need to copy the *contents* of db_path into temp_dir/db_name, or just copy db_path to temp_dir/db_name
    target_path = temp_dir / db_path.name
    
    if target_path.exists():
        shutil.rmtree(target_path)
    
    print(f"Copying {db_path} to {target_path}...")
    try:
        shutil.copytree(db_path, target_path)
    except Exception as e:
        print(f"Error copying database: {e}")
        # Try to clean up
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
        
    return target_path

def sniff_db(db_path: Path):
    """Attempt to open and read a few keys from the database."""
    temp_path = None
    db = None
    try:
        temp_path = copy_db_to_temp(db_path)
        
        # Open the database
        print(f"Opening LevelDB at {temp_path}...")
        try:
            db = plyvel.DB(str(temp_path), create_if_missing=False)
        except Exception as e:
            print(f"Failed to open LevelDB: {e}")
            return

        print("Successfully opened DB. Scanning first 20 keys...")
        count = 0
        for key, value in db.iterator():
            print(f"Key: {key!r}")
            # Try to decode value if it looks like text, else hex
            try:
                print(f"Val: {value.decode('utf-8')[:100]}")
            except:
                print(f"Val: <binary len={len(value)}>")
            
            print("-" * 20)
            count += 1
            if count >= 20:
                break
                
        if count == 0:
            print("Database is empty.")

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        if db:
            db.close()
        if temp_path and temp_path.exists():
            print(f"Cleaning up {temp_path}...")
            shutil.rmtree(temp_path.parent, ignore_errors=True)

def main():
    print(f"Searching for Teams databases in {TEAMS_ROOT}...")
    
    seen = set()
    found_any = False
    
    # Prioritize specific known paths if possible, but search all
    for db_path in find_teams_databases(TEAMS_ROOT):
        if db_path in seen:
            continue
        seen.add(db_path)
        
        # Filter out some unlikely candidates if successful (optional optimization)
        if "IndexedDB" not in str(db_path) and "leveldb" not in str(db_path).lower():
            continue
            
        found_any = True
        print(f"\nFound potential DB: {db_path}")
        
        # Prompt user or just try specific ones
        # For now, let's try to sniff it if it looks like the main one
        if "teams.microsoft.com" in str(db_path) or "IndexedDB" in str(db_path):
             sniff_db(db_path)
             
    if not found_any:
        print("No databases found.")

if __name__ == "__main__":
    main()
