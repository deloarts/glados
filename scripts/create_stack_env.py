#!/usr/bin/env python3
"""
Creates the env file of a new Glados stack by asking a few questions.

It writes every value docker-compose.yml needs, generates the passwords and
keys in the format each one requires, and turns the answers into the
matching COMPOSE_PROFILES. The result is meant for the first deploy: upload
it to Portainer with "Load variables from .env file", or keep it next to
docker-compose.yml as .env for the CLI (docs/INSTALLATION.md sections 3 and
4). It never overwrites an existing file without asking, and writes the new
one readable by its owner only, since it holds every secret of the stack.

Usage:
    python3 scripts/create_stack_env.py [--output stack.env]

Only the Python standard library is used, so it runs on any machine with
Python 3.10 or newer, including the Docker host itself.
"""

from __future__ import annotations

import argparse
import getpass
import ipaddress
import os
import re
import secrets
import sys
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_VERSION = re.compile(r"^(v\d+\.\d+(\.\d+)?|staging|release-candidate)$")
_DEFAULT_EXTERNAL_SUBNET = "192.168.241.0/24"


def hex_key() -> str:
    """A 64 character hex key, for the signing and encryption keys, which
    need at least 32 characters."""
    return secrets.token_hex(32)


def url_safe_secret(length: int = 32) -> str:
    """A random secret of `length` bytes in unpadded base64url, safe in an
    env file and in a URL."""
    return secrets.token_urlsafe(length)


def x25519_private_key() -> str:
    """Thirty-two random bytes in unpadded base64url. Every such value is a
    valid X25519 private key, the format a time tracking service expects
    for opening sealed credentials."""
    return secrets.token_urlsafe(32)


def check_env_value(value: str) -> str | None:
    """Why a value cannot go into the env file unquoted, or None. Compose
    interpolates `$` and treats ` #` as the start of a comment, and a line
    break would end the value."""
    if "\n" in value or "\r" in value:
        return "must be a single line"
    if "$" in value:
        return "must not contain $"
    if " #" in value:
        return "must not contain ' #'"
    return None


def check_url(value: str, *, schemes: tuple[str, ...] = ("https", "http")) -> str | None:
    parts = urlsplit(value)
    if parts.scheme not in schemes or not parts.netloc:
        return f"must be a URL starting with {' or '.join(s + '://' for s in schemes)}"
    return check_env_value(value)


def check_email(value: str) -> str | None:
    return None if _EMAIL.match(value) else "must be an email address"


def check_version(value: str) -> str | None:
    if value == "latest":
        return "pin a release such as v0.1 instead of latest"
    if not _VERSION.match(value):
        return "must be a release such as v0.1 or v0.1.2, or a channel such as staging"
    return None


def check_networks(value: str) -> str | None:
    for item in value.split(","):
        try:
            ipaddress.ip_network(item.strip(), strict=False)
        except ValueError:
            return f"{item.strip()!r} is not an address or CIDR network"
    return None


def check_password(value: str) -> str | None:
    if len(value) < 12:
        return "must have at least 12 characters"
    return check_env_value(value)


@dataclass
class Answers:
    """Everything the questions decide. The generated secrets are filled in
    by `build_env`, so a test can build an env file without a terminal."""

    version: str = "v0.1"
    domain: str = "https://glados.example.com"
    portainer: bool = True
    access: str = "host-proxy"  # host-proxy, remote-proxy, cloudflare, direct
    remote_proxy: str = ""
    frontend_port: int = 8080
    tunnel_token: str = ""
    seaweedfs: bool = True
    pgadmin: bool = False
    pgadmin_email: str = ""
    private_images: bool = True
    admin_name: str = "Glados Admin"
    admin_mail: str = "admin@example.com"
    admin_password: str = ""
    log_level: str = "INFO"
    time_tracking: bool = False
    time_tracking_base_url: str = ""
    time_tracking_project: str = ""
    time_tracking_timezone: str = "Europe/Vienna"
    generated: list[str] = field(default_factory=list)


def profiles(answers: Answers) -> list[str]:
    chosen = []
    if answers.seaweedfs:
        chosen.append("seaweedfs")
    if answers.access == "cloudflare":
        chosen.append("cloudflare")
    if answers.pgadmin:
        chosen.append("pgadmin")
    return chosen


