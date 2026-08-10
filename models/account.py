from dataclasses import dataclass, field
from typing import List, Set, Optional

# Default provider type used when an account/supplier omits one.
# Centralized so the literal isn't duplicated as a magic string elsewhere.
DEFAULT_PROVIDER_TYPE = "modelscope"


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
        provider_type=account_dict.get("provider_type", DEFAULT_PROVIDER_TYPE),
        api_key_records=api_key_records if api_key_records is not None
        else account_dict.get("api_key_records"),
        unavailable_models=unavailable_models or set(),
    )
