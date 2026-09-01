from __future__ import annotations

import json
from dataclasses import dataclass

from aqt import mw
from aqt.qt import QApplication

from .card_context import context_from_card, title_from_card
from .codex_client import CodexErrorKind, CodexResult, RequestKind
from .deck_profiles import deck_references, effective_profile
from .profile_dialog import add_profile_change_listener, show_profile_dialog
from .profiles import DeckProfile
from .request_coordinator import RequestHandle
from .service import get_store
from .ui.codex_runtime import ConnectionState, ConnectionStatus, get_runtime


@dataclass
class ChatSession:
    """One temporary workspace conversation, independent of reviewer navigation."""

    conversation_id: str
    kind: str
    label: str
    context: str
    profile_context: str = ""
    card_id: int | None = None
    deck_id: int | None = None
    pending_message: str | None = None
    pending_message_visible: bool = True
    pending_presentation: str = "message"
    pending_display_text: str | None = None
    request_handle: RequestHandle | None = None
    request_state: str | None = None
    connection_ready: bool = False
    last_connection_result: CodexResult | None = None
    automatic_message: str | None = None
    automatic_action_title: str | None = None
    scroll_top: int = 0
    scroll_following: bool = True


class ReviewerChatController:
    """A persistent, in-memory AI workspace for Anki Reviewer."""

    def __init__(self) -> None:
        self._current_card = None
        self._web = None
        self._open = False
        self._menu_open = False
        self._sessions: dict[str, ChatSession] = {}
        self._selected_conversation_id: str | None = None
        add_profile_change_listener(self._on_profiles_changed)

    def _on_profiles_changed(self) -> None:
        """Refresh deck actions and card shortcuts immediately after profile Save."""

        session = self._card_session(create=False)
        if session is not None:
            profile = self._effective_profile_for_current_card()
            session.profile_context = profile.context if profile else ""
        deck_session = self._deck_session(create=False)
        if deck_session is not None:
            profile = self._effective_profile_for_current_card()
            deck_session.profile_context = profile.context if profile else ""
        self._render()

    def on_card_shown(self, card, web) -> None:
        self._current_card, self._web = card, web
        self._render()

    def bootstrap(self, card) -> dict[str, object]:
        """Return a complete UI snapshot for the incoming reviewer document.

        ``card_will_show`` runs while the outgoing page is still alive. Clearing
        the old webview here prevents asynchronous status updates from painting
        that outgoing page during Anki's card replacement.
        """

        self._current_card, self._web = card, None
        return self._payload()

    def handle(self, card, web, payload: dict[str, object]) -> None:
        if payload.get("action") == "save_scroll":
            self._current_card, self._web = card, web
            self.save_scroll(payload.get("scroll"))
            return
        self.on_card_shown(card, web)
        action = payload.get("action")
        handlers = {
            "toggle": self.toggle_menu,
            "toggle_menu": self.toggle_menu,
            "open_custom": lambda: self.open_card_chat(focus_composer=True),
            "open_deck_general": self.open_deck_general,
            "configure_profiles": self.configure_profiles,
            "sync": self._render,
            "minimize": self.minimize,
            "close_workspace": self.close_workspace,
            "restore_workspace": self.restore_workspace,
            "cancel": self.cancel,
            "retry": self.retry_connection,
            "copy_diagnostic": self.copy_diagnostic,
            "reset_layout": self.reset_layout,
        }
        if action == "select_action":
            self.select_action(str(payload.get("action_id", "")))
        elif action == "send":
            self.send(str(payload.get("message", "")))
        elif action == "save_layout":
            self.save_layout(payload.get("layout"))
        elif action == "select_session":
            self.save_scroll(payload.get("scroll"))
            self.select_session(payload.get("conversation_id"))
        elif action in handlers:
            self.save_scroll(payload.get("scroll"))
            handlers[action]()

    def toggle_menu(self) -> None:
        self._menu_open = not self._menu_open
        self._render()

    def configure_profiles(self) -> None:
        self._menu_open = False
        self._render()
        show_profile_dialog()

    def open_card_chat(self, *, focus_composer: bool = False) -> None:
        session = self._card_session(create=True)
        if session:
            self._activate(session, focus_composer=focus_composer)

    def open_deck_general(self) -> None:
        session = self._deck_session(create=True)
        if session:
            self._activate(session)

    def select_action(self, action_id: str) -> None:
        profile = self._effective_profile_for_current_card()
        action = (
            next((item for item in profile.actions if item.id == action_id), None)
            if profile
            else None
        )
        session = self._card_session(create=True)
        if action is None or session is None or self._is_busy(session):
            return
        session.automatic_message = action.instruction
        session.automatic_action_title = action.title
        session.request_state = "preparing"
        self._activate(session)

    def _activate(self, session: ChatSession, *, focus_composer: bool = False) -> None:
        self._selected_conversation_id, self._open, self._menu_open = (
            session.conversation_id,
            True,
            False,
        )
        self._render(focus_composer=focus_composer)
        get_runtime().ensure_ready(
            lambda status, key=session.conversation_id: self._on_connection_status(
                key, status
            )
        )

    def minimize(self) -> None:
        self._open, self._menu_open = False, False
        self._render()

    def close_workspace(self) -> None:
        """End work in every chat while retaining the runtime-only history."""

        self._open, self._menu_open = False, False
        for session in self._sessions.values():
            session.automatic_message, session.automatic_action_title = None, None
            if session.request_handle:
                get_runtime().cancel(session.request_handle)
                session.request_state = "cancelling"
        # Closing all chats ends the active workspace. Histories remain in the
        # runtime store and will be available again if the user starts that
        # card or deck conversation later, but there is nothing left to resume.
        self._sessions.clear()
        self._selected_conversation_id = None
        self._render()

    def restore_workspace(self) -> None:
        if self._selected_session() is not None:
            self._open, self._menu_open = True, False
        else:
            self._menu_open = True
        self._render()

    def select_session(self, conversation_id: object) -> None:
        key = str(conversation_id or "")
        if key not in self._sessions:
            return
        self._selected_conversation_id, self._open, self._menu_open = key, True, False
        self._render()

    def send(
        self,
        message: str,
        *,
        show_user_message: bool = True,
        request_kind: RequestKind = RequestKind.CUSTOM,
    ) -> None:
        session = self._selected_session()
        if session:
            self._send_session(session, message, show_user_message, request_kind)

    def _send_session(
        self,
        session: ChatSession,
        message: str,
        visible: bool,
        request_kind: RequestKind,
        *,
        presentation: str = "message",
        display_text: str | None = None,
    ) -> None:
        message = message.strip()
        if not message or not session.connection_ready or self._is_busy(session):
            return
        session.pending_message = message
        session.pending_message_visible = visible
        session.pending_presentation = presentation
        session.pending_display_text = display_text
        session.request_state = "queued"
        if self._selected_conversation_id == session.conversation_id:
            self._render(composer="")
        session.request_handle = get_runtime().submit_chat(
            session.context,
            get_store().turns_for(session.conversation_id),
            message,
            profile_context=session.profile_context,
            request_kind=request_kind,
            on_started=lambda handle, key=session.conversation_id: self._on_request_started(
                key, handle
            ),
            on_finished=lambda handle, result, key=session.conversation_id: self._on_response(
                key, handle, result
            ),
        )

    def cancel(self) -> None:
        session = self._selected_session()
        if session and session.request_handle:
            get_runtime().cancel(session.request_handle)
            session.request_state = "cancelling"
            self._render()
        elif session and session.automatic_message is not None:
            session.automatic_message, session.automatic_action_title = None, None
            session.request_state = None
            self._render(status="Action cancelled.")

    def retry_connection(self) -> None:
        session = self._selected_session()
        if session:
            if session.automatic_message is not None:
                session.request_state = "preparing"
                self._render()
            get_runtime().retry_connection(
                lambda status, key=session.conversation_id: self._on_connection_status(
                    key, status
                )
            )

    def copy_diagnostic(self) -> None:
        session = self._selected_session()
        result = session.last_connection_result if session else None
        if result and result.diagnostic:
            QApplication.clipboard().setText(
                result.diagnostic.copyable_text(result.error_kind)
            )
            self._render(status="Safe diagnostic copied.")

    def _on_request_started(self, key: str, handle: RequestHandle) -> None:
        session = self._sessions.get(key)
        if session is None or session.request_handle != handle:
            return
        session.request_state = "running"
        self._render()

    def _on_response(
        self, key: str, handle: RequestHandle, result: CodexResult
    ) -> None:
        session = self._sessions.get(key)
        if session is None or session.request_handle != handle:
            return
        message, visible = session.pending_message, session.pending_message_visible
        presentation, display_text = (
            session.pending_presentation,
            session.pending_display_text,
        )
        session.pending_message, session.pending_message_visible = None, True
        session.pending_presentation, session.pending_display_text = "message", None
        session.request_handle, session.request_state = None, None
        if result.succeeded and message is not None:
            get_store().add_exchange(
                key,
                message,
                result.text or "",
                show_user_message=visible,
                presentation=presentation,
                display_text=display_text,
            )
            self._render_for_session(key, status="Ready")
        elif result.error_kind == CodexErrorKind.CANCELLED:
            self._record_failed_action(
                key, message, visible, presentation, display_text, "cancelled"
            )
            self._render_for_session(key, status="Request cancelled.")
        else:
            self._record_failed_action(
                key, message, visible, presentation, display_text, "failed"
            )
            self._render_for_session(
                key, status=result.error_message or "Codex could not respond."
            )

    @staticmethod
    def _record_failed_action(
        key: str,
        message: str | None,
        visible: bool,
        presentation: str,
        display_text: str | None,
        state: str,
    ) -> None:
        if message is not None:
            get_store().add_user_message(
                key,
                message,
                visible=visible,
                presentation=presentation,
                display_text=display_text,
                state=state,
            )

    def _on_connection_status(self, key: str, status: ConnectionStatus) -> None:
        session = self._sessions.get(key)
        if session is None:
            return
        session.last_connection_result = status.result
        session.connection_ready = status.state == ConnectionState.READY
        if status.state == ConnectionState.CHECKING:
            self._render_for_session(key, status="Checking saved AI connection…")
        elif session.connection_ready:
            self._render_for_session(key, status="Ready")
            if session.automatic_message:
                message, title = (
                    session.automatic_message,
                    session.automatic_action_title,
                )
                session.automatic_message, session.automatic_action_title = None, None
                self._send_session(
                    session,
                    message,
                    True,
                    RequestKind.PRESET,
                    presentation="action",
                    display_text=title,
                )
        else:
            if session.automatic_message is not None:
                session.request_state = None
            self._render_for_session(
                key,
                status=(status.result.error_message if status.result else None)
                or "AI connection is not ready. Retry connection.",
            )

    def _render_for_session(self, key: str, **kwargs) -> None:
        (
            self._render(**kwargs)
            if self._selected_conversation_id == key
            else self._render()
        )

    def _card_session(self, *, create: bool) -> ChatSession | None:
        card = self._current_card or getattr(mw.reviewer, "card", None)
        try:
            card_id = int(card.id)
        except (AttributeError, TypeError, ValueError):
            return None
        key, session = f"card:{card_id}", self._sessions.get(f"card:{card_id}")
        if session is None and create:
            profile = self._effective_profile_for_current_card()
            title = self._compact_title(
                title_from_card(card, profile.title_field if profile else "")
            )
            session = ChatSession(
                key,
                "card",
                title or f"Card {card_id}",
                context_from_card(card) or "No readable card text was provided.",
                profile.context if profile else "",
                card_id=card_id,
            )
            self._sessions[key] = session
        return session

    def _deck_session(self, *, create: bool) -> ChatSession | None:
        card = self._current_card or getattr(mw.reviewer, "card", None)
        try:
            deck_id = int(card.did)
        except (AttributeError, TypeError, ValueError):
            return None
        key, session = f"deck:{deck_id}", self._sessions.get(f"deck:{deck_id}")
        if session is None and create:
            profile, name = self._effective_profile_for_current_card(), self._deck_name(
                deck_id
            )
            session = ChatSession(
                key,
                "deck",
                f"{name} · General",
                f"Deck: {name}",
                profile.context if profile else "",
                deck_id=deck_id,
            )
            self._sessions[key] = session
        return session

    @staticmethod
    def _deck_name(deck_id: int) -> str:
        return next(
            (deck.name for deck in deck_references() if deck.id == deck_id),
            f"Deck {deck_id}",
        )

    @staticmethod
    def _compact_title(value: str) -> str:
        value = " ".join(value.split())
        return value[:57] + "…" if len(value) > 58 else value

    def _selected_session(self) -> ChatSession | None:
        return self._sessions.get(self._selected_conversation_id or "")

    @staticmethod
    def _is_busy(session: ChatSession) -> bool:
        """True while a request or its connection preparation is active."""

        return session.pending_message is not None or (
            session.automatic_message is not None
            and session.request_state == "preparing"
        )

    def _effective_profile_for_current_card(self) -> DeckProfile | None:
        try:
            return effective_profile(int((self._current_card or mw.reviewer.card).did))
        except (AttributeError, TypeError, ValueError):
            return None

    def _render(
        self,
        *,
        status: str | None = None,
        composer: str | None = None,
        focus_composer: bool = False,
    ) -> None:
        if self._web is None:
            return
        payload = self._payload(
            status=status, composer=composer, focus_composer=focus_composer
        )
        self._web.eval(
            "window.AnkiAIWorkspace&&window.AnkiAIWorkspace.render("
            + json.dumps(payload)
            + ");"
        )

    def _payload(
        self,
        *,
        status: str | None = None,
        composer: str | None = None,
        focus_composer: bool = False,
    ) -> dict[str, object]:
        session = self._selected_session()
        turns = []
        if session:
            turns = [
                {
                    "role": turn.role,
                    "text": (
                        turn.display_text
                        if turn.display_text is not None
                        else turn.text
                    ),
                    "presentation": turn.presentation,
                    "state": turn.state,
                }
                for turn in get_store().turns_for(session.conversation_id)
                if turn.visible
            ]
            if session.pending_message is not None and session.pending_message_visible:
                turns.append(
                    {
                        "role": "user",
                        "text": (
                            session.pending_display_text
                            if session.pending_display_text is not None
                            else session.pending_message
                        ),
                        "presentation": session.pending_presentation,
                        "state": session.request_state,
                    }
                )
            elif session.automatic_action_title is not None:
                turns.append(
                    {
                        "role": "user",
                        "text": session.automatic_action_title,
                        "presentation": "action",
                        "state": "queued",
                    }
                )
            if self._is_busy(session):
                turns.append({"role": "assistant", "typing": True})
        return {
            "open": self._open and session is not None,
            "workspace_open": self._open and session is not None,
            "menu_open": self._menu_open,
            "menu": self._menu_payload(),
            "shortcuts": self._shortcut_payload(),
            "shortcuts_pending": self._card_shortcuts_pending(),
            "sessions": self._sessions_payload(),
            "selected_conversation_id": session.conversation_id if session else None,
            "workspace_has_sessions": bool(self._sessions),
            "workspace_pending": any(
                self._is_busy(item) for item in self._sessions.values()
            ),
            "turns": turns,
            "connection_health": self._connection_health(session),
            "ready": bool(session and session.connection_ready),
            "pending": bool(session and self._is_busy(session)),
            "failed": bool(
                session
                and session.last_connection_result
                and not session.connection_ready
            ),
            "composer": composer,
            "focus_composer": focus_composer,
            "layout": self._window_layout(),
            "scroll_top": session.scroll_top if session else 0,
            "scroll_following": session.scroll_following if session else True,
        }

    @staticmethod
    def _connection_health(session: ChatSession | None) -> str:
        if session is None:
            return "checking"
        if session.connection_ready:
            return "connected"
        if session.last_connection_result is not None:
            return "unavailable"
        return "checking"

    def _menu_payload(self) -> dict[str, object]:
        profile = self._effective_profile_for_current_card()
        try:
            deck_id = int((self._current_card or mw.reviewer.card).did)
        except (AttributeError, TypeError, ValueError):
            deck_id = 0
        return {
            "profile_name": profile.name if profile else "",
            "actions": (
                [{"id": action.id, "title": action.title} for action in profile.actions]
                if profile
                else []
            ),
            "has_profile": profile is not None,
            "deck_general_label": f"{self._deck_name(deck_id)} · General",
        }

    def _shortcut_payload(self) -> list[dict[str, str]]:
        profile = self._effective_profile_for_current_card()
        if profile is None:
            return []
        return [
            {"id": action.id, "title": action.title}
            for action in profile.actions
            if action.show_on_card
        ]

    def _card_shortcuts_pending(self) -> bool:
        session = self._card_session(create=False)
        return bool(session and self._is_busy(session))

    def _sessions_payload(self) -> list[dict[str, object]]:
        return [
            {
                "conversation_id": session.conversation_id,
                "kind": session.kind,
                "label": session.label,
                "pending": self._is_busy(session),
            }
            for session in self._sessions.values()
        ]

    def save_layout(self, layout: object) -> None:
        if not isinstance(layout, dict):
            return
        normalized: dict[str, int] = {}
        for key in ("left", "top", "width", "height"):
            value = layout.get(key)
            if not isinstance(value, (int, float)):
                return
            normalized[key] = max(0, min(10_000, int(value)))
        config = mw.addonManager.getConfig("anki_ai_workspace") or {}
        config["window_layout"] = normalized
        mw.addonManager.writeConfig("anki_ai_workspace", config)

    def save_scroll(self, scroll: object) -> None:
        """Keep per-conversation reading position for this Anki runtime only."""

        session = self._selected_session()
        if session is None or not isinstance(scroll, dict):
            return
        top, following = scroll.get("top"), scroll.get("following")
        if not isinstance(top, (int, float)) or not isinstance(following, bool):
            return
        session.scroll_top = max(0, min(1_000_000, int(top)))
        session.scroll_following = following

    def reset_layout(self) -> None:
        config = mw.addonManager.getConfig("anki_ai_workspace") or {}
        config.pop("window_layout", None)
        mw.addonManager.writeConfig("anki_ai_workspace", config)
        self._render()

    @staticmethod
    def _window_layout() -> dict[str, int] | None:
        layout = (mw.addonManager.getConfig("anki_ai_workspace") or {}).get(
            "window_layout"
        )
        if not isinstance(layout, dict):
            return None
        try:
            return {key: int(layout[key]) for key in ("left", "top", "width", "height")}
        except (KeyError, TypeError, ValueError):
            return None


controller = ReviewerChatController()
