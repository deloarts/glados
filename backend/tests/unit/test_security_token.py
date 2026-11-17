"""
Coverage for src/modules/platform/infrastructure/security/token.py and totp.py, which are
only importable under pytest because tests/conftest.py sets the env vars
their module-level `cfg` singleton needs.

This is security-critical code: JWT signing-key selection, expiry, and
the "reject anything that doesn't verify" contract. A regression here
(e.g. a partial TOTP-challenge token becoming usable as a full access
token, or a persistent-key token validating against the non-persistent
key) is an authentication bypass, so the negative cases matter more than
the happy path.
"""

from datetime import UTC
from datetime import datetime
from datetime import timedelta

import jwt
import pytest
from pydantic import ValidationError

from src.modules.platform.infrastructure.config.settings import cfg
from src.modules.platform.infrastructure.security.token import TokenPayload
from src.modules.platform.infrastructure.security.token import create_access_token
from src.modules.platform.infrastructure.security.token import create_partial_token
from src.modules.platform.infrastructure.security.token import get_subject_from_token
from src.modules.platform.infrastructure.security.token import get_token_payload
from src.modules.platform.infrastructure.security.totp import generate_totp_secret
from src.modules.platform.infrastructure.security.totp import get_totp_provisioning_uri
from src.modules.platform.infrastructure.security.totp import verify_totp
from src.modules.platform.infrastructure.security.totp import verify_totp_once

# ── create_access_token / round trip ──────────────────────────────────


class TestCreateAccessToken:
    def test_round_trips_the_subject(self):
        token = create_access_token(subject=42, persistent=True, expires_delta=timedelta(minutes=5))
        assert get_subject_from_token(token, persistent=True) == "42"

    def test_subject_is_always_stringified(self):
        """sub is str(subject) on the way in, so an int subject comes back
        as a string, callers must not rely on the original type."""
        token = create_access_token(subject=42, persistent=True, expires_delta=timedelta(minutes=5))
        payload = get_token_payload(token, persistent=True)
        assert payload is not None
        assert payload.sub == "42"

    def test_token_version_is_embedded_when_supplied(self):
        token = create_access_token(
            subject=1, persistent=True, expires_delta=timedelta(minutes=5), token_version=7
        )
        payload = get_token_payload(token, persistent=True)
        assert payload is not None
        assert payload.ver == 7

    def test_token_version_is_absent_when_not_supplied(self):
        token = create_access_token(subject=1, persistent=True, expires_delta=timedelta(minutes=5))
        payload = get_token_payload(token, persistent=True)
        assert payload is not None
        assert payload.ver is None

    def test_token_version_zero_is_embedded_not_treated_as_unset(self):
        """`if token_version is not None`, version 0 is a real version."""
        token = create_access_token(
            subject=1, persistent=True, expires_delta=timedelta(minutes=5), token_version=0
        )
        payload = get_token_payload(token, persistent=True)
        assert payload is not None
        assert payload.ver == 0

    def test_custom_expiry_is_honoured(self):
        token = create_access_token(subject=1, persistent=True, expires_delta=timedelta(minutes=5))
        raw = jwt.decode(
            token, cfg.security.secret_key_persistent, algorithms=[cfg.security.algorithm]
        )
        expected = datetime.now(UTC) + timedelta(minutes=5)
        assert abs(raw["exp"] - expected.timestamp()) < 5

    def test_an_already_expired_token_does_not_validate(self):
        token = create_access_token(subject=1, persistent=True, expires_delta=timedelta(minutes=-1))
        assert get_token_payload(token, persistent=True) is None
        assert get_subject_from_token(token, persistent=True) is None

    def test_none_expiry_omits_the_exp_claim_entirely(self):
        """Session tokens are bounded by their server-side row, not by JWT
        expiry, `expires_delta=None` must not sneak in a default."""
        token = create_access_token(subject=1, persistent=True, expires_delta=None)
        raw = jwt.decode(
            token, cfg.security.secret_key_persistent, algorithms=[cfg.security.algorithm]
        )
        assert "exp" not in raw
        assert get_token_payload(token, persistent=True) is not None

    def test_sid_is_embedded_and_round_trips(self):
        token = create_access_token(subject=1, persistent=False, expires_delta=None, sid="abc-123")
        payload = get_token_payload(token, persistent=False)
        assert payload is not None
        assert payload.sid == "abc-123"

    def test_sid_is_absent_when_not_supplied(self):
        token = create_access_token(subject=1, persistent=True, expires_delta=timedelta(minutes=5))
        payload = get_token_payload(token, persistent=True)
        assert payload is not None
        assert payload.sid is None


# ── Signing-key separation ────────────────────────────────────────────
#
# _secret_key() deliberately collapses both keys onto the persistent one
# when cfg.debug is True, so key *separation* only holds in non-debug
# mode. The suite's own settings (tests/conftest.py) set debug=false, but
# running with ENV_FILE=.env.dev pointed at a developer config flips it,
# so each mode gets its own test rather than one that silently depends on
# how the suite was invoked.