def build_env(answers: Answers) -> list[tuple[str, list[tuple[str, str]]]]:
    """The env file as sections of (name, value) pairs. Generates every
    secret the answers did not supply and records its name in
    `answers.generated`."""

    def generated(name: str, value: str) -> tuple[str, str]:
        answers.generated.append(name)
        return name, value

    postgres_password = url_safe_secret(24)
    sections: list[tuple[str, list[tuple[str, str]]]] = []

    deploy = [("GLADOS_VERSION", answers.version)]
    if answers.portainer:
        deploy.append(("ENV_FILE", "stack.env"))
    deploy.append(("COMPOSE_PROFILES", ",".join(profiles(answers))))
    if answers.access == "direct":
        deploy += [("FRONTEND_BIND", "0.0.0.0"), ("GLADOS_TRUSTED_PROXIES", "none")]
    elif answers.access == "remote-proxy":
        deploy += [("FRONTEND_BIND", "0.0.0.0"), ("GLADOS_TRUSTED_PROXIES", answers.remote_proxy)]
    if answers.frontend_port != 8080:
        deploy.append(("FRONTEND_PORT", str(answers.frontend_port)))
    sections.append(("Release and deploy control", deploy))

    sections.append(
        (
            "App",
            [
                ("DEBUG", "false"),
                ("DOMAIN", answers.domain),
                ("LOG_LEVEL", answers.log_level),
                ("LOG_DB_LEVEL", "INFO"),
                ("LOG_FORMAT", "text"),
            ],
        )
    )
    sections.append(
        (
            "Database and Redis",
            [
                (
                    "DATABASE__URL",
                    f"postgresql+psycopg://glados:{postgres_password}@postgres:5432/glados",
                ),
                ("POSTGRES_USER", "glados"),
                generated("POSTGRES_PASSWORD", postgres_password),
                ("POSTGRES_DB", "glados"),
                ("REDIS__URL", "redis://redis:6379/0"),
            ],
        )
    )
    sections.append(
        (
            "Security (keep SECURITY__ENCRYPTION_KEY and SECURITY__BACKUP_ENCRYPTION_KEY apart from the backups)",
            [
                generated("SECURITY__SECRET_KEY_PERSISTENT", hex_key()),
                generated("SECURITY__SECRET_KEY_NON_PERSISTENT", hex_key()),
                generated("SECURITY__ENCRYPTION_KEY", hex_key()),
                generated("SECURITY__BACKUP_ENCRYPTION_KEY", hex_key()),
            ],
        )
    )

    admin_password = answers.admin_password
    admin = [
        ("INIT__FULL_NAME", answers.admin_name),
        ("INIT__MAIL", answers.admin_mail),
    ]
    if admin_password:
        admin.append(("INIT__PASSWORD", admin_password))
    else:
        admin.append(generated("INIT__PASSWORD", url_safe_secret(18)))
    sections.append(("Initial admin, change the password after the first sign-in", admin))
    sections.append(("Storage", [("LOCAL_STORAGE__BASE_DIR", "./media")]))

    if answers.seaweedfs:
        sections.append(
            (
                "SeaweedFS, enter the same pair in Admin Settings > Storage",
                [
                    ("SEAWEEDFS_ACCESS_KEY", "glados"),
                    generated("SEAWEEDFS_SECRET_KEY", url_safe_secret(24)),
                ],
            )
        )
    if answers.pgadmin:
        sections.append(
            (
                "pgAdmin",
                [
                    ("PGADMIN_DEFAULT_EMAIL", answers.pgadmin_email),
                    generated("PGADMIN_DEFAULT_PASSWORD", url_safe_secret(18)),
                ],
            )
        )
    if answers.access == "cloudflare":
        sections.append(("Cloudflare Tunnel", [("TUNNEL_TOKEN", answers.tunnel_token)]))
    if answers.time_tracking:
        insecure = urlsplit(answers.time_tracking_base_url).scheme == "http"
        sections.append(
            (
                "Time tracking service, enter the same API key in Admin Settings > Time Tracking",
                [
                    generated("TIME_TRACKING_SERVICE_API_KEY", url_safe_secret(32)),
                    generated("TIME_TRACKING_SERVICE_CREDENTIAL_PRIVATE_KEY", x25519_private_key()),
                    ("TIME_TRACKING_SERVICE_BASE_URL", answers.time_tracking_base_url),
                    ("TIME_TRACKING_SERVICE_ALLOW_INSECURE_HTTP", "true" if insecure else "false"),
                    ("TIME_TRACKING_SERVICE_DEFAULT_PROJECT", answers.time_tracking_project),
                    ("TIME_TRACKING_SERVICE_TIMEZONE", answers.time_tracking_timezone),
                ],
            )
        )
    return sections


def render(sections: list[tuple[str, list[tuple[str, str]]]]) -> str:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        f"# Glados stack env, created by scripts/create_stack_env.py on {stamp}.",
        "# Every secret of the stack is in here: keep this file in a password",
        "# manager, never in git. docs/INSTALLATION.md section 5 explains each value.",
    ]
    for title, pairs in sections:
        lines += ["", f"# {title}"]
        lines += [f"{name}={value}" for name, value in pairs]
    return "\n".join(lines) + "\n"


# ── Questions ─────────────────────────────────────────────────────────────


def ask(
    question: str,
    default: str = "",
    check: Callable[[str], str | None] | None = None,
    *,
    secret: bool = False,
    optional: bool = False,
) -> str:
    hint = f" [{default}]" if default else (" (optional)" if optional else "")
    while True:
        prompt = f"{question}{hint}: "
        raw = getpass.getpass(prompt) if secret else input(prompt)
        value = raw.strip() or default
        if not value:
            if optional:
                return ""
            print("  A value is needed.")
            continue
        problem = (check or check_env_value)(value)
        if problem is None:
            return value
        print(f"  That {problem}.")


