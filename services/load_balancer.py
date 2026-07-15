from typing import List
import logging

logger = logging.getLogger(__name__)


class LoadBalancer:
    """Load balancer for selecting ModelScope accounts."""

    def __init__(self, accounts: List):
        self.accounts = accounts
        self.current_index = 0

    def select_account(self, model_name: str = None):
        """Select an available account using round-robin strategy."""
        if not self.accounts:
            raise ValueError("No accounts available for load balancing")
        available_accounts = [
            acc for acc in self.accounts
            if acc.unavailable_models is None or model_name not in acc.unavailable_models
        ]
        if not available_accounts:
            all_unavailable = set()
            for acc in self.accounts:
                if acc.unavailable_models:
                    all_unavailable.update(acc.unavailable_models)
            raise ValueError(
                f"All accounts are unavailable for model {model_name}. "
                f"Unavailable models: {all_unavailable}"
            )
        account = available_accounts[self.current_index % len(available_accounts)]
        self.current_index += 1
        logger.info(f"Selected account {account.account_id} for load balancing")
        return account
