"""LLM provider API tests."""

import uuid
from http import HTTPStatus

import pytest

from db.repositories import LLMProviderRepository
from enums import LLMProviderType
from tests.factories import LLMProviderFactory, UserFactory
from tests.test_api.base import BaseTestCase
from utils.encryption import decrypt


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
            "base_url": "http://localhost:11434",
            "config": {"timeout": 5},
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        data = await self.assert_response_dict(response=response)
        self.assert_has_keys(
            data,
            {"id", "user_id", "name", "type", "base_url"},
        )
        if data["name"] != payload["name"]:
            pytest.fail("Provider name did not match request")
        if data["type"] != payload["type"]:
            pytest.fail("Provider type did not match request")
        if data["user_id"] != user["id"]:
            pytest.fail("Provider user_id did not match current user")
        if data["config"] != payload["config"]:
            pytest.fail("Provider config did not match request")

    @pytest.mark.asyncio
    async def test_api_key_stored_encrypted_and_not_returned(self) -> None:
        """A provided API key is encrypted at rest and never returned."""
        _, headers = await self.create_user_and_get_token()
        plaintext = "sk-super-secret-key"
        payload = {
            "name": f"provider-{uuid.uuid4().hex[:8]}",
            "type": LLMProviderType.OLLAMA,
            "base_url": "http://localhost:11434",
            "api_key": plaintext,
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        data = await self.assert_response_dict(response=response)
        if "api_key" in data:
            pytest.fail("API key must never appear in the response")

        stored = await LLMProviderRepository().get_by(
            session=self.session, id=data["id"]
        )
        if stored is None or stored.api_key is None:
            pytest.fail("Expected the provider to persist an API key")
        elif stored.api_key == plaintext:
            pytest.fail("API key must be stored encrypted, not as plaintext")
        elif decrypt(stored.api_key) != plaintext:
            pytest.fail("Stored API key must decrypt back to the original value")

    @pytest.mark.asyncio
    async def test_oversized_config_rejected(self) -> None:
        """A config dict that serializes too large is rejected."""
        _, headers = await self.create_user_and_get_token()
        payload = {
            "name": f"provider-{uuid.uuid4().hex[:8]}",
            "type": LLMProviderType.OLLAMA,
            "base_url": "http://localhost:11434",
            "config": {"blob": "x" * 10_000},
        }

        response = await self.client.post(url=self.url, json=payload, headers=headers)

        if response.status_code != HTTPStatus.UNPROCESSABLE_ENTITY:
            pytest.fail(f"Expected a validation error, got {response.status_code}")

    @pytest.mark.asyncio
    async def test_duplicate_name_rejected(self) -> None:
        """Creating two providers with the same name for one user returns 409."""
        _, headers = await self.create_user_and_get_token()
        payload = {
            "name": f"provider-{uuid.uuid4().hex[:8]}",
            "type": LLMProviderType.OLLAMA,
            "base_url": "http://localhost:11434",
        }

        first_response = await self.client.post(
            url=self.url, json=payload, headers=headers
        )
        await self.assert_response_dict(response=first_response)

        second_response = await self.client.post(
            url=self.url, json=payload, headers=headers
        )

        if second_response.status_code != HTTPStatus.CONFLICT:
            pytest.fail(
                f"Expected 409 for a duplicate name, got {second_response.status_code}"
            )


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
            json={"name": new_name},
            headers=headers,
        )

        data = await self.assert_response_dict(response=response)
        if data["name"] != new_name:
            pytest.fail("Provider name was not updated")


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
            url=self.url,
            headers=headers,
        )
        data = await self.assert_response_list(response=fetch)
        ids = {item.get("id") for item in data}
        if provider.id in ids:
            pytest.fail("Expected deleted provider to not appear in list")


