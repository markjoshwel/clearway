import os
import sys
import time
import json
import imaplib
import email
import email.utils
from email.header import decode_header
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Any, Callable
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import urllib.request
import urllib.error

load_dotenv()

# Fix Windows console encoding for Unicode
if sys.platform == "win32":
    import io

    # TextIOWrapper requires a binary buffer
    stdout_buffer: Any = sys.stdout.buffer
    sys.stdout = io.TextIOWrapper(stdout_buffer, encoding="utf-8")

# --- Data Models ---


@dataclass
class UserProfile:
    id: str  # Email address
    display_name: str


@dataclass
class Message:
    id: str
    sender_id: str
    sender_name: str
    content: str
    timestamp: datetime
    conversation_id: str
    is_unread: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "sender_id": self.sender_id,
            "sender_name": self.sender_name,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "conversation_id": self.conversation_id,
            "is_unread": self.is_unread,
        }


@dataclass
class Conversation:
    id: str
    title: str
    last_message_time: datetime
    messages: list[Message]
    unread_count: int = 0
    thread_type: str = "Email"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "last_message_time": self.last_message_time.isoformat(),
            "messages": [m.to_dict() for m in self.messages],
            "unread_count": self.unread_count,
            "thread_type": self.thread_type,
        }


# --- Notification Hook ---


