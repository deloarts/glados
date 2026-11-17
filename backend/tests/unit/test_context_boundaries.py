"""
Guards the modules the backend is cut into (docs/CONTRIBUTING.md section 1
and ADR 0012). The folders are the modules: every file under src/ sits in
one module under src/modules/, in the shared kernel, in the read tier or in
the composition root (src/bootstrap/). import-linter checks the imports
(backend/.importlinter): the layers inside each module, the dependencies
each module declares, the public API of each module, and the rules for the
kernel, the read tier and the root. This test checks what import-linter
cannot: that the declared dependencies have no cycles, that each of them is
used, and that the contracts forbid exactly what DEPENDS_ON leaves out.
"""

import ast
import configparser
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
CONTRACTS = SRC.parent / ".importlinter"

PLATFORM = "platform"
CATALOGUE = "catalogue"
WORKSPACE = "workspace"
EXTERNAL_DATA = "external_data"
FULFILLMENT = "fulfillment"
QUALITY = "quality"
OPERATIONS = "operations"

# The modules each module may import, besides itself and the shared kernel.
# The read tier may import every module and the composition root imports
# everything; nothing imports either.
DEPENDS_ON: dict[str, frozenset[str]] = {
    PLATFORM: frozenset(),
    CATALOGUE: frozenset({PLATFORM}),
    WORKSPACE: frozenset({PLATFORM, CATALOGUE}),
    EXTERNAL_DATA: frozenset({PLATFORM, CATALOGUE}),
    FULFILLMENT: frozenset({PLATFORM, CATALOGUE, WORKSPACE}),
    QUALITY: frozenset({PLATFORM, CATALOGUE, WORKSPACE, FULFILLMENT}),
    OPERATIONS: frozenset({PLATFORM, CATALOGUE, FULFILLMENT}),
}
TIERS = ("shared_kernel", "read", "bootstrap")


def _module_paths() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def context_of(path: Path) -> str | None:
    """The module or tier a file under src/ belongs to, from its folder."""
    parts = path.relative_to(SRC).parts
    if len(parts) > 2 and parts[0] == "modules" and parts[1] in DEPENDS_ON:
        return parts[1]
    if len(parts) > 1 and parts[0] in TIERS:
        return parts[0]
    return None


