"""LLM provider API tests."""

import secrets
import uuid
from http import HTTPStatus

import pytest

from enums import LLMProviderType
from tests.factories import LLMProviderFactory, UserFactory
from tests.test_api.base import BaseTestCase


class TestLLMProviderCreate(BaseTestCase):
    """Tests for POST /llm-providers."""

    url = "/llm-providers"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful creation returns provider data."""
        user, headers = await self.create_user_and_get_token()
        payload = {
            "name": f"provider-{uuid.uuid4().hex[:8]}",
            "type": LLMProviderType.OLLAMA,
            "api_key": secrets.token_urlsafe(18),
            "base_url": "https://example.com",
            "is_default": True,
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "user_id", "name", "type", "base_url", "is_default"},
        )
        if data["name"] != payload["name"]:
            pytest.fail("Provider name did not match request")
        if data["type"] != payload["type"]:
            pytest.fail("Provider type did not match request")
        if data["user_id"] != user["id"]:
            pytest.fail("Provider user_id did not match current user")
        if "api_key" in data:
            pytest.fail("Provider response must not include api_key")


class TestLLMProviderList(BaseTestCase):
    """Tests for GET /llm-providers."""

    url = "/llm-providers"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """List returns providers for the current user only."""
        user, headers = await self.create_user_and_get_token()
        other = await UserFactory.create_async(session=self.session)

        first = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        second = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        other_provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=other.id
        )

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        ids = {item.get("id") for item in data}
        if first.id not in ids or second.id not in ids:
            pytest.fail("Expected providers to appear in list")
        if other_provider.id in ids:
            pytest.fail("Unexpected provider from another user in list")


class TestLLMProviderGet(BaseTestCase):
    """Tests for GET /llm-providers/{provider_id}."""

    url = "/llm-providers"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful request returns provider data."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )

        response = await self.client.get(
            url=f"{self.url}/{provider.id}",
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["id"] != provider.id:
            pytest.fail("Provider id did not match")


class TestLLMProviderUpdate(BaseTestCase):
    """Tests for PATCH /llm-providers/{provider_id}."""

    url = "/llm-providers"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful update returns updated provider data."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )
        new_name = f"provider-{uuid.uuid4().hex[:8]}"

        response = await self.client.patch(
            url=f"{self.url}/{provider.id}",
            json={"name": new_name, "is_default": True},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != new_name:
            pytest.fail("Provider name was not updated")
        if data["is_default"] is not True:
            pytest.fail("Provider is_default was not updated")


class TestLLMProviderDelete(BaseTestCase):
    """Tests for DELETE /llm-providers/{provider_id}."""

    url = "/llm-providers"

    @pytest.mark.asyncio
    async def test_ok(self) -> None:
        """Successful delete removes the provider."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"]
        )

        response = await self.client.delete(
            url=f"{self.url}/{provider.id}",
            headers=headers,
        )

        await self.assert_response_ok(response=response)

        fetch = await self.client.get(
            url=f"{self.url}/{provider.id}",
            headers=headers,
        )
        if fetch.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected deleted provider to return 404")