debug_mode = pytest.mark.skipif(not cfg.debug, reason="only applies when cfg.debug is True")
non_debug_mode = pytest.mark.skipif(cfg.debug, reason="only applies when cfg.debug is False")


class TestSigningKeySeparation:
    @non_debug_mode
    def test_persistent_and_non_persistent_tokens_use_different_keys(self):
        """The whole point of the two-key scheme: a "remember me"
        (persistent) token must not validate as a session token, or vice
        versa."""
        persistent = create_access_token(
            subject=1, persistent=True, expires_delta=timedelta(minutes=5)
        )
        non_persistent = create_access_token(
            subject=1, persistent=False, expires_delta=timedelta(minutes=5)
        )

        assert get_token_payload(persistent, persistent=False) is None
        assert get_token_payload(non_persistent, persistent=True) is None

    @debug_mode
    def test_debug_mode_collapses_both_keys_onto_the_persistent_one(self):
        """Documented convenience for local development, every token
        validates either way. This is precisely why debug must never be
        enabled in production."""
        non_persistent = create_access_token(
            subject=1, persistent=False, expires_delta=timedelta(minutes=5)
        )
        assert get_token_payload(non_persistent, persistent=True) is not None

    def test_each_token_validates_against_its_own_key(self):
        """Holds in both modes."""
        persistent = create_access_token(
            subject=1, persistent=True, expires_delta=timedelta(minutes=5)
        )
        non_persistent = create_access_token(
            subject=1, persistent=False, expires_delta=timedelta(minutes=5)
        )

        assert get_token_payload(persistent, persistent=True) is not None
        assert get_token_payload(non_persistent, persistent=False) is not None


# ── create_partial_token ──────────────────────────────────────────────


class TestCreatePartialToken:
    def test_carries_the_totp_pending_scope(self):
        payload = get_token_payload(create_partial_token(subject=1), persistent=False)
        assert payload is not None
        assert payload.scope == "totp_pending"

    def test_a_full_access_token_carries_no_scope(self):
        """This asymmetry is what lets route guards distinguish a
        half-authenticated TOTP challenge from a real session."""
        token = create_access_token(1, persistent=False, expires_delta=timedelta(minutes=5))
        payload = get_token_payload(token, persistent=False)
        assert payload is not None
        assert payload.scope is None

    @non_debug_mode
    def test_is_signed_with_the_non_persistent_key(self):
        token = create_partial_token(subject=1)
        assert get_token_payload(token, persistent=False) is not None
        assert get_token_payload(token, persistent=True) is None

    def test_expires_in_about_five_minutes(self):
        token = create_partial_token(subject=1)
        # Decode against whichever key _secret_key(persistent=False) picked,
        # so this holds in debug mode too.
        key = (
            cfg.security.secret_key_persistent
            if cfg.debug
            else cfg.security.secret_key_non_persistent
        )
        raw = jwt.decode(token, key, algorithms=[cfg.security.algorithm])
        expected = datetime.now(UTC) + timedelta(minutes=5)
        assert abs(raw["exp"] - expected.timestamp()) < 5


# ── get_token_payload / get_subject_from_token rejection paths ────────


class TestTokenRejection:
    def test_empty_token_returns_none(self):
        assert get_token_payload("", persistent=True) is None

    def test_garbage_token_returns_none_instead_of_raising(self):
        assert get_token_payload("not-a-jwt", persistent=True) is None

    def test_token_signed_with_a_foreign_key_returns_none(self):
        forged = jwt.encode(
            {"sub": "1", "exp": datetime.now(UTC) + timedelta(minutes=5)},
            "some-other-key",
            algorithm=cfg.security.algorithm,
        )
        assert get_token_payload(forged, persistent=True) is None

    def test_tampered_token_returns_none(self):
        token = create_access_token(subject=1, persistent=True, expires_delta=timedelta(minutes=5))
        tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
        assert get_token_payload(tampered, persistent=True) is None

    def test_get_subject_returns_none_for_an_invalid_token(self):
        assert get_subject_from_token("not-a-jwt", persistent=True) is None

    def test_get_subject_returns_none_when_the_payload_has_no_subject(self):
        token = jwt.encode(
            {"exp": datetime.now(UTC) + timedelta(minutes=5)},
            cfg.security.secret_key_persistent,
            algorithm=cfg.security.algorithm,
        )
        assert get_subject_from_token(token, persistent=True) is None

    def test_get_subject_returns_none_for_an_empty_token(self):
        assert get_subject_from_token("", persistent=True) is None


# ── TokenPayload model ────────────────────────────────────────────────


