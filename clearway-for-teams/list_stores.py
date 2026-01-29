import os
import shutil
import tempfile
import sys
from pathlib import Path
from ccl_chromium_reader import ccl_chromium_indexeddb # type: ignore

def copy_db_to_temp(db_path: Path) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="teams_db_copy_"))
    target_path = temp_dir / db_path.name
    print(f"Copying {db_path} to {target_path}...", flush=True)
    shutil.copytree(db_path, target_path, ignore=shutil.ignore_patterns("LOCK"))
    return target_path

def sniff(db_path: Path):
    if not db_path.exists():
        print(f"Path does not exist: {db_path}", flush=True)
        return

    temp_path = None
    try:
        temp_path = copy_db_to_temp(db_path)
        print(f"Opening IndexedDB at {temp_path}...", flush=True)
        
        print("Parsing with ccl_chromium_indexeddb (this may take a minute)...", flush=True)
        db = ccl_chromium_indexeddb.IndexedDb(temp_path)
        
        if not db.global_metadata or not db.global_metadata.db_ids:
            print("No databases found in global metadata.", flush=True)
            return

        print(f"Success! Found {len(db.global_metadata.db_ids)} databases.", flush=True)
        
        for db_id in db.global_metadata.db_ids:
            print(f"\nDB: {db_id.name} (Origin: {db_id.origin}, ID: {db_id.dbid_no})", flush=True)
            
            # The object stores are also stored in metadata
            # We can use db.get_object_store_metadata
            # But we need to know how many stores there are.
            # Usually we can get the Max Object Store ID from database metadata.
            try:
                max_store_id = db.get_database_metadata(db_id.dbid_no, ccl_chromium_indexeddb.DatabaseMetadataType.MaximumObjectStoreId)
                print(f"  Max Store ID: {max_store_id}", flush=True)
                
                for store_id in range(1, (max_store_id or 0) + 1):
                    try:
                        store_name = db.get_object_store_metadata(db_id.dbid_no, store_id, ccl_chromium_indexeddb.ObjectStoreMetadataType.StoreName)
                        if store_name:
                            print(f"  Store: {store_name} (ID: {store_id})", flush=True)
                            
                            # Try to iterate a few records to confirm content
                            count = 0
                            for record in db.iterate_records(db_id.dbid_no, store_id):
                                count += 1
                                if count <= 1:
                                    print(f"    Sample Key: {record.key}")
                                    # Value might be large/complex, show type or start
                                    val_repr = str(record.value)
                                    if len(val_repr) > 200:
                                        val_repr = val_repr[:200] + "..."
                                    print(f"    Sample Val: {val_repr}")
                                
                                # Heuristic match for messages
                                if count == 1 and ("reply" in store_name.lower() or "message" in store_name.lower()):
                                    print("    [!] Potential message store found.")
                                
                            print(f"    Total records: {count}", flush=True)
                    except Exception as e:
                        # Some IDs might not exist
                        pass
            except Exception as e:
                print(f"  Error getting DB metadata: {e}", flush=True)
                
    except Exception as e:
        print(f"Error sniffing {db_path.name}: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        if temp_path and temp_path.exists():
            shutil.rmtree(temp_path.parent, ignore_errors=True)

if __name__ == "__main__":
    app_data = os.environ.get("LOCALAPPDATA", "")
    paths = [
        Path(app_data) / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb",
    ]
    
    for p in paths:
        print(f"\n--- Sniffing {p} ---", flush=True)
        sniff(p)
