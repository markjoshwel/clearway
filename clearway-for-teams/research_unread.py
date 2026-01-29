import os
import shutil
import tempfile
import sys
from pathlib import Path
from ccl_chromium_reader import ccl_chromium_indexeddb # type: ignore

def copy_db_to_temp(db_path: Path) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="teams_unread_research_"))
    target_path = temp_dir / db_path.name
    shutil.copytree(db_path, target_path, ignore=shutil.ignore_patterns("LOCK"))
    return target_path

def research_unread(db_path: Path):
    temp_path = copy_db_to_temp(db_path)
    try:
        db = ccl_chromium_indexeddb.IndexedDb(temp_path)
        
        # 1. Check replychainmetadata for consumptionHorizon
        print("\n--- Researching Channel/Chat Metadata (replychainmetadata) ---")
        meta_db_id = None
        for db_id in db.global_metadata.db_ids:
            if "replychain-metadata-manager" in db_id.name:
                meta_db_id = db_id.dbid_no
                break
        
        if meta_db_id:
            for record in db.iterate_records(meta_db_id, 1): # Store 1: replychainmetadata
                val = record.value
                if val:
                    print(f"Conv: {val.get('conversationId')} | ConsumptionHorizon: {val.get('consumptionHorizon')}")
        
        # 2. Check syncstate-manager for unread indicators
        print("\n--- Researching Sync State (syncstates) ---")
        sync_db_id = None
        for db_id in db.global_metadata.db_ids:
            if "syncstate-manager" in db_id.name:
                sync_db_id = db_id.dbid_no
                break
        
        if sync_db_id:
            for record in db.iterate_records(sync_db_id, 1):
                val = record.value
                if val and "unread" in str(val).lower():
                    print(f"Sync Item: {val}")

    finally:
        shutil.rmtree(temp_path.parent, ignore_errors=True)

if __name__ == "__main__":
    app_data = os.environ.get("LOCALAPPDATA", "")
    db_path = Path(app_data) / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb"
    research_unread(db_path)
