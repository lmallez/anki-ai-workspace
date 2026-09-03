from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Sequence

from aqt import mw

from ..codex_client import (
    ChatTurn,
    CodexClient,
    CodexDiagnostic,
    CodexErrorKind,
    CodexResult,
    DEFAULT_CUSTOM_REASONING_EFFORT,
    DEFAULT_MODEL_VERBOSITY,
    DEFAULT_PRESET_REASONING_EFFORT,
    RequestKind,
)
from ..diagnostics import logger
from ..request_coordinator import ChatRequest, ChatRequestCoordinator, RequestHandle


class ConnectionState(str, Enum):
    UNCHECKED = "unchecked"
    CHECKING = "checking"
    READY = "ready"
    NEEDS_SETUP = "needs_setup"
    FAILED = "failed"


@dataclass(frozen=True)
class ConnectionStatus:
    state: ConnectionState
    result: CodexResult | None = None


class AnkiCodexRuntime:
    """One Anki-native Codex queue and one readiness check per Anki session."""

    def __init__(self) -> None:
        self._queue = ChatRequestCoordinator()
        self._status = ConnectionStatus(ConnectionState.UNCHECKED)
        self._connection_listeners: list[Callable[[ConnectionStatus], None]] = []

    def ensure_ready(self, listener: Callable[[ConnectionStatus], None]) -> None:
        logger().info("connection readiness requested state=%s", self._status.state)
        self._connection_listeners.append(listener)
        if self._status.state == ConnectionState.READY:
            self._notify_connection_listeners()
        elif self._status.state != ConnectionState.CHECKING:
            self._start_connection_check()
        else:
            listener(self._status)

    def retry_connection(self, listener: Callable[[ConnectionStatus], None]) -> None:
        self._connection_listeners.append(listener)
        if self._status.state == ConnectionState.CHECKING:
            listener(self._status)
            return
        self._start_connection_check()

    def reset_and_check_connection(self) -> None:
        """Discard cached readiness after the configured executable changes."""

        self._status = ConnectionStatus(ConnectionState.UNCHECKED)
        self._start_connection_check()

    def submit_chat(
        self,
        card_context: str,
        turns: Sequence[ChatTurn],
        user_message: str,
        *,
        profile_context: str = "",
        request_kind: RequestKind = RequestKind.CUSTOM,
        on_started: Callable[[RequestHandle], None],
        on_finished: Callable[[RequestHandle, CodexResult], None],
    ) -> RequestHandle:
        client = self._client()
        handle, request = self._queue.submit(
            lambda cancelled: client.ask(
                card_context,
                turns,
                user_message,
                profile_context=profile_context,
                request_kind=request_kind,
                cancellation_event=cancelled,
            ),
            on_started=on_started,
            on_finished=on_finished,
        )
        if request is not None:
            self._start_request(request)
        return handle

    def cancel(self, handle: RequestHandle) -> None:
        request = self._queue.cancel(handle)
        if request is not None:
            request.on_finished(
                request.handle,
                CodexResult(
                    error_kind=CodexErrorKind.CANCELLED,
                    error_message="The Codex request was cancelled.",
                ),
            )

    def _start_connection_check(self) -> None:
        logger().info("connection check queued")
        self._status = ConnectionStatus(ConnectionState.CHECKING)
        self._notify_check_started()
        client = self._client()
        _handle, request = self._queue.submit(
            lambda _cancelled: client.check_connection(),
            on_started=lambda _handle: None,
            on_finished=self._finish_connection_check,
        )
        if request is not None:
            self._start_request(request)

    def _finish_connection_check(
        self, handle: RequestHandle, result: CodexResult
    ) -> None:
        next_request = self._queue.complete(handle)
        state = ConnectionState.READY
        if not result.succeeded:
            if result.error_kind in {
                CodexErrorKind.EXECUTABLE_NOT_FOUND,
                CodexErrorKind.EXECUTABLE_BROKEN,
                CodexErrorKind.AUTH_REQUIRED,
            }:
                state = ConnectionState.NEEDS_SETUP
            else:
                state = ConnectionState.FAILED
        self._status = ConnectionStatus(state, result)
        logger().info(
            "connection check finished state=%s error_kind=%s", state, result.error_kind
        )
        self._notify_connection_listeners()
        if next_request is not None:
            self._start_request(next_request)

    def _start_request(self, request: ChatRequest) -> None:
        logger().info("anki task submitted request_id=%s", request.handle.request_id)
        request.on_started(request.handle)
        mw.taskman.run_in_background(
            lambda: request.run(request.cancelled),
            on_done=lambda future, current=request: self._finish_future(
                current, future
            ),
            uses_collection=False,
        )

    def _finish_future(self, request: ChatRequest, future) -> None:
        try:
            result = future.result()
        except Exception:
            logger().error("anki task failed request_id=%s", request.handle.request_id)
            result = CodexResult(
                error_kind=CodexErrorKind.SERVICE_ERROR,
                error_message="Anki could not start the Codex request. Retry connection.",
                diagnostic=CodexDiagnostic(
                    stage="startup",
                    executable=self._client().executable,
                ),
            )
        self._finish_request(request, result)

    def _finish_request(self, request: ChatRequest, result: CodexResult) -> None:
        logger().info(
            "anki task finished request_id=%s error_kind=%s",
            request.handle.request_id,
            result.error_kind,
        )
        request.on_finished(request.handle, result)
        next_request = self._queue.complete(request.handle)
        if next_request is not None:
            self._start_request(next_request)

    def _notify_connection_listeners(self) -> None:
        listeners, self._connection_listeners = self._connection_listeners, []
        for listener in listeners:
            listener(self._status)

    def _notify_check_started(self) -> None:
        for listener in self._connection_listeners:
            listener(self._status)

    @staticmethod
    def _client() -> CodexClient:
        config = mw.addonManager.getConfig("anki_ai_workspace") or {}
        return CodexClient(
            str(config.get("codex_executable") or ""),
            timeout_seconds=config.get("codex_timeout_seconds", 90),
            preset_reasoning_effort=config.get(
                "preset_reasoning_effort", DEFAULT_PRESET_REASONING_EFFORT
            ),
            custom_reasoning_effort=config.get(
                "custom_reasoning_effort", DEFAULT_CUSTOM_REASONING_EFFORT
            ),
            model_verbosity=config.get("model_verbosity", DEFAULT_MODEL_VERBOSITY),
        )


_runtime = AnkiCodexRuntime()


def get_runtime() -> AnkiCodexRuntime:
    return _runtime
