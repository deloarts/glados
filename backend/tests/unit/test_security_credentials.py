"""
Coverage for the three remaining 0%-covered security primitives:
hashing.py (bcrypt password hashing), api_key.py, and pat.py
(opaque bearer credentials, SHA-256 hashed at rest).

Each module encodes a deliberate design decision documented in its own
docstring, bcrypt's per-call random salt for passwords vs. deterministic
SHA-256 for already-high-entropy API keys/PATs. Those properties are
exactly what these tests pin: a "helpful" refactor swapping one scheme
for the other would break either revocation lookups or password security,
and nothing else in the suite would catch it.
"""

from src.modules.platform.infrastructure.security.api_key import (
    display_prefix as api_key_display_prefix,
)
from src.modules.platform.infrastructure.security.api_key import generate_api_key
from src.modules.platform.infrastructure.security.api_key import hash_api_key
from src.modules.platform.infrastructure.security.hashing import get_hash
from src.modules.platform.infrastructure.security.hashing import verify_hash
from src.modules.platform.infrastructure.security.pat import display_prefix as pat_display_prefix
from src.modules.platform.infrastructure.security.pat import generate_pat
from src.modules.platform.infrastructure.security.pat import hash_pat

# ── hashing.py (bcrypt) ───────────────────────────────────────────────


class TestHashing:
    def test_hash_verifies_against_the_original_value(self):
        assert verify_hash("correct horse battery staple", get_hash("correct horse battery staple"))

    def test_wrong_value_does_not_verify(self):
        assert verify_hash("wrong", get_hash("right")) is False

    def test_hash_is_not_the_plaintext(self):
        assert get_hash("secret") != "secret"

    def test_hashing_is_salted_so_the_same_input_hashes_differently(self):
        """bcrypt generates a fresh salt per call, two hashes of the same
        password must differ, and both must still verify."""
        password = "same-password"
        first, second = get_hash(password), get_hash(password)

        assert first != second
        assert verify_hash(password, first)
        assert verify_hash(password, second)

    def test_hash_has_the_bcrypt_format(self):
        assert get_hash("x").startswith("$2b$")

    def test_verification_is_case_sensitive(self):
        assert verify_hash("Password", get_hash("password")) is False

    def test_empty_value_can_be_hashed_and_verified(self):
        assert verify_hash("", get_hash(""))

    def test_unicode_values_round_trip(self):
        value = "résumé-naïve-€-🔐"
        assert verify_hash(value, get_hash(value))


class TestHashingPastBcryptsInputLimit:
    """bcrypt reads only the first 72 bytes. bcrypt 4 dropped the rest
    silently and bcrypt 5 raises, so hashing.py cuts the input itself. These
    pin that a long password still hashes, still verifies, verifies against a
    hash bcrypt 4 stored, and that the bytes past the limit still do not
    count, exactly as before the upgrade."""

    LONG = "a" * 72 + "suffix12"
    # Two-byte characters after one ASCII byte, so the 72-byte cut splits "ä".
    SPLIT = "a" + "ä" * 40

    # Hashes written by bcrypt 4.3.0 (cost 4) for LONG and SPLIT, the way a
    # password row looks after it was stored before the upgrade.
    LONG_BCRYPT4 = "$2b$04$2kV8yDSAEL24GYkMCbLMqua4lAYb1my6n9GwCmcv41aWXEu8ktSqO"
    SPLIT_BCRYPT4 = "$2b$04$q1Xx56cIdqo57oNPBXd96.vhLuY3M4HCkGot7gTrPr4kog5V0zE/W"

    def test_a_password_over_72_bytes_hashes_and_verifies(self):
        assert len(self.LONG.encode("utf-8")) == 80
        assert verify_hash(self.LONG, get_hash(self.LONG))

    def test_a_hash_stored_by_bcrypt_4_still_verifies(self):
        assert verify_hash(self.LONG, self.LONG_BCRYPT4)
        assert verify_hash(self.SPLIT, self.SPLIT_BCRYPT4)

    def test_bytes_past_the_limit_do_not_count(self):
        hashed = get_hash(self.LONG)
        assert verify_hash("a" * 72, hashed)
        assert verify_hash("a" * 72 + "anything else", hashed)

    def test_a_difference_inside_the_limit_still_fails(self):
        assert verify_hash("b" + self.LONG[1:], get_hash(self.LONG)) is False

    def test_a_multi_byte_character_cut_at_the_limit_verifies(self):
        assert len(self.SPLIT.encode("utf-8")) == 81
        assert verify_hash(self.SPLIT, get_hash(self.SPLIT))


