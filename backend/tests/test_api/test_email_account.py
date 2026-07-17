"""Email account API tests."""

import pytest
from fastapi import status

from db.repositories import EmailAccountRepository
from tests.factories import EmailAccountFactory, UserFactory
from tests.test_api.base import BaseTestCase
from utils.encryption import decrypt


def _payload() -> dict[str, object]:
    """Build a valid email account payload."""
    return {
        "name": "Support inbox",
        "email_address": "support@example.com",
        "username": "support@example.com",
        "password": "app-password",
        "imap_host": "imap.example.com",
        "imap_port": 993,
        "imap_use_ssl": True,
        "smtp_host": "smtp.example.com",
        "smtp_port": 587,
        "smtp_use_tls": True,
        "smtp_use_ssl": False,
    }


class TestEmailAccountCreate(BaseTestCase):
    """Tests for POST /email-accounts."""

    url = "/email-accounts"

    async def test_encrypts_password_and_omits_it_from_response(self) -> None:
        """Credentials are encrypted at rest and write-only over the API."""
        user, headers = await self.create_user_and_get_token()
        payload = _payload()
        response = await self.client.post(self.url, json=payload, headers=headers)
        data = await self.assert_response_dict(response=response)

        if data["user_id"] != user["id"] or data["name"] != payload["name"]:
            pytest.fail("Created account did not match the request")
        if "password" in data:
            pytest.fail("Email password must never be returned")
        stored = await EmailAccountRepository().get_by(
            session=self.session, id=data["id"]
        )
        if stored is None:
            pytest.fail("Expected the email account to persist")
            return
        if stored.password == payload["password"]:
            pytest.fail("Email password was not stored encrypted")
        if decrypt(stored.password) != payload["password"]:
            pytest.fail("Encrypted password did not round-trip")

    async def test_rejects_conflicting_smtp_security_modes(self) -> None:
        """Implicit TLS and STARTTLS cannot be active together."""
        _, headers = await self.create_user_and_get_token()
        payload = _payload() | {"smtp_use_ssl": True}
        response = await self.client.post(self.url, json=payload, headers=headers)
        if response.status_code != status.HTTP_422_UNPROCESSABLE_CONTENT:
            pytest.fail(f"Expected 422, got {response.status_code}")


class TestEmailAccountListDelete(BaseTestCase):
    """Tests for email account ownership and deletion."""

    url = "/email-accounts"

    async def test_list_is_scoped_to_current_user(self) -> None:
        """Accounts owned by another user are not listed."""
        user, headers = await self.create_user_and_get_token()
        other = await UserFactory.create_async(session=self.session)
        mine = await EmailAccountFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        theirs = await EmailAccountFactory.create_async(
            session=self.session, user_id=other.id
        )
        response = await self.client.get(self.url, headers=headers)
        data = await self.assert_response_list(response=response)
        ids = {item["id"] for item in data}
        if mine.id not in ids or theirs.id in ids:
            pytest.fail("Email account list was not owner-scoped")

    async def test_delete_removes_owned_account(self) -> None:
        """An owner can delete their account."""
        user, headers = await self.create_user_and_get_token()
        account = await EmailAccountFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        response = await self.client.delete(f"{self.url}/{account.id}", headers=headers)
        await self.assert_response_ok(response=response)
        stored = await EmailAccountRepository().get_by(
            session=self.session, id=account.id
        )
        if stored is not None:
            pytest.fail("Deleted email account still exists")
