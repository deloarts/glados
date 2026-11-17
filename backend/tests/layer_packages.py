"""
Finds the modules of one layer package across every module of src/. Since
the code is split into modules, a layer package such as the persistence
repositories exists once per module, and a test that inspects every
repository or every request schema walks all of them.
"""

import pkgutil
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"
_ROOTS = ("modules/*", "read", "bootstrap", "shared_kernel")


def layer_module_names(layer: str, *, recursive: bool = True) -> list[str]:
    """The dotted names of the modules in `layer` (a path such as
    `adapters/outbound/persistence/repositories`) of every module, with
    subpackages when `recursive`."""
    names: list[str] = []
    for root in _ROOTS:
        for package_dir in sorted(_SRC.glob(f"{root}/{layer}")):
            if not (package_dir / "__init__.py").exists():
                continue
            prefix = ".".join(("src", *package_dir.relative_to(_SRC).parts)) + "."
            walk = pkgutil.walk_packages if recursive else pkgutil.iter_modules
            names.extend(info.name for info in walk([str(package_dir)], prefix))
    return names