# ── api_key.py ────────────────────────────────────────────────────────


class TestApiKey:
    def test_generated_key_carries_the_expected_prefix(self):
        assert generate_api_key().startswith("glados_ak_")

    def test_generated_keys_are_unique(self):
        assert len({generate_api_key() for _ in range(50)}) == 50

    def test_generated_key_is_long_enough_to_be_high_entropy(self):
        # 32 random bytes urlsafe-encoded is ~43 chars, plus the prefix.
        assert len(generate_api_key()) >= len("glados_ak_") + 40

    def test_hash_is_deterministic(self):
        """Unlike bcrypt, the hash must be stable for the same input,
        revocation looks keys up *by hash*, which a random salt would
        make impossible."""
        token = generate_api_key()
        assert hash_api_key(token) == hash_api_key(token)

    def test_different_keys_hash_differently(self):
        assert hash_api_key(generate_api_key()) != hash_api_key(generate_api_key())

    def test_hash_is_a_sha256_hex_digest(self):
        digest = hash_api_key("anything")
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")

    def test_hash_does_not_contain_the_plaintext(self):
        token = generate_api_key()
        assert token not in hash_api_key(token)

    def test_display_prefix_keeps_the_prefix_plus_twelve_chars(self):
        token = generate_api_key()
        assert api_key_display_prefix(token) == token[: len("glados_ak_") + 12]

    def test_display_prefix_is_not_the_whole_secret(self):
        token = generate_api_key()
        assert len(api_key_display_prefix(token)) < len(token)

    def test_display_prefix_of_a_short_token_does_not_crash(self):
        assert api_key_display_prefix("short") == "short"


# ── pat.py ────────────────────────────────────────────────────────────


class TestPat:
    def test_generated_pat_carries_the_expected_prefix(self):
        assert generate_pat().startswith("glados_pat_")

    def test_generated_pats_are_unique(self):
        assert len({generate_pat() for _ in range(50)}) == 50

    def test_hash_is_deterministic(self):
        token = generate_pat()
        assert hash_pat(token) == hash_pat(token)

    def test_different_pats_hash_differently(self):
        assert hash_pat(generate_pat()) != hash_pat(generate_pat())

    def test_hash_is_a_sha256_hex_digest(self):
        digest = hash_pat("anything")
        assert len(digest) == 64
        assert set(digest) <= set("0123456789abcdef")

    def test_display_prefix_keeps_the_prefix_plus_twelve_chars(self):
        token = generate_pat()
        assert pat_display_prefix(token) == token[: len("glados_pat_") + 12]

    def test_display_prefix_of_a_short_token_does_not_crash(self):
        assert pat_display_prefix("short") == "short"


# ── Cross-scheme separation ───────────────────────────────────────────


class TestApiKeyAndPatAreDistinguishable:
    def test_prefixes_do_not_collide(self):
        """An API key must never be mistakable for a PAT by prefix alone,
        auth middleware routes on this."""
        assert not generate_api_key().startswith("glados_pat_")
        assert not generate_pat().startswith("glados_ak_")

    def test_both_schemes_hash_the_same_input_identically(self):
        """Both are plain SHA-256 with no scheme-specific salting, so the
        same string hashes the same under either, the prefix, not the
        hash, is what separates the two credential types."""
        assert hash_api_key("same-input") == hash_pat("same-input")
