"""The cheap pre-filter.

Scope §6: this stage is a cost control, not a quality control. Sending every
Slack message to an LLM does not pencil out, so anything that clearly cannot
carry a durable engineering fact is dropped here for free.

It is deliberately biased toward *keeping* borderline text: a false keep costs
one cheap model call, a false drop loses the memory permanently and silently.
Tune `CAPTURE_MIN_LENGTH` before adding cleverness here.
"""

import os
import re
from dataclasses import dataclass

from app.ingest.events import Event

MIN_LENGTH = int(os.getenv("CAPTURE_MIN_LENGTH", "40"))

# Slack emits these for membership churn and edits — never content.
_NOISE_SUBTYPES = {
    "channel_join",
    "channel_leave",
    "channel_topic",
    "channel_purpose",
    "channel_name",
    "channel_archive",
    "channel_unarchive",
    "message_deleted",
    "bot_message",
    "reminder_add",
    "file_share",
}

# Whole-message acknowledgements. Anchored, so "lgtm, but the retry loop still
# double-counts" survives — that one is a real convention signal.
_ACK = re.compile(
    r"^(lgtm|ok(ay)?|k|sure|thanks?|ty|thx|nice|cool|\+1|-1|done|yep|yeah|nope|"
    r"no|yes|agreed|same|this|\^+|👍|🎉|✅|🙏|😂|haha+)[\s!.?]*$",
    re.IGNORECASE,
)

_URL_ONLY = re.compile(r"^\s*<?https?://\S+>?\s*$")
_MENTION = re.compile(r"<[@#][^>]+>")
_SLACK_LINK = re.compile(r"<(https?://[^|>]+)(\|[^>]*)?>")
_CODE_BLOCK = re.compile(r"```.*?```", re.DOTALL)

# Terms that mark text as candidate-bearing even when it is short. Short and
# decisive ("we're going with Postgres, not Mongo") is the exact case a pure
# length cutoff would throw away.
_SIGNAL_TERMS = (
    "decided", "decision", "we should", "we will", "we're going", "going with",
    "instead of", "rather than", "because", "the reason", "rationale",
    "trade-off", "tradeoff", "convention", "always", "never", "must", "policy",
    "standard", "architecture", "design", "migrate", "migration", "deprecat",
    "switch to", "moved off", "moving off", "rfc", "adr", "proposal",
    "agreed", "consensus", "postmortem", "root cause", "runbook", "owns",
    "owner", "responsible for", "prefers", "let's use", "lets use",
)


@dataclass(slots=True)
class FilterResult:
    keep: bool
    reason: str


def _clean(text: str) -> str:
    """Strip Slack markup so length and pattern checks see real prose."""
    text = _CODE_BLOCK.sub(" ", text)
    text = _SLACK_LINK.sub(r"\1", text)
    text = _MENTION.sub(" ", text)
    return text.strip()


def prefilter(event: Event) -> FilterResult:
    if event.is_bot:
        return FilterResult(False, "bot message")

    if event.subtype in _NOISE_SUBTYPES:
        return FilterResult(False, f"noise subtype {event.subtype!r}")

    text = _clean(event.text)
    if not text:
        return FilterResult(False, "empty after markup strip")

    if _ACK.match(text):
        return FilterResult(False, "acknowledgement only")

    if _URL_ONLY.match(event.text.strip()):
        return FilterResult(False, "bare link with no commentary")

    lowered = text.lower()
    has_signal = any(term in lowered for term in _SIGNAL_TERMS)

    if len(text) < MIN_LENGTH and not has_signal:
        return FilterResult(False, f"under {MIN_LENGTH} chars with no signal term")

    return FilterResult(True, "signal term present" if has_signal else "candidate-bearing")
