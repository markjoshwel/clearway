from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListItem, ListView, Static, Label
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual.widgets import OptionList
from textual.widgets.option_list import Option
from datetime import datetime
from pathlib import Path
import os
from typing import List

from teams_bridge import TeamsExtractor, Conversation, Message

class MessageItem(Static):
    """A widget to display a single message."""
    def __init__(self, message: Message):
        super().__init__()
        self.msg = message

    def compose(self) -> ComposeResult:
        yield Label(f"[{self.msg.timestamp.strftime('%H:%M')}] [bold]{self.msg.sender_name}[/]:")
        yield Static(self.msg.content, classes="content")

class TeamsViewer(App):
    """A TUI viewer for Microsoft Teams conversations."""

    CSS = """
    Screen {
        background: #1e1e1e;
    }

    #sidebar {
        width: 35;
        background: #252526;
        border-right: solid #333;
    }

    #message-view {
        background: #1e1e1e;
    }

    ListItem {
        padding: 1;
    }

    ListItem > Label {
        width: 100%;
    }

    MessageItem {
        padding: 0 1;
        margin-bottom: 1;
        background: #2d2d2d;
    }

    MessageItem .content {
        padding-left: 2;
        color: #cccccc;
    }

    #conv-header {
        background: $accent;
        color: white;
        padding: 1;
        text-align: center;
        text-style: bold;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh Data"),
    ]

    def __init__(self):
        super().__init__()
        self.conversations: List[Conversation] = []
        self.app_data = os.environ.get("LOCALAPPDATA", "")
        self.db_path = Path(self.app_data) / "Packages/MSTeams_8wekyb3d8bbwe/LocalCache/Microsoft/MSTeams/EBWebView/WV2Profile_tfw/IndexedDB/https_teams.microsoft.com_0.indexeddb.leveldb"

    def compose(self) -> ComposeResult:
        from textual.containers import VerticalScroll
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Label("Conversations", id="conv-header")
                yield ListView(id="conv-list")
            with Vertical(id="message-view"):
                yield VerticalScroll(id="messages")
        yield Footer()

    async def on_mount(self) -> None:
        self.action_refresh()

    def action_refresh(self) -> None:
        """Fetch fresh data from Teams DB."""
        self.notify("Refreshing Teams data...")
        try:
            with TeamsExtractor(self.db_path) as extractor:
                self.conversations = extractor.get_conversations()
            
            conv_list = self.query_one("#conv-list", ListView)
            conv_list.clear()
            for conv in self.conversations:
                # Only show conversations with messages OR if they are unread
                if not conv.messages and conv.unread_count == 0:
                    continue
                    
                # Use display name or ID, truncate if needed
                title = conv.title if conv.title else "Unknown"
                if conv.unread_count > 0:
                    title = f"{title} [{conv.unread_count}]"
                    
                if len(title) > 30:
                    title = title[:27] + "..."
                conv_list.append(ListItem(Label(title)))
            
            if self.conversations:
                conv_list.index = 0
                self.show_conversation(self.conversations[0])
                
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and event.list_view.id == "conv-list":
            index = event.list_view.index
            if index is not None and index < len(self.conversations):
                self.show_conversation(self.conversations[index])

    def show_conversation(self, conv: Conversation) -> None:
        """Update the message view for the selected conversation."""
        msg_container = self.query_one("#messages")
        msg_container.remove_children()
        
        if not conv.messages:
            msg_container.mount(Label("No messages saved locally for this conversation.", classes="info"))
        else:
            for msg in conv.messages:
                msg_container.mount(MessageItem(msg))
        
        msg_container.scroll_end(animate=False)

if __name__ == "__main__":
    app = TeamsViewer()
    app.run()
