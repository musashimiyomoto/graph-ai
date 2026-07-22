"""Channel catalog API tests."""

import pytest

from enums import ExecutionSource
from tests.test_api.base import BaseTestCase


class TestChannelCatalog(BaseTestCase):
    """Tests for ``GET /channels/catalog``."""

    async def test_catalog_exposes_metadata_and_capabilities(self) -> None:
        """Clients receive every channel, settings section, and adapter contract."""
        response = await self.client.get("/channels/catalog")
        data = await self.assert_response_list(response=response)
        if {item["source"] for item in data} != {
            source.value for source in ExecutionSource
        }:
            pytest.fail("Channel catalog does not cover every execution source")

        by_source = {item["source"]: item for item in data}
        telegram = by_source[ExecutionSource.TELEGRAM.value]
        if telegram["capabilities"] != {
            "receive": True,
            "acknowledge": True,
            "deliver": True,
        }:
            pytest.fail("Telegram adapter capabilities are incomplete")
        if telegram["settings"]["component_key"] != "telegram":
            pytest.fail("Telegram settings metadata is missing")

        webhook = by_source[ExecutionSource.WEBHOOK.value]
        if webhook["capabilities"]["acknowledge"]:
            pytest.fail("Push webhooks must not advertise cursor acknowledgement")
        if webhook["output_fields"][0]["name"] != "webhook_url":
            pytest.fail("Webhook Output fields did not come from its plugin")
