"""Top-level conftest: make 'provider.' prefix resolvable to project root.

The project's source tree lives at the root of this repo (where services/,
models/, repositories/ etc. reside). Tests and main.py import these via the
``provider.`` prefix (e.g. ``from provider.services.load_balancer import ...``).

Because the directory itself is named ``modelscope-provider`` (not ``provider``),
plain ``provider.`` imports don't resolve without help. This conftest registers
``provider`` as a namespace package whose ``__path__`` is the project root, so
that ``from provider.X.Y import Z`` works the same as ``from X.Y import Z``.
"""
import os
import sys
import types

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# Add root to sys.path so bare imports resolve
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

# Register `provider` namespace package pointing to root, so `provider.X.Y`
# resolves to modules at the project root.
if "provider" not in sys.modules:
    _provider_pkg = types.ModuleType("provider")
    _provider_pkg.__path__ = [_PROJECT_ROOT]
    _provider_pkg.__package__ = "provider"
    sys.modules["provider"] = _provider_pkg
