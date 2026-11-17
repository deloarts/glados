"""
The stack env generator at scripts/create_stack_env.py: every key comes out
in the format the service reading it accepts, the profiles follow the
answers, and no value would be mangled by compose's env file parsing.
"""

import base64
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "create_stack_env.py"


@pytest.fixture(scope="module")
def script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("create_stack_env", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _env(script: ModuleType, **answers: object) -> dict[str, str]:
    content = script.render(script.build_env(script.Answers(**answers)))
    pairs = [
        line.split("=", 1) for line in content.splitlines() if line and not line.startswith("#")
    ]
    return {name: value for name, value in pairs}


def test_every_glados_key_is_long_enough_and_distinct(script: ModuleType) -> None:
    env = _env(script)
    keys = [
        env["SECURITY__SECRET_KEY_PERSISTENT"],
        env["SECURITY__SECRET_KEY_NON_PERSISTENT"],
        env["SECURITY__ENCRYPTION_KEY"],
        env["SECURITY__BACKUP_ENCRYPTION_KEY"],
    ]
    assert all(len(key) >= 32 for key in keys)
    assert len(set(keys)) == len(keys)


def test_the_database_url_carries_the_generated_postgres_password(script: ModuleType) -> None:
    env = _env(script)
    assert f":{env['POSTGRES_PASSWORD']}@postgres:5432/" in env["DATABASE__URL"]


def test_the_time_tracking_credential_key_decodes_to_32_bytes(script: ModuleType) -> None:
    env = _env(script, time_tracking=True, time_tracking_base_url="http://10.0.0.5")
    encoded = env["TIME_TRACKING_SERVICE_CREDENTIAL_PRIVATE_KEY"]
    raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    assert len(raw) == 32
    assert env["TIME_TRACKING_SERVICE_ALLOW_INSECURE_HTTP"] == "true"


@pytest.mark.parametrize(
    ("answers", "expected"),
    [
        ({}, "seaweedfs"),
        ({"seaweedfs": False}, ""),
        (
            {"access": "cloudflare", "pgadmin": True, "pgadmin_email": "a@b.at"},
            "seaweedfs,cloudflare,pgadmin",
        ),
    ],
)
def test_profiles_follow_the_answers(
    script: ModuleType, answers: dict[str, object], expected: str
) -> None:
    assert _env(script, **answers)["COMPOSE_PROFILES"] == expected


def test_direct_access_trusts_no_proxy(script: ModuleType) -> None:
    env = _env(script, access="direct")
    assert env["FRONTEND_BIND"] == "0.0.0.0"
    assert env["GLADOS_TRUSTED_PROXIES"] == "none"


def test_no_generated_value_needs_quoting(script: ModuleType) -> None:
    env = _env(script, time_tracking=True, time_tracking_base_url="https://t.example.com")
    for name, value in env.items():
        assert script.check_env_value(value) is None, name


@pytest.mark.parametrize("value", ["latest", "0.1", "v0"])
def test_unpinned_versions_are_refused(script: ModuleType, value: str) -> None:
    assert script.check_version(value) is not None


@pytest.mark.parametrize("value", ["v0.1", "v0.1.2", "staging"])
def test_pinned_versions_and_channels_are_accepted(script: ModuleType, value: str) -> None:
    assert script.check_version(value) is None


def test_a_value_compose_would_interpolate_is_refused(script: ModuleType) -> None:
    assert script.check_env_value("pa$$word") is not None
    assert script.check_env_value("text # comment") is not None