def _imported_modules(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        for name in names:
            parts = name.split(".")
            if len(parts) > 2 and parts[:2] == ["src", "modules"]:
                found.add(parts[2])
    return found


def _contracts() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read(CONTRACTS)
    return parser


def _lines(value: str) -> set[str]:
    return {
        line.strip()
        for line in value.splitlines()
        if line.strip() and not line.strip().startswith("#")
    }


def test_every_file_belongs_to_a_module() -> None:
    outside = [
        path.relative_to(SRC).as_posix()
        for path in _module_paths()
        if path not in (SRC / "__init__.py", SRC / "modules" / "__init__.py")
        and context_of(path) is None
    ]
    assert not outside, (
        "every file under src/ sits in src/modules/<module>/, src/shared_kernel/, src/read/ or "
        f"src/bootstrap/: {outside}"
    )


def test_the_declared_dependencies_have_no_cycles() -> None:
    def reaches(start: str, goal: str, seen: frozenset[str] = frozenset()) -> bool:
        return any(
            dep == goal or (dep not in seen and reaches(dep, goal, seen | {dep}))
            for dep in DEPENDS_ON[start]
        )

    cyclic = sorted(module for module in DEPENDS_ON if reaches(module, module))
    assert not cyclic, f"these modules depend on themselves through DEPENDS_ON: {cyclic}"


def test_every_declared_dependency_is_used() -> None:
    used: set[tuple[str, str]] = set()
    for path in _module_paths():
        source = context_of(path)
        if source in DEPENDS_ON:
            used |= {(source, target) for target in _imported_modules(path)}
    unused = sorted(
        f"{source} -> {target}"
        for source, targets in DEPENDS_ON.items()
        for target in targets
        if (source, target) not in used
    )
    assert not unused, f"remove these from DEPENDS_ON, no import uses them: {unused}"


def test_the_contracts_forbid_what_depends_on_leaves_out() -> None:
    contracts = _contracts()
    wrong = []
    for module, allowed in DEPENDS_ON.items():
        expected = {
            f"src.modules.{other}"
            for other in DEPENDS_ON
            if other != module and other not in allowed
        }
        section = f"importlinter:contract:{module.replace('_', '-')}-dependencies"
        actual = _lines(contracts[section]["forbidden_modules"]) if section in contracts else set()
        if actual != expected:
            wrong.append(f"{section}: expected {sorted(expected)}, found {sorted(actual)}")
    assert not wrong, f"the dependency contracts in .importlinter differ from DEPENDS_ON: {wrong}"


def test_every_module_has_a_privacy_contract() -> None:
    contracts = _contracts()
    missing = [
        module
        for module in DEPENDS_ON
        if f"importlinter:contract:{module.replace('_', '-')}-privacy" not in contracts
    ]
    assert not missing, f"add a protected contract to .importlinter for: {missing}"


def _packages(directory: Path) -> list[Path]:
    return sorted(
        p
        for p in directory.iterdir()
        if p.name != "__pycache__"
        and (
            (p.is_dir() and (p / "__init__.py").exists())
            or (p.suffix == ".py" and p.stem != "__init__")
        )
    )


def test_the_privacy_contracts_cover_every_adapter() -> None:
    """A module's adapters are internal except its ORM models and row
    mappers, which other modules' persistence adapters may use (shared
    database), its API schemas, which other modules' routes may embed, its
    dependency factories, which the factories of the modules above build on
    (test_every_module_protects_its_dependency_factories), and its settings
    store, which the stores of the modules above extend. The privacy
    contracts list those packages one by one to leave the exceptions out, so
    a new one must be added there."""
    contracts = _contracts()
    missing = []
    for module in DEPENDS_ON:
        if module == PLATFORM:
            continue
        section = f"importlinter:contract:{module.replace('_', '-')}-privacy"
        protected = _lines(contracts[section]["protected_modules"])
        adapters = SRC / "modules" / module / "adapters"
        expected: list[Path] = []
        for child in _packages(adapters):
            for grand in _packages(child) if child.name in ("inbound", "outbound") else [child]:
                if grand.name == "persistence":
                    for path in _packages(grand):
                        if path.name == "repositories":
                            expected += [
                                r
                                for r in _packages(path)
                                if not r.stem.endswith("_settings_repository")
                            ]
                        elif path.name not in ("models", "mappers"):
                            expected.append(path)
                elif grand.name == "api" and child.name == "inbound":
                    expected += [p for p in _packages(grand) if p.name not in ("schemas", "deps")]
                else:
                    expected.append(grand)
        missing += [
            name
            for path in expected
            if (name := ".".join(("src", *path.relative_to(SRC).with_suffix("").parts)))
            not in protected
        ]
    platform = _lines(contracts["importlinter:contract:platform-privacy"]["protected_modules"])
    repositories = (
        SRC / "modules" / PLATFORM / "adapters" / "outbound" / "persistence" / "repositories"
    )
    missing += [
        name
        for path in _packages(repositories)
        if not path.stem.endswith("_settings_repository")
        and (name := ".".join(("src", *path.relative_to(SRC).with_suffix("").parts)))
        not in platform
    ]
    assert not missing, f"add these to their module's privacy contract in .importlinter: {missing}"


def test_every_module_protects_its_dependency_factories() -> None:
    """A module's dependency factories build its use cases, so only the
    factories of other modules, which wire its repositories and facades into
    their own use cases, and the composition root may import them. Routes of
    another module never take its use cases from there."""
    contracts = _contracts()
    missing = []
    for module in DEPENDS_ON:
        if module == PLATFORM:
            continue
        section = f"importlinter:contract:{module.replace('_', '-')}-deps"
        deps = f"src.modules.{module}.adapters.inbound.api.deps"
        if section not in contracts or _lines(contracts[section]["protected_modules"]) != {deps}:
            missing.append(module)
            continue
        assert _lines(contracts[section]["allowed_importers"]) == {
            f"src.modules.{module}",
            "src.modules.*.adapters.inbound.api.deps",
            "src.bootstrap",
        }, section
    assert not missing, f"add a deps contract to .importlinter for: {missing}"


def test_the_fulfillment_layers_name_every_use_case_group() -> None:
    """The layers contract over the use-case groups of Planning & fulfillment
    constrains only the groups it names, so a new group must take its place
    in it before it can import or be imported by the others."""
    contract = _contracts()["importlinter:contract:fulfillment-use-case-layers"]
    named = {
        group.strip()
        for layer in _lines(contract["layers"])
        for group in layer.replace(":", "|").split("|")
    }
    use_cases = SRC / "modules" / FULFILLMENT / "application" / "use_cases"
    missing = sorted(
        f"use_cases.{path.name}"
        for path in _packages(use_cases)
        if path.is_dir() and f"use_cases.{path.name}" not in named
    )
    assert not missing, f"add these to the fulfillment-use-case-layers contract: {missing}"
