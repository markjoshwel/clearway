import os
from pathlib import Path
from datetime import datetime
from teams_bridge import TeamsExtractor

def list_unread():
    app_data = os.environ.get("LOCALAPPDATA", "")
    db_path = Path(app_data) / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb"

    print(f"Checking for unread Teams messages...\n")
    
    try:
        with TeamsExtractor(db_path) as extractor:
            conversations = extractor.get_conversations()
            
            unread_found = False
            for conv in conversations:
                if conv.unread_count > 0:
                    unread_found = True
                    print(f"--- {conv.title} ({conv.unread_count} unread) ---")
                    
                    # Filter and show only unread messages
                    unread_msgs = [m for m in conv.messages if m.is_unread]
                    for msg in unread_msgs:
                        ts_str = msg.timestamp.strftime('%Y-%m-%d %H:%M')
                        print(f"  [{ts_str}] {msg.sender_name}: {msg.content}")
                    print()
            
            if not unread_found:
                print("No unread messages found.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_unread()