def ask_yes(question: str, default: bool) -> bool:
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{question} [{hint}]: ").strip().lower()
        if not raw:
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print("  Answer y or n.")


def ask_choice(question: str, options: list[tuple[str, str]], default: str) -> str:
    print(question)
    for number, (_, label) in enumerate(options, start=1):
        print(f"  {number}) {label}")
    keys = [key for key, _ in options]
    while True:
        raw = input(f"Choice [{keys.index(default) + 1}]: ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return keys[int(raw) - 1]
        print(f"  Enter a number from 1 to {len(options)}.")


def interview() -> Answers:
    a = Answers()
    print("Glados stack setup. Press Enter to take the value in brackets.\n")

    print("── Release")
    a.version = ask("Glados release to run, e.g. v0.1, or the channel staging", "v0.1", check_version)
    a.portainer = ask_yes("Is the stack deployed with Portainer?", True)

    print("\n── Access")
    a.domain = ask("Public URL users open, e.g. https://glados.example.com", "", check_url)
    a.access = ask_choice(
        "How do users reach Glados?",
        [
            ("host-proxy", "through a reverse proxy on this Docker host (nginx, Caddy, ...)"),
            ("remote-proxy", "through a reverse proxy on another machine"),
            ("cloudflare", "through a Cloudflare Tunnel"),
            ("direct", "directly on the published port, with no proxy in front"),
        ],
        "host-proxy",
    )
    if a.access == "remote-proxy":
        a.remote_proxy = ask("Address or CIDR network of that proxy", "", check_networks)
    if a.access == "cloudflare":
        a.tunnel_token = ask("Cloudflare Tunnel token", "", secret=True)
    if a.access in ("direct", "remote-proxy", "host-proxy"):
        port = ask("Host port the frontend is published on", "8080", _check_port)
        a.frontend_port = int(port)

    print("\n── Services")
    a.seaweedfs = ask_yes("Store files in the bundled SeaweedFS (S3 storage in the stack)?", True)
    a.pgadmin = ask_yes("Include pgAdmin, a database console for one-off fixes?", False)
    if a.pgadmin:
        a.pgadmin_email = ask("pgAdmin login email", "", check_email)
    a.private_images = ask_yes("Are the Glados images private on GHCR?", True)
    a.time_tracking = ask_yes("Connect a time tracking service?", False)
    if a.time_tracking:
        a.time_tracking_base_url = ask(
            "URL of the attendance system the service reads from", "", check_url
        )
        a.time_tracking_project = ask("Default project", "", optional=True)
        a.time_tracking_timezone = ask("Time zone of the attendance system", "Europe/Vienna")

    print("\n── Initial admin")
    a.admin_name = ask("Full name", "Glados Admin")
    a.admin_mail = ask("Email", "", check_email)
    if not ask_yes("Generate a random password for this admin?", True):
        a.admin_password = ask("Password", "", check_password, secret=True)

    print("\n── Logging")
    a.log_level = ask_choice(
        "Minimum level written to the container log",
        [("INFO", "INFO"), ("DEBUG", "DEBUG"), ("WARNING", "WARNING")],
        "INFO",
    )
    return a


def _check_port(value: str) -> str | None:
    if not value.isdigit() or not 1 <= int(value) <= 65535:
        return "must be a port number from 1 to 65535"
    return None


def write(path: Path, content: str) -> None:
    """Writes the file readable by its owner only, before any secret lands
    in it."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(content)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the env file of a new Glados stack.")
    parser.add_argument("--output", type=Path, default=Path("stack.env"), help="default: stack.env")
    args = parser.parse_args()

    if args.output.exists() and not ask_yes(f"{args.output} exists. Overwrite it?", False):
        print("Nothing written.")
        return 1
    try:
        answers = interview()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled, nothing written.")
        return 1

    write(args.output, render(build_env(answers)))
    print(f"\nWrote {args.output} (readable by you only).")
    print("Generated: " + ", ".join(answers.generated) + ".")
    print("Keep the file in a password manager. Without SECURITY__ENCRYPTION_KEY")
    print("and SECURITY__BACKUP_ENCRYPTION_KEY, the stored secrets and the backups")
    print("cannot be read.")
    if answers.portainer:
        print("Portainer: Stacks > Add stack, paste docker-compose.yml, then")
        print(f"'Load variables from .env file' with {args.output}.")
        if answers.private_images:
            print("Add ghcr.io under Registries with a read:packages token first, so")
            print("Portainer can pull the private images.")
    else:
        print(f"CLI: copy {args.output} next to docker-compose.yml as .env, then")
        if answers.private_images:
            print("log in once with docker login ghcr.io (a read:packages token) and run")
        print("docker compose up -d.")
    if answers.time_tracking:
        print("Time tracking: add the service's entry to the stack's compose file,")
        print("reading the TIME_TRACKING_SERVICE_* values, then enter its URL and the")
        print("same API key in Admin Settings > Time Tracking and confirm its key.")
    if answers.seaweedfs:
        print("Storage: enter SEAWEEDFS_ACCESS_KEY and SEAWEEDFS_SECRET_KEY in")
        print("Admin Settings > Storage after the first sign-in.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
