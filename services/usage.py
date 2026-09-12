"""Upstream usage-token normalization.

Upstreams disagree on whether ``input_tokens`` includes the cached portion of
the prompt:

- OpenAI (``prompt_tokens`` + ``prompt_tokens_details.cached_tokens``) and the
  Anthropic-compatible endpoints of 商汤/智谱 count the cache **inside**
  ``input_tokens`` — e.g. ``input_tokens=89179, cache_read_input_tokens=88960``.
- DeepSeek's Anthropic-compatible endpoint counts it **outside** — the
  ``input_tokens`` it returns is only the uncached remainder, e.g.
  ``input_tokens=305`` with ``cache_read_input_tokens=221952`` for a 222k
  prompt.

Storing both conventions as-is made the aggregate cache-hit rate exceed 100 %
(the miss volume went negative) and made token quota usage under-count
DeepSeek traffic by an order of magnitude.
"""

from typing import Tuple


def normalize_cache_usage(
    input_tokens: int,
    cached_tokens: int,
    cache_creation_tokens: int = 0,
) -> Tuple[int, int, int]:
    """Return ``(input_tokens, cached_tokens, cache_creation_tokens)`` with
    ``input_tokens`` always meaning the full prompt size.

    The cached portion (reads plus creations, both of which are prompt tokens)
    is folded into ``input_tokens`` **only** when it is reported outside it.
    Comparing first is what makes the rule self-detecting: upstreams that
    already include the cache pass through unchanged, so no per-model list is
    needed. Applying it twice is a no-op.

    The returned ``cached_tokens`` / ``cache_creation_tokens`` stay as
    reported. After normalization they are *breakdowns* of the new
    ``input_tokens`` (the new input already contains them) — never add them
    back. Cache-hit-rate queries use them as the numerator over
    ``input_tokens``.
    """
    inp = input_tokens or 0
    cache = cached_tokens or 0
    creation = cache_creation_tokens or 0
    if cache + creation <= inp:
        return inp, cache, creation
    return inp + cache + creation, cache, creation
