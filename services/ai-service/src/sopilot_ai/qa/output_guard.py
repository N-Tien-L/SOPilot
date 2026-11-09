"""Output guard for the streamed answer (TECH-V2-ai-service §7.1 step 7, FR-13 layer 3).

The last ``max(len(canary), 40) + 32`` characters are held back and not sent. Every new delta is
checked:

- the canary appears in the output -> ``OUTPUT_CANARY``;
- a run of ``ECHO_WINDOW`` (40) consecutive characters of the protected rules appears in the output
  -> ``OUTPUT_PROMPT_ECHO``.

Because the held-back tail is longer than the canary and the echo window, a violation is always
caught before any of its characters are sent. The caller then sends a ``replace`` with a fixed
sentence and stops the stream; nothing is partly visible.
"""
from __future__ import annotations

from dataclasses import dataclass, field

ECHO_WINDOW = 40
HOLD_EXTRA = 32


@dataclass(frozen=True)
class Verdict:
    text: str  # safe text to send now
    violation: str | None = None  # OUTPUT_CANARY | OUTPUT_PROMPT_ECHO


@dataclass
class OutputGuard:
    canary: str
    protected: str
    _full: str = field(default="", init=False)
    _sent: int = field(default=0, init=False)
    _tripped: str | None = field(default=None, init=False)

    @property
    def hold(self) -> int:
        # The held-back tail must hold a whole echo window (40) and the canary, whatever canary a
        # caller passes: max(len(canary), 40) + 32. With the 23-character production canary: 72.
        return max(len(self.canary), ECHO_WINDOW) + HOLD_EXTRA

    @property
    def output(self) -> str:
        """Everything the model produced so far (for ``done.finalText`` on success)."""
        return self._full

    @property
    def tripped(self) -> bool:
        return self._tripped is not None

    def feed(self, delta: str) -> Verdict:
        if self._tripped:
            return Verdict("", self._tripped)
        start = max(0, len(self._full) - ECHO_WINDOW + 1)
        self._full += delta
        violation = self._check(start)
        if violation:
            self._tripped = violation
            return Verdict("", violation)
        safe_end = max(self._sent, len(self._full) - self.hold)
        text = self._full[self._sent:safe_end]
        self._sent = safe_end
        return Verdict(text)

    def finish(self) -> Verdict:
        """End of stream: release the held-back tail if no violation was found."""
        if self._tripped:
            return Verdict("", self._tripped)
        text = self._full[self._sent:]
        self._sent = len(self._full)
        return Verdict(text)

    def _check(self, start: int) -> str | None:
        # Case-insensitive: a model that prints the canary in lowercase still leaks it.
        if self.canary and self.canary.casefold() in self._full.casefold():
            return "OUTPUT_CANARY"
        if self.protected:
            # Only windows that end in the new text can be new matches.
            for i in range(start, len(self._full) - ECHO_WINDOW + 1):
                if self._full[i:i + ECHO_WINDOW] in self.protected:
                    return "OUTPUT_PROMPT_ECHO"
        return None
