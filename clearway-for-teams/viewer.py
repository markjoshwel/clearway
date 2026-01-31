"""Interactive TUI viewer for Microsoft Teams conversations.

This application provides a rich terminal interface for browsing
Teams conversations with features like:
- Search/filter conversations
- Unread message highlighting
- Keyboard navigation
- Conversation type indicators
- Timestamps and sender information
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.reactive import reactive
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Static,
)

from libteamsdb import (
    Conversation,
    DatabaseLocation,
    DatabaseNotFoundError,
    ExtractionError,
    Message,
    TeamsDatabaseDiscovery,
    TeamsDatabaseExtractor,
    ThreadType,
)


class ConversationItem(ListItem):
    """A widget to display a conversation in the list."""

    def __init__(self, conversation: Conversation) -> None:
        super().__init__()
        self.conversation = conversation

    def compose(self) -> ComposeResult:
        conv = self.conversation

        # Type indicator
        if conv.thread_type == ThreadType.TOPIC:
            prefix = "[C]"
            type_color = "cyan"
        elif conv.thread_type == ThreadType.MEETING:
            prefix = "[M]"
            type_color = "yellow"
        else:
            prefix = "[P]"
            type_color = "green"

        # Build display text
        title = conv.title or "Unknown"
        if conv.hidden:
            title = f"[dim]{title}[/]"

        # Unread indicator
        if conv.unread_count > 0:
            display = f"[{type_color}]{prefix}[/{type_color}] {title} [bold red]({conv.unread_count})[/]"
        else:
            display = f"[{type_color}]{prefix}[/{type_color}] {title}"

        # Truncate if too long
        if len(display) > 40:
            display = display[:37] + "..."

        yield Label(display)


class MessageItem(Static):
    """A widget to display a single message."""

    def __init__(self, message: Message) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        msg = self.message

        # Format timestamp
        ts_str = msg.timestamp.strftime("%Y-%m-%d %H:%M")

        # Unread indicator
        if msg.is_unread:
            prefix = "[red]●[/] "
        else:
            prefix = "  "

        # Header line with timestamp and sender
        header = f"{prefix}[dim]{ts_str}[/] [bold]{msg.sender_name}[/]"
        yield Label(header)

        # Message content with wrapping
        content = msg.content if msg.content else "[dim](no content)[/]"
        yield Static(content, classes="content")


class TeamsViewer(App[None]):
    """A TUI viewer for Microsoft Teams conversations."""

    CSS = """
    Screen {
        background: #1a1a1a;
    }
    
    #sidebar {
        width: 45;
        background: #252526;
        border-right: solid #3c3c3c;
    }
    
    #search-box {
        height: 3;
        background: #2d2d2d;
        border-bottom: solid #3c3c3c;
        padding: 0 1;
    }
    
    #conv-list {
        height: 1fr;
        background: #252526;
        border: none;
    }
    
    ListItem {
        padding: 0 1;
        height: auto;
    }
    
    ListItem > Label {
        width: 100%;
        height: auto;
        padding: 1 0;
    }
    
    ListItem:focus {
        background: #094771;
    }
    
    ListItem:hover {
        background: #2a2d2e;
    }
    
    #message-view {
        background: #1a1a1a;
    }
    
    #conv-header {
        background: #094771;
        color: white;
        height: 3;
        padding: 1;
        text-align: center;
        text-style: bold;
        border-bottom: solid #3c3c3c;
    }
    
    #messages {
        background: #1a1a1a;
        padding: 1;
    }
    
    MessageItem {
        padding: 1;
        margin-bottom: 1;
        background: #252526;
        border-left: solid #094771;
    }
    
    MessageItem:focus-within {
        background: #2a2d2e;
    }
    
    MessageItem .content {
        margin-left: 2;
        color: #cccccc;
        text-style: none;
    }
    
    #status-bar {
        height: 1;
        background: #007acc;
        color: white;
        padding: 0 1;
    }
    
    #empty-state {
        align: center middle;
        text-align: center;
        color: #666;
    }
    
    .info {
        color: #666;
        text-style: italic;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("r", "refresh", "Refresh"),
        Binding("/", "focus_search", "Search"),
        Binding("j", "next_conv", "Next"),
        Binding("k", "prev_conv", "Previous"),
        Binding("g", "first_conv", "First"),
        Binding("G", "last_conv", "Last"),
        Binding("u", "show_unread", "Unread Only"),
        Binding("a", "show_all", "Show All"),
    ]

    # Reactive state
    all_conversations: reactive[List[Conversation]] = reactive([])
    filtered_conversations: reactive[List[Conversation]] = reactive([])
    current_filter: reactive[str] = reactive("")
    show_unread_only: reactive[bool] = reactive(False)
    db_location: Optional[DatabaseLocation] = None

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__()
        self._specified_db_path = db_path

    def compose(self) -> ComposeResult:
        """Compose the UI layout."""
        yield Header(show_clock=True)

        with Horizontal():
            # Sidebar with search and conversation list
            with Vertical(id="sidebar"):
                yield Input(
                    placeholder="Search conversations...",
                    id="search-box",
                )
                yield ListView(id="conv-list")

            # Message view area
            with Vertical(id="message-view"):
                yield Label("Select a conversation", id="conv-header")
                with VerticalScroll(id="messages"):
                    yield Label(
                        "Loading conversations...",
                        id="empty-state",
                    )

        yield Label("Ready", id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        """Initialize data when app mounts."""
        self.action_refresh()

    def watch_current_filter(self, filter_text: str) -> None:
        """React to filter changes."""
        self._apply_filter()

    def watch_show_unread_only(self, show_unread: bool) -> None:
        """React to unread filter changes."""
        self._apply_filter()

    def _apply_filter(self) -> None:
        """Apply current filters to conversation list."""
        conversations = self.all_conversations

        # Apply text filter
        if self.current_filter:
            filter_lower = self.current_filter.lower()
            conversations = [
                c for c in conversations if filter_lower in c.title.lower()
            ]

        # Apply unread filter
        if self.show_unread_only:
            conversations = [c for c in conversations if c.unread_count > 0]

        self.filtered_conversations = conversations
        self._update_conversation_list()

    def _update_conversation_list(self) -> None:
        """Update the conversation list view."""
        conv_list = self.query_one("#conv-list", ListView)
        conv_list.clear()

        for conv in self.filtered_conversations:
            conv_list.append(ConversationItem(conv))

        # Update status
        total = len(self.all_conversations)
        filtered = len(self.filtered_conversations)
        status_text = f"Showing {filtered} of {total} conversations"

        if self.current_filter:
            status_text += f' (filter: "{self.current_filter}")'
        if self.show_unread_only:
            status_text += " [unread only]"

        self.query_one("#status-bar", Label).update(status_text)

        # Select first item if available
        if self.filtered_conversations and conv_list.children:
            conv_list.index = 0
            self._show_conversation(self.filtered_conversations[0])

    def _show_conversation(self, conv: Conversation) -> None:
        """Display a conversation's messages."""
        # Update header
        header = self.query_one("#conv-header", Label)
        header.update(f"{conv.title} ({len(conv.messages)} messages)")

        # Update messages
        msg_container = self.query_one("#messages", VerticalScroll)
        msg_container.remove_children()

        if not conv.messages:
            msg_container.mount(
                Label(
                    "No messages saved locally for this conversation.",
                    classes="info",
                )
            )
        else:
            for msg in conv.messages:
                msg_container.mount(MessageItem(msg))

        msg_container.scroll_end(animate=False)

    def action_refresh(self) -> None:
        """Refresh data from the database."""
        self.notify("Refreshing data...")

        try:
            # Get database path
            if self._specified_db_path:
                db_path = self._specified_db_path
            else:
                discovery = TeamsDatabaseDiscovery()
                self.db_location = discovery.find_first()
                db_path = self.db_location.path

            # Extract data
            with TeamsDatabaseExtractor(db_path) as extractor:
                self.all_conversations = extractor.get_conversations()

            self._apply_filter()

            source = self.db_location.source if self.db_location else "specified"
            self.notify(
                f"Loaded {len(self.all_conversations)} conversations from {source}"
            )

        except DatabaseNotFoundError as e:
            self.notify(f"Database not found: {e}", severity="error")
        except ExtractionError as e:
            self.notify(f"Error reading database: {e}", severity="error")
        except Exception as e:
            self.notify(f"Unexpected error: {e}", severity="error")

    def action_focus_search(self) -> None:
        """Focus the search input."""
        self.query_one("#search-box", Input).focus()

    def action_next_conv(self) -> None:
        """Select next conversation."""
        conv_list = self.query_one("#conv-list", ListView)
        if conv_list.index is not None:
            conv_list.index = min(
                conv_list.index + 1,
                len(self.filtered_conversations) - 1,
            )

    def action_prev_conv(self) -> None:
        """Select previous conversation."""
        conv_list = self.query_one("#conv-list", ListView)
        if conv_list.index is not None:
            conv_list.index = max(conv_list.index - 1, 0)

    def action_first_conv(self) -> None:
        """Select first conversation."""
        if self.filtered_conversations:
            self.query_one("#conv-list", ListView).index = 0

    def action_last_conv(self) -> None:
        """Select last conversation."""
        if self.filtered_conversations:
            self.query_one("#conv-list", ListView).index = (
                len(self.filtered_conversations) - 1
            )

    def action_show_unread(self) -> None:
        """Toggle showing only unread conversations."""
        self.show_unread_only = True
        self.notify("Showing only unread conversations")

    def action_show_all(self) -> None:
        """Show all conversations."""
        self.show_unread_only = False
        self.notify("Showing all conversations")

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle search input changes."""
        if event.input.id == "search-box":
            self.current_filter = event.value

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Handle conversation selection."""
        if event.list_view.id == "conv-list":
            index = event.list_view.index
            if index is not None and index < len(self.filtered_conversations):
                self._show_conversation(self.filtered_conversations[index])


def main() -> None:
    """Run the Teams viewer application."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Interactive Teams conversation viewer"
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Path to Teams database (auto-discovered if not specified)",
    )

    args = parser.parse_args()

    app = TeamsViewer(db_path=args.db_path)
    app.run()


if __name__ == "__main__":
    main()
