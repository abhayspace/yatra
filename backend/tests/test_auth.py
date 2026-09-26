"""Unit tests for auth validation logic — no Supabase/LLM calls."""

import pytest
from pydantic import ValidationError

from app.auth.routes import (
    LoginRequest,
    RegisterRequest,
    SetupCredentialsRequest,
    VerifyOtpRequest,
    _password_check,
)


def test_register_valid():
    r = RegisterRequest(
        username="ab_hay",
        full_name="Abhay Tripathi",
        email="a@b.com",
        password="passw0rd1",
        confirm_password="passw0rd1",
    )
    assert r.username == "ab_hay"


def test_register_rejects_bad_username():
    for bad in ["a", "has space", "x" * 21, "dash-name", ""]:
        with pytest.raises(ValidationError):
            RegisterRequest(
                username=bad,
                full_name="A B",
                email="a@b.com",
                password="passw0rd1",
                confirm_password="passw0rd1",
            )


def test_register_rejects_weak_passwords():
    for bad_pw in ["short1", "onlyletters", "12345678", ""]:
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="valid_user",
                full_name="A B",
                email="a@b.com",
                password=bad_pw,
                confirm_password=bad_pw,
            )


def test_register_rejects_bad_email_and_name():
    with pytest.raises(ValidationError):
        RegisterRequest(
            username="u_ser",
            full_name="A B",
            email="not-an-email",
            password="passw0rd1",
            confirm_password="passw0rd1",
        )
    with pytest.raises(ValidationError):
        RegisterRequest(
            username="u_ser",
            full_name="x",
            email="a@b.com",
            password="passw0rd1",
            confirm_password="passw0rd1",
        )


def test_verify_otp_requires_six_digits():
    with pytest.raises(ValidationError):
        VerifyOtpRequest(email="a@b.com", otp="12345")
    with pytest.raises(ValidationError):
        VerifyOtpRequest(email="a@b.com", otp="abcdef")
    ok = VerifyOtpRequest(email="a@b.com", otp="123456")
    assert ok.otp == "123456"


def test_setup_credentials_schema():
    with pytest.raises(ValidationError):
        SetupCredentialsRequest(
            setup_token="t", password="weak", confirm_password="weak"
        )
    ok = SetupCredentialsRequest(
        setup_token="t", password="passw0rd", confirm_password="passw0rd"
    )
    assert ok.password == "passw0rd"


def test_password_check_rules():
    assert _password_check("abc12345") == "abc12345"
    with pytest.raises(ValueError):
        _password_check("no_digits_here")
    with pytest.raises(ValueError):
        _password_check("1234567")  # too short + no letters


def test_login_request_shape():
    req = LoginRequest(username="u", password="p")
    assert req.username == "u"
