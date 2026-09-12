from dataclasses import dataclass, field
from typing import List, Set, Optional

# Default provider type used when an account/supplier omits one.
# Centralized so the literal isn't duplicated as a magic string elsewhere.
DEFAULT_PROVIDER_TYPE = "modelscope"

# Upstream protocol used for Anthropic-protocol requests, per supplier.
# See ``ModelScopeAccount.anthropic_stream_protocol`` for the semantics.
# ``auto`` is the default: it stays on the native path but self-heals when an
# upstream's Anthropic streaming path is broken (see migration 029), so no
# manual config is needed to survive such a supplier.
DEFAULT_ANTHROPIC_STREAM_PROTOCOL = "auto"
ANTHROPIC_STREAM_PROTOCOLS = ("native", "openai", "auto")


def normalize_stream_protocol(value: Optional[str]) -> str:
    """Coerce a ``anthropic_stream_protocol`` value to one of the three modes.

    Called both on write (repository) and on read (``build_ms_account``) so the
    value that reaches the router is always one of
    :data:`ANTHROPIC_STREAM_PROTOCOLS`, even for rows written before the
    column existed (migration 029) or edited with a typo.
    """
    if value in ANTHROPIC_STREAM_PROTOCOLS:
        return value
    return DEFAULT_ANTHROPIC_STREAM_PROTOCOL


@dataclass
class ModelScopeAccount:
    """ModelScope account configuration."""

    account_id: str
    # ``api_key`` is the *effective* primary key used on the request hot path.
    # It is DERIVED, not stored: for DB-backed accounts it comes from the first
    # eligible record in ``api_key_records`` (the account_api_keys table); for
    # env-configured single-key accounts it falls back to the passed value.
    # The legacy ``accounts.api_key`` column was dropped (migration 023) — do not
    # read or write it; all keys live in account_api_keys.
    api_key: str = ""
    base_url: str = ""
    # Optional separate upstream base for the Anthropic-native protocol. When a
    # supplier exposes OpenAI and Anthropic endpoints at different URLs, set
    # ``base_url`` to the OpenAI endpoint and ``anthropic_base_url`` to the
    # Anthropic one. Empty means "fall back to base_url for Anthropic too".
    anthropic_base_url: str = ""
    # Auth scheme used when speaking to this supplier's Anthropic endpoint
    # (``/v1/messages``). Native Anthropic providers use ``"anthropic"``
    # (``x-api-key``); some dual-protocol suppliers (e.g. SenseTime) expose an
    # Anthropic-compatible ``/v1/messages`` but still require ``Authorization:
    # Bearer``, in which case this is ``"bearer"``.
    anthropic_auth_style: str = "anthropic"
    # Which upstream protocol to speak for this supplier when the client used
    # the Anthropic entry point. The gateway must not hardcode
    # ``/v1/messages``: some suppliers (e.g. SenseTime / 商汤) serve an
    # Anthropic-shaped endpoint whose *streaming* path returns 200 +
    # ``text/event-stream`` and then EOFs with an empty body, which makes
    # Anthropic clients retry the whole request non-streaming — billing it
    # twice — while their OpenAI endpoint streams the same models fine.
    #   "native" → hit ``/v1/messages`` unchanged.
    #   "openai" → convert the request to OpenAI format, hit
    #              ``/v1/chat/completions``, convert the response back.
    #   "auto"   → native first, but remember a switch to "openai" for a given
    #              model once its stream comes back empty repeatedly.
    #              (default — no config needed to survive a broken supplier)
    anthropic_stream_protocol: str = DEFAULT_ANTHROPIC_STREAM_PROTOCOL
    provider_type: str = DEFAULT_PROVIDER_TYPE
    name: str = ""
    quota_limit: int = 0
    quota_remaining: int = 0
    last_reset_date: str = ""
    unavailable_models: Set[str] = None
    api_keys: List[str] = field(default_factory=list)
    api_key_records: Optional[List[dict]] = field(default=None)

    def __post_init__(self):
        if self.unavailable_models is None:
            self.unavailable_models = set()
        # Derive the effective primary key from the multi-key records when
        # present (DB-backed accounts). Env-configured single-key accounts pass
        # ``api_key`` directly with no records and keep it as-is.
        if self.api_key_records:
            records = self.api_key_records
            eligible = [r for r in records if r.get("status", "active") != "frozen"]
            chosen = (eligible or records)[0]
            derived = (chosen or {}).get("api_key", "")
            if derived:
                self.api_key = derived
        if not self.api_keys:
            self.api_keys = [self.api_key] if self.api_key else []


def build_ms_account(
    account_dict: dict,
    *,
    api_key_records=None,
    unavailable_models=None,
) -> "ModelScopeAccount":
    """Construct a :class:`ModelScopeAccount` from a raw DB row dict.

    Shared by the alias router and the load-balancer refresh path so the
    multi-key ``api_key_records`` field (and ``unavailable_models``) are
    populated consistently instead of each caller re-deriving them.

    Args:
        account_dict: a row dict from the ``accounts`` table (expects keys
            ``account_id``, ``base_url`` and optionally ``name``/``provider_type``).
        api_key_records: list of key dicts from ``account_api_keys``; defaults
            to whatever is already present on ``account_dict``.
        unavailable_models: a set of currently-unavailable model names.
    """
    return ModelScopeAccount(
        account_id=account_dict["account_id"],
        name=account_dict.get("name", ""),
        base_url=account_dict["base_url"],
        anthropic_base_url=account_dict.get("anthropic_base_url", "") or "",
        anthropic_auth_style=account_dict.get("anthropic_auth_style", "anthropic") or "anthropic",
        anthropic_stream_protocol=normalize_stream_protocol(
            account_dict.get("anthropic_stream_protocol")
        ),
        provider_type=account_dict.get("provider_type", DEFAULT_PROVIDER_TYPE),
        api_key_records=api_key_records if api_key_records is not None
        else account_dict.get("api_key_records"),
        unavailable_models=unavailable_models or set(),
    )