class TestLLMProviderModelCatalog(BaseTestCase):
    """Tests for GET /llm-providers/model-catalog."""

    url = "/llm-providers/model-catalog"

    @pytest.mark.asyncio
    async def test_returns_curated_entries(self) -> None:
        """The catalog returns a non-empty list of model families and tags."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.get(url=self.url, headers=headers)

        data = await self.assert_response_list(response=response)
        if not data:
            pytest.fail("Expected a non-empty catalog")
        first = data[0]
        self.assert_has_keys(first, {"name", "description", "tags"})
        if not first["tags"]:
            pytest.fail("Expected each catalog entry to have at least one tag")
        self.assert_has_keys(first["tags"][0], {"tag", "size_gb", "params"})


class TestLLMProviderModelPull(BaseTestCase):
    """Tests for POST /llm-providers/{provider_id}/models."""

    @pytest.mark.asyncio
    async def test_enqueues_pull_job(self) -> None:
        """Pulling a model on an Ollama provider returns 202 with a job id."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"], type=LLMProviderType.OLLAMA
        )

        response = await self.client.post(
            url=f"/llm-providers/{provider.id}/models",
            json={"model": "llama3.2:1b"},
            headers=headers,
        )

        if response.status_code != HTTPStatus.ACCEPTED:
            pytest.fail("Expected a 202 Accepted for a queued pull")
        data = await self.assert_response_dict(response=response)
        if not data["job_id"] or data["model"] != "llama3.2:1b":
            pytest.fail("Expected a job id and the pulled model in the response")

    @pytest.mark.asyncio
    async def test_non_ollama_provider_rejected(self) -> None:
        """Pulling on a non-Ollama provider is rejected."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session,
            user_id=user["id"],
            type=LLMProviderType.OPENAI,
            api_key="encrypted-placeholder",
        )

        response = await self.client.post(
            url=f"/llm-providers/{provider.id}/models",
            json={"model": "gpt-4o-mini"},
            headers=headers,
        )

        if response.status_code != HTTPStatus.NOT_IMPLEMENTED:
            pytest.fail("Expected pulling on a non-Ollama provider to be rejected")

    @pytest.mark.asyncio
    async def test_unknown_provider_404s(self) -> None:
        """Pulling on a provider that doesn't exist returns 404."""
        _, headers = await self.create_user_and_get_token()

        response = await self.client.post(
            url="/llm-providers/999999/models",
            json={"model": "llama3.2:1b"},
            headers=headers,
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected a 404 for an unknown provider")


class TestLLMProviderModelPullStream(BaseTestCase):
    """Tests for GET /llm-providers/{provider_id}/models/pull/{job_id}/stream."""

    @pytest.mark.asyncio
    async def test_streams_terminal_snapshot(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pre-existing terminal snapshot is streamed and the frame closes."""

        async def _fake_snapshot(pool: object, job_id: str) -> dict:
            del pool, job_id
            return {"status": "success", "percent": 100, "done": True}

        monkeypatch.setattr(
            "api.routers.llm_provider.read_pull_snapshot", _fake_snapshot
        )
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"], type=LLMProviderType.OLLAMA
        )

        response = await self.client.get(
            url=f"/llm-providers/{provider.id}/models/pull/some-job/stream",
            headers=headers,
        )

        if response.status_code != HTTPStatus.OK:
            pytest.fail("Stream request should return OK")
        if not response.headers["content-type"].startswith("text/event-stream"):
            pytest.fail("Stream should use the SSE content type")
        if "data:" not in response.text or "success" not in response.text:
            pytest.fail("Stream should emit the terminal success frame")

    @pytest.mark.asyncio
    async def test_other_user_cannot_stream(self) -> None:
        """A stream for another user's provider is rejected before streaming."""
        owner, _ = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=owner["id"], type=LLMProviderType.OLLAMA
        )
        _, other_headers = await self.create_user_and_get_token()

        response = await self.client.get(
            url=f"/llm-providers/{provider.id}/models/pull/some-job/stream",
            headers=other_headers,
        )

        if response.status_code != HTTPStatus.NOT_FOUND:
            pytest.fail("Expected NOT_FOUND streaming another user's provider")


class TestLLMProviderModelDelete(BaseTestCase):
    """Tests for DELETE /llm-providers/{provider_id}/models."""

    @pytest.mark.asyncio
    async def test_deletes_model(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Deleting a model calls the Ollama client and returns 202."""
        captured: list[str] = []

        class _StubOllamaClient:
            """Ollama client stub recording the deleted model name."""

            def __init__(self, *args: object, **kwargs: object) -> None:
                """Accept any constructor args."""
                del args, kwargs

            async def delete_model(self, model: str) -> None:
                """Record the deleted model name."""
                captured.append(model)

        monkeypatch.setattr("usecases.llm_provider.OllamaClient", _StubOllamaClient)
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session, user_id=user["id"], type=LLMProviderType.OLLAMA
        )

        response = await self.client.request(
            method="DELETE",
            url=f"/llm-providers/{provider.id}/models",
            params={"model": "llama3.2:1b"},
            headers=headers,
        )

        await self.assert_response_ok(response=response)
        if captured != ["llama3.2:1b"]:
            pytest.fail("Expected the Ollama client to delete the given model")

    @pytest.mark.asyncio
    async def test_non_ollama_provider_rejected(self) -> None:
        """Deleting a model on a non-Ollama provider is rejected."""
        user, headers = await self.create_user_and_get_token()
        provider = await LLMProviderFactory.create_async(
            session=self.session,
            user_id=user["id"],
            type=LLMProviderType.OPENAI,
            api_key="encrypted-placeholder",
        )

        response = await self.client.request(
            method="DELETE",
            url=f"/llm-providers/{provider.id}/models",
            params={"model": "gpt-4o-mini"},
            headers=headers,
        )

        if response.status_code != HTTPStatus.NOT_IMPLEMENTED:
            pytest.fail("Expected deleting on a non-Ollama provider to be rejected")