class TestTokenPayload:
    def test_all_fields_default_to_none(self):
        payload = TokenPayload()
        assert payload.sub is None
        assert payload.ver is None
        assert payload.scope is None
        assert payload.sid is None

    def test_accepts_a_string_subject(self):
        assert TokenPayload(sub="a").sub == "a"

    def test_rejects_a_non_string_subject(self):
        """Every token this codebase mints writes str(subject), see the
        field's own docstring, so a numeric or boolean `sub` claim can
        only come from a forged or malformed token. get_token_payload's
        `except (jwt.PyJWTError, ValidationError)` relies on this raising
        rather than silently coercing, so a forged token like that is
        rejected instead of quietly accepted with the wrong type."""
        with pytest.raises(ValidationError):
            TokenPayload(sub=1)


# ── TOTP ──────────────────────────────────────────────────────────────


class TestTotp:
    def test_generated_secret_is_valid_base32_of_the_usual_length(self):
        secret = generate_totp_secret()
        assert len(secret) == 32
        assert set(secret) <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")

    def test_generated_secrets_are_not_reused(self):
        assert generate_totp_secret() != generate_totp_secret()

    def test_verify_accepts_the_current_code(self):
        import pyotp

        secret = generate_totp_secret()
        assert verify_totp(secret, pyotp.TOTP(secret).now()) is True

    def test_verify_rejects_a_wrong_code(self):
        secret = generate_totp_secret()
        assert verify_totp(secret, "000000") is False

    def test_verify_rejects_a_code_from_a_different_secret(self):
        import pyotp

        code = pyotp.TOTP(generate_totp_secret()).now()
        assert verify_totp(generate_totp_secret(), code) is False

    def test_provisioning_uri_embeds_the_account_and_issuer(self):
        uri = get_totp_provisioning_uri("JBSWY3DPEHPK3PXP", "alice", "Glados")
        assert uri.startswith("otpauth://totp/")
        assert "alice" in uri
        assert "issuer=Glados" in uri
        assert "secret=JBSWY3DPEHPK3PXP" in uri


# ── verify_totp_once (replay protection) ────────────────────────────


class _ClaimSet:
    """A minimal, real claim-once store, not a canned True/False lambda,
    so these tests exercise verify_totp_once's actual counter arithmetic,
    not just whatever a mock was told to return."""

    def __init__(self) -> None:
        self.claimed: set[str] = set()
        self.calls: list[str] = []

    async def consume(self, counter: str) -> bool:
        self.calls.append(counter)
        if counter in self.claimed:
            return False
        self.claimed.add(counter)
        return True


class TestVerifyTotpOnce:
    async def test_accepts_a_correct_code_the_first_time(self):
        import pyotp

        secret = generate_totp_secret()
        claims = _ClaimSet()

        assert (
            await verify_totp_once(secret, pyotp.TOTP(secret).now(), consume=claims.consume) is True
        )

    async def test_rejects_the_same_code_a_second_time(self):
        import pyotp

        secret = generate_totp_secret()
        code = pyotp.TOTP(secret).now()
        claims = _ClaimSet()

        assert await verify_totp_once(secret, code, consume=claims.consume) is True
        assert await verify_totp_once(secret, code, consume=claims.consume) is False

    async def test_a_wrong_code_never_reaches_consume(self):
        """A wrong code must fail on verify_totp alone, never touching
        the replay store means a guessing attacker cannot use it as a
        side channel, and it keeps failed guesses from ever occupying a
        claim slot a legitimate retry might need."""
        claims = _ClaimSet()

        result = await verify_totp_once(generate_totp_secret(), "000000", consume=claims.consume)

        assert result is False
        assert claims.calls == []

    async def test_consume_is_called_with_the_current_30_second_step(self):
        import time

        import pyotp

        secret = generate_totp_secret()
        claims = _ClaimSet()
        expected_counter = str(int(time.time()) // 30)

        await verify_totp_once(secret, pyotp.TOTP(secret).now(), consume=claims.consume)

        assert claims.calls == [expected_counter]

    async def test_two_different_secrets_share_the_same_step_counter(self):
        """The counter is a function of wall-clock time alone, it does
        not depend on which secret produced the code. A caller that scopes
        its replay-guard key by user id (see login_totp/totp.py) is what
        keeps two different users' claims from colliding, not this."""
        import pyotp

        secret_a = generate_totp_secret()
        secret_b = generate_totp_secret()
        claims = _ClaimSet()

        await verify_totp_once(secret_a, pyotp.TOTP(secret_a).now(), consume=claims.consume)
        await verify_totp_once(secret_b, pyotp.TOTP(secret_b).now(), consume=claims.consume)

        assert len(claims.calls) == 2
        assert claims.calls[0] == claims.calls[1]


@pytest.mark.parametrize("persistent", [True, False])
def test_round_trip_works_for_both_key_modes(persistent):
    token = create_access_token(
        subject="user-7", persistent=persistent, expires_delta=timedelta(minutes=5)
    )
    assert get_subject_from_token(token, persistent=persistent) == "user-7"
