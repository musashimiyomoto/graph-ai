"""Saved PostgreSQL connection API tests."""

import pytest

from db.repositories import PostgresConnectionRepository
from tests.test_api.base import BaseTestCase
from utils.encryption import decrypt


class TestPostgresConnectionApi(BaseTestCase):
    """Connection creation, secrecy, listing, and deletion."""

    url = "/postgres-connections"

    async def test_create_encrypts_dsn_and_never_returns_it(self) -> None:
        """The DSN is write-only and encrypted at rest."""
        _, headers = await self.create_user_and_get_token()
        dsn = "postgresql://user:secret@localhost:5432/app"
        response = await self.client.post(
            self.url, json={"name": "App DB", "dsn": dsn}, headers=headers
        )
        data = await self.assert_response_dict(response=response)
        if "dsn" in data:
            pytest.fail("PostgreSQL DSN must never be returned")
        stored = await PostgresConnectionRepository().get_by(
            session=self.session, id=data["id"]
        )
        if stored is None:
            pytest.fail("Connection was not persisted")
        elif stored.dsn == dsn or decrypt(stored.dsn) != dsn:
            pytest.fail("Connection DSN was not encrypted correctly")

    async def test_list_and_delete_are_owner_scoped(self) -> None:
        """An account sees and deletes only its own saved connections."""
        user, headers = await self.create_user_and_get_token()
        created = await PostgresConnectionRepository().create(
            session=self.session,
            data={"user_id": user["id"], "name": "Warehouse", "dsn": "encrypted"},
        )
        await self.session.commit()
        response = await self.client.get(self.url, headers=headers)
        data = await self.assert_response_list(response=response)
        if [item["id"] for item in data] != [created.id]:
            pytest.fail("Connection list did not contain the owned connection")
        delete_response = await self.client.delete(
            f"{self.url}/{created.id}", headers=headers
        )
        await self.assert_response_ok(response=delete_response)
        if (
            await PostgresConnectionRepository().get_by(
                session=self.session, id=created.id
            )
            is not None
        ):
            pytest.fail("Connection was not deleted")