class NotificationHook:
    """Webhook notifier for new ProtonMail messages."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.environ.get("PROTONMAIL_WEBHOOK_URL", "")
        self._last_notified_ids: set[str] = set()

    def load_state(self) -> None:
        """Load last notified message IDs from state file."""
        state_file = Path(".protonmail_state.json")
        if state_file.exists():
            try:
                with open(state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._last_notified_ids = set(data.get("notified_ids", []))
            except (json.JSONDecodeError, IOError):
                pass

    def save_state(self) -> None:
        """Save last notified message IDs to state file."""
        state_file = Path(".protonmail_state.json")
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump({"notified_ids": list(self._last_notified_ids)}, f, indent=2)
        except IOError:
            pass

    def notify(self, conversation: Conversation) -> bool:
        """Send notification for a new conversation. Returns True if successful."""
        if not self.webhook_url:
            print(
                f"[NOTIFY] New email: {conversation.title} from {conversation.messages[0].sender_name}"
            )
            return True

        # Track that we've notified about this message
        message_id = conversation.messages[0].id
        if message_id in self._last_notified_ids:
            return True  # Already notified

        payload = {
            "event": "new_email",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "conversation": conversation.to_dict(),
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    self._last_notified_ids.add(message_id)
                    self.save_state()
                    return True
        except urllib.error.URLError as e:
            print(f"[ERROR] Failed to send webhook: {e}")
        except Exception as e:
            print(f"[ERROR] Unexpected error sending webhook: {e}")

        return False

    def is_new_message(self, message_id: str) -> bool:
        """Check if a message is new (not previously notified)."""
        return message_id not in self._last_notified_ids

    def mark_notified(self, message_id: str) -> None:
        """Mark a message as notified."""
        self._last_notified_ids.add(message_id)
        self.save_state()


# --- Extractor Class ---


class ProtonmailExtractor:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 1143,
        user: str = "",
        password: str = "",
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.imap: Optional[imaplib.IMAP4] = None

    def __enter__(self) -> "ProtonmailExtractor":
        self.imap = imaplib.IMAP4(self.host, self.port)
        self.imap.login(self.user, self.password)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.imap:
            self.imap.logout()

    def _decode_mime_header(self, header: str) -> str:
        decoded: list[tuple[bytes | str, Optional[str]]] = decode_header(header)
        parts: list[str] = []
        for content, encoding in decoded:
            if isinstance(content, bytes):
                parts.append(content.decode(encoding or "utf-8", errors="replace"))
            else:
                parts.append(content)
        return "".join(parts)

    def _parse_message(
        self, mid_bytes: bytes, raw_email: bytes
    ) -> Optional[Conversation]:
        """Parse a raw email into a Conversation object."""
        mid = mid_bytes.decode()
        msg = email.message_from_bytes(raw_email)

        subject = self._decode_mime_header(str(msg.get("Subject", "No Subject")))
        sender = self._decode_mime_header(str(msg.get("From", "Unknown")))
        date_str = msg.get("Date")

        # Simple timestamp parsing
        ts = datetime.now(timezone.utc)
        if date_str:
            try:
                ts = email.utils.parsedate_to_datetime(str(date_str))
            except (ValueError, TypeError):
                pass

        # Check if unread (SEEN flag)
        is_unread = True
        if self.imap:
            res_flags, flags_data = self.imap.fetch(mid, "(FLAGS)")
            if res_flags == "OK" and flags_data:
                first_flags = flags_data[0]
                if isinstance(first_flags, bytes):
                    is_unread = b"\\Seen" not in first_flags
                elif isinstance(first_flags, tuple) and len(first_flags) > 0:
                    flags_str = str(first_flags[0])
                    is_unread = "\\Seen" not in flags_str

        # Get message content
        content = ""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if isinstance(payload, bytes):
                            content = payload.decode("utf-8", errors="replace")
                        else:
                            content = str(payload)
                        break
                    except (AttributeError, UnicodeDecodeError, TypeError):
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if isinstance(payload, bytes):
                    content = payload.decode("utf-8", errors="replace")
                else:
                    content = str(payload) if payload else ""
            except (AttributeError, UnicodeDecodeError, TypeError):
                content = str(msg.get_payload())

        return Conversation(
            id=mid,
            title=subject,
            last_message_time=ts,
            messages=[
                Message(
                    id=mid,
                    sender_id=sender,
                    sender_name=sender,
                    content=content[:500],
                    timestamp=ts,
                    conversation_id=mid,
                    is_unread=is_unread,
                )
            ],
            unread_count=1 if is_unread else 0,
        )

    def get_conversations(self, limit: int = 20) -> list[Conversation]:
        if not self.imap:
            return []

        self.imap.select("INBOX")
        # Search for all messages to build conversation view
        status, messages = self.imap.search(None, "ALL")
        if status != "OK":
            return []

        msg_ids = messages[0].split()
        # Take the last 'limit' messages
        recent_ids = msg_ids[-limit:]
        recent_ids.reverse()

        conversations: list[Conversation] = []

        for mid_bytes in recent_ids:
            res, data = self.imap.fetch(mid_bytes, "(RFC822)")
            if res != "OK" or not data:
                continue

            first_part = data[0]
            if not isinstance(first_part, tuple) or len(first_part) < 2:
                continue

            raw_email: bytes = first_part[1]
            conv = self._parse_message(mid_bytes, raw_email)
            if conv:
                conversations.append(conv)

        return sorted(conversations, key=lambda x: x.last_message_time, reverse=True)

    def get_unread_conversations(self, limit: int = 20) -> list[Conversation]:
        """Get only unread conversations."""
        all_conversations = self.get_conversations(limit)
        return [c for c in all_conversations if c.unread_count > 0]

    def get_recent_communications(
        self, since: Optional[datetime] = None, limit: int = 20
    ) -> list[Conversation]:
        """Get conversations since a specific time (default: last 24 hours)."""
        if since is None:
            since = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        all_conversations = self.get_conversations(limit * 2)  # Get more to filter
        recent = [c for c in all_conversations if c.last_message_time >= since]
        return recent[:limit]


# --- Monitor Service ---


class ProtonmailMonitor:
    """Monitors ProtonMail for new messages and triggers notifications."""

    def __init__(
        self,
        extractor: ProtonmailExtractor,
        hook: NotificationHook,
        check_interval: int = 60,
    ):
        self.extractor = extractor
        self.hook = hook
        self.check_interval = check_interval
        self._running = False
        self._on_notification: Optional[Callable[[Conversation], None]] = None

    def on_notification(self, callback: Callable[[Conversation], None]) -> None:
        """Register a callback for new notifications."""
        self._on_notification = callback

    def _check_and_notify(self) -> None:
        """Check for new unread messages and send notifications."""
        try:
            with self.extractor:
                unread = self.extractor.get_unread_conversations()

                for conv in unread:
                    message_id = conv.messages[0].id

                    if self.hook.is_new_message(message_id):
                        # Send notification
                        success = self.hook.notify(conv)

                        if success:
                            self.hook.mark_notified(message_id)

                            # Call optional callback
                            if self._on_notification:
                                self._on_notification(conv)

                        print(
                            f"[NEW EMAIL] {conv.title} from {conv.messages[0].sender_name}"
                        )

        except Exception as e:
            print(f"[ERROR] Monitor check failed: {e}")

    def start(self) -> None:
        """Start monitoring loop (runs indefinitely)."""
        self._running = True
        self.hook.load_state()

        print(
            f"[MONITOR] Starting ProtonMail monitor (checking every {self.check_interval}s)..."
        )
        print(f"[MONITOR] Press Ctrl+C to stop")

        try:
            while self._running:
                self._check_and_notify()
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            print("\n[MONITOR] Stopping...")
            self._running = False

    def stop(self) -> None:
        """Stop the monitoring loop."""
        self._running = False

    def check_once(self) -> list[Conversation]:
        """Check once for new messages and return them."""
        self.hook.load_state()
        new_messages: list[Conversation] = []

        try:
            with self.extractor:
                unread = self.extractor.get_unread_conversations()

                for conv in unread:
                    message_id = conv.messages[0].id

                    if self.hook.is_new_message(message_id):
                        success = self.hook.notify(conv)
                        if success:
                            self.hook.mark_notified(message_id)
                            new_messages.append(conv)

            return new_messages

        except Exception as e:
            print(f"[ERROR] Check failed: {e}")
            return []


# --- Execution ---


def print_help() -> None:
    """Print usage information."""
    print("Usage: python protonmail_bridge.py <command>")
    print()
    print("Commands:")
    print("  get-conversation-list               List recent emails")
    print("  get-unread-conversation-list        List only unread emails")
    print("  get-recent-conversation-communications [hours]")
    print(
        "                                      List emails from last N hours (default: 24)"
    )
    print(
        "  notify-hook-of-new-communication    Check once and notify about new messages"
    )
    print("  monitor                             Continuously monitor for new messages")
    print()
    print("Environment variables:")
    print("  PROTONMAIL_USER        Bridge username from hydroxide")
    print("  PROTONMAIL_PASSWORD    Bridge password from hydroxide")
    print("  PROTONMAIL_WEBHOOK_URL Optional webhook URL for notifications")


def main() -> None:
    host = os.environ.get("PROTONMAIL_IMAP_HOST", "127.0.0.1")
    port = int(os.environ.get("PROTONMAIL_IMAP_PORT", "1143"))
    user = os.environ.get("PROTONMAIL_USER", "")
    password = os.environ.get("PROTONMAIL_PASSWORD", "")
    webhook_url = os.environ.get("PROTONMAIL_WEBHOOK_URL", "")

    if not user or not password:
        print(
            "Error: PROTONMAIL_USER and PROTONMAIL_PASSWORD environment variables must be set."
        )
        print("Note: These are the credentials provided by hydroxide.")
        return

    # Check command line args
    if len(sys.argv) == 1 or sys.argv[1] in ("--help", "-h", "help"):
        print_help()
        return

    command = sys.argv[1]

    if command == "monitor":
        # Run in monitor mode
        extractor = ProtonmailExtractor(host, port, user, password)
        hook = NotificationHook(webhook_url)
        monitor = ProtonmailMonitor(extractor, hook, check_interval=60)
        monitor.start()

    elif command == "get-conversation-list":
        # List recent emails (Component 1)
        print(f"Initializing Protonmail Message Bridge (via hydroxide IMAP)...")
        try:
            with ProtonmailExtractor(host, port, user, password) as extractor:
                conversations = extractor.get_conversations()

                print(f"\nFound {len(conversations)} recent emails.\n")
                print("=" * 60)

                for conv in conversations:
                    status = " (UNREAD)" if conv.unread_count > 0 else ""
                    print(f"EMAIL: {conv.title}{status}")
                    print(f"From: {conv.messages[0].sender_name}")
                    print(f"Date: {conv.last_message_time}")
                    print("-" * 30)
                    print(f"Snippet: {conv.messages[0].content[:200]}...")
                    print("=" * 60)

        except Exception as e:
            print(f"Fatal error: {e}")
            import traceback

            traceback.print_exc()

    elif command == "get-unread-conversation-list":
        # List unread emails only (Component 2)
        print(f"Fetching unread conversation list...")
        try:
            with ProtonmailExtractor(host, port, user, password) as extractor:
                conversations = extractor.get_unread_conversations()

                print(f"\nFound {len(conversations)} unread emails.\n")
                print("=" * 60)

                for conv in conversations:
                    print(f"EMAIL: {conv.title}")
                    print(f"From: {conv.messages[0].sender_name}")
                    print(f"Date: {conv.last_message_time}")
                    print("-" * 30)
                    print(f"Snippet: {conv.messages[0].content[:200]}...")
                    print("=" * 60)
        except Exception as e:
            print(f"Fatal error: {e}")
            import traceback

            traceback.print_exc()

    elif command == "get-recent-conversation-communications":
        # List recent communications (Component 3)
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        print(f"Fetching recent communications from last {hours} hours...")
        try:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            with ProtonmailExtractor(host, port, user, password) as extractor:
                conversations = extractor.get_recent_communications(since=since)

                print(f"\nFound {len(conversations)} emails from last {hours} hours.\n")
                print("=" * 60)

                for conv in conversations:
                    status = " (UNREAD)" if conv.unread_count > 0 else ""
                    print(f"EMAIL: {conv.title}{status}")
                    print(f"From: {conv.messages[0].sender_name}")
                    print(f"Date: {conv.last_message_time}")
                    print("-" * 30)
                    print(f"Snippet: {conv.messages[0].content[:200]}...")
                    print("=" * 60)
        except Exception as e:
            print(f"Fatal error: {e}")
            import traceback

            traceback.print_exc()

    elif command == "notify-hook-of-new-communication":
        # Check once and notify about new emails (Component 4)
        print(f"Checking for new communications to notify about...")
        extractor = ProtonmailExtractor(host, port, user, password)
        hook = NotificationHook(webhook_url)
        monitor = ProtonmailMonitor(extractor, hook)

        new_messages = monitor.check_once()
        if new_messages:
            print(f"\nNotified about {len(new_messages)} new message(s)")
        else:
            print("\nNo new messages to notify about")

    else:
        print(f"Unknown command: {command}")
        print_help()


if __name__ == "__main__":
    main()
