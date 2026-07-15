from dataclasses import dataclass
from typing import Set


@dataclass
class ModelScopeAccount:
    """ModelScope account configuration."""

    account_id: str
    api_key: str
    base_url: str
    quota_limit: int = 0
    quota_remaining: int = 0
    last_reset_date: str = ""
    unavailable_models: Set[str] = None

    def __post_init__(self):
        if self.unavailable_models is None:
            self.unavailable_models = set()
