"""Hook registry for coordinating extension callbacks."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from zscripts.observability.instrumentation import InstrumentationManager
from zscripts.observability.logging import get_logger

HookCallback = Callable[..., object | None]


@dataclass(slots=True)
class HookRegistration:
    """Record describing a registered extension hook callback."""

    hook: str
    extension: str
    callback: HookCallback


class ExtensionHookRegistry:
    """Manage hook callbacks registered by extensions."""

    def __init__(self, instrumentation: InstrumentationManager) -> None:
        self._instrumentation = instrumentation
        self._callbacks: dict[str, list[HookRegistration]] = {}
        self._logger = get_logger("extensions.hooks")

    def register(self, hook: str, callback: HookCallback, *, extension: str) -> None:
        """Register ``callback`` for the named ``hook``.

        Args:
            hook: Identifier for the lifecycle event or signal.
            callback: Callable invoked when the hook is emitted.
            extension: Name of the extension registering the hook (for logging).

        Raises:
            ValueError: If the hook name is empty.
        """

        normalized = hook.strip()
        if not normalized:
            raise ValueError("Hook names must be non-empty strings.")
        registration = HookRegistration(
            hook=normalized,
            extension=extension,
            callback=callback,
        )
        bucket = self._callbacks.setdefault(normalized, [])
        bucket.append(registration)
        self._logger.debug(
            "extension.hook.registered",
            extra={"hook": normalized, "extension": extension, "count": len(bucket)},
        )

    def emit(self, hook: str, /, *args: object, **kwargs: object) -> list[object | None]:
        """Invoke callbacks registered for ``hook`` and return their results."""

        normalized = hook.strip()
        stored = self._callbacks.get(normalized)
        records = list(stored) if stored is not None else []
        results: list[object | None] = []
        for record in records:
            attributes: dict[str, str] = {"hook": normalized, "extension": record.extension}
            with self._instrumentation.operation(
                "extension.hook",
                attributes=attributes,
            ) as operation_result:
                try:
                    outcome = record.callback(*args, **kwargs)
                except Exception:
                    operation_result.status = "error"
                    self._logger.exception(
                        "extension.hook.error",
                        extra=attributes,
                    )
                    results.append(None)
                else:
                    results.append(outcome)
        return results

    def summary(self) -> Mapping[str, int]:
        """Return a mapping of hook names to registration counts."""

        return {hook: len(callbacks) for hook, callbacks in self._callbacks.items()}

    def clear(self) -> None:
        """Remove all registered hooks (primarily for tests)."""

        self._callbacks.clear()


__all__ = ["ExtensionHookRegistry", "HookRegistration", "HookCallback"]
