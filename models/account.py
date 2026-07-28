from dataclasses import dataclass
from typing import Set

# Default provider type used when an account/supplier omits one.
# Centralized so the literal isn't duplicated as a magic string elsewhere.
DEFAULT_PROVIDER_TYPE = "modelscope"


@dataclass
class ModelScopeAccount:
    """ModelScope account configuration."""

    account_id: str
    api_key: str
    base_url: str
    provider_type: str = DEFAULT_PROVIDER_TYPE
    name: str = ""
    quota_limit: int = 0
    quota_remaining: int = 0
    last_reset_date: str = ""
    unavailable_models: Set[str] = None

    def __post_init__(self):
        if self.unavailable_models is None:
            self.unavailable_models = set()
