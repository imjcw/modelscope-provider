from typing import List
import logging

logger = logging.getLogger(__name__)


class LoadBalancer:
    """Load balancer for selecting ModelScope accounts."""

    def __init__(
        self,
        accounts: List,
        supplier_model_repo=None,
    ):
        self.accounts = accounts
        self.current_index = 0
        self.supplier_model_repo = supplier_model_repo

    def select_account(self, model_name: str = None):
        """Select an available account using round-robin strategy.

        When supplier_model_repo is set, first filter to suppliers that
        declare support for model_name. Falls back to all accounts if
        no supplier declares the model (backward compat).
        """
        if not self.accounts:
            raise ValueError("No accounts available for load balancing")
        candidates = self.accounts

        # Filter by model support if repo is available and model_name given
        if self.supplier_model_repo is not None and model_name:
            db_candidates = self.supplier_model_repo.find_suppliers_for_model(
                model_name
            )
            db_candidate_ids = {c["account_id"] for c in db_candidates}
            if db_candidate_ids:
                model_filtered = [
                    acc for acc in self.accounts
                    if acc.account_id in db_candidate_ids
                ]
                if model_filtered:
                    logger.info(
                        f"Filtered {len(candidates)} accounts to {len(model_filtered)} "
                        f"for model {model_name}"
                    )
                    candidates = model_filtered
                else:
                    logger.warning(
                        f"No active supplier declares model {model_name}; "
                        f"falling back to all accounts"
                    )
                # If db_candidates is empty or model_filtered is empty,
                # we fall through to the existing unavailable_models filter
            else:
                logger.warning(
                    f"No supplier declares model {model_name}; "
                    f"falling back to all accounts"
                )

        # Existing unavailable_models filter
        available_accounts = [
            acc for acc in candidates
            if acc.unavailable_models is None or model_name not in acc.unavailable_models
        ]
        if not available_accounts:
            all_unavailable = set()
            for acc in candidates:
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
