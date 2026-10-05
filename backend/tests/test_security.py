"""Tests for password hashing."""

from app.core.security import hash_password, verify_password


def test_hash_is_not_the_password_and_verifies() -> None:
    password_hash = hash_password("correct-horse")

    assert password_hash != "correct-horse"
    assert verify_password("correct-horse", password_hash)


def test_wrong_password_is_rejected() -> None:
    assert not verify_password("wrong", hash_password("correct-horse"))


def test_same_password_gives_different_hashes() -> None:
    assert hash_password("correct-horse") != hash_password("correct-horse")