import pytest

from app.core.security import decrypt_secret, encrypt_secret, secret_hint


def test_encrypt_round_trip_and_ciphertext_hides_key():
    token = encrypt_secret("sk-live-1234567890abcd")
    assert "1234567890" not in token
    assert decrypt_secret(token) == "sk-live-1234567890abcd"


def test_tampered_ciphertext_is_rejected():
    with pytest.raises(ValueError):
        decrypt_secret(encrypt_secret("secret")[:-4] + "AAAA")


def test_hint_shows_only_last_four():
    assert secret_hint("sk-live-1234567890abcd") == "…abcd"
    assert secret_hint("short") == "…"
