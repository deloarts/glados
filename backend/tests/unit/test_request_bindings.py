"""
Every binding a module declares for a dependency it cannot build is bound by
the composition root once the process has registered, so no route fails at
request time on an implementation nobody supplied.
"""

import importlib
from pathlib import Path

import pytest

from src.bootstrap.registrations import register_all
from src.modules.platform.adapters.inbound.api.deps.binding import Binding

_SRC = Path(__file__).resolve().parents[2] / "src"


def _binding_modules() -> list[str]:
    paths = sorted(_SRC.glob("modules/*/adapters/inbound/api/deps/bindings.py"))
    paths.append(_SRC / "read" / "adapters" / "inbound" / "api" / "deps.py")
    return [".".join(p.relative_to(_SRC.parent).with_suffix("").parts) for p in paths]


def test_every_declared_binding_is_bound_after_registration() -> None:
    register_all()
    unbound = []
    for name in _binding_modules():
        module = importlib.import_module(name)
        for attribute, value in vars(module).items():
            if isinstance(value, Binding):
                try:
                    value.get()
                except RuntimeError:
                    unbound.append(f"{name}.{attribute}")
    assert not unbound, f"bind these in src/bootstrap/bindings.py: {unbound}"


def test_an_unbound_binding_names_itself_and_the_place_to_bind_it() -> None:
    binding: Binding[int] = Binding("The answer")

    with pytest.raises(RuntimeError, match=r"The answer is not bound; src/bootstrap/bindings.py"):
        binding.get()

    binding.bind(42)
    assert binding.get() == 42
