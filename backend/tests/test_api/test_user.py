"""User API tests."""

import pytest

from tests.test_api.base import BaseTestCase


class TestUserMe(BaseTestCase):
    """Tests for GET /users/me."""

    url = "/users/me"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful request returns current user data."""
        user, headers = await self.create_user_and_get_token()

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(data, {"id", "email", "created_at", "updated_at"})
        if data["id"] != user["id"]:
            pytest.fail("Response id did not match user id")
        if data["email"] != user["email"]:
            pytest.fail("Response email did not match user email")


class TestUserMeDelete(BaseTestCase):
    """Tests for DELETE /users/me."""

    url = "/users/me"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful request deletes the current user."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.delete(url=self.url, headers=headers)

        await self.assert_response_ok(response=response)
