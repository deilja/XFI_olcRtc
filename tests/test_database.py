import asyncio
import os
import tempfile


def test_database_and_port_allocation():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["DB_PATH"] = os.path.join(tmp, "test.sqlite")
        os.environ["PORT_RANGE_START"] = "25000"
        os.environ["PORT_RANGE_END"] = "25002"

        import database

        async def run():
            await database.init_db()
            async with database.async_session() as session:
                user = await database.get_or_create_user(session, 123)
                assert user.id == 123
                assert user.balance == 0.0
                port = await database.get_free_port(session)
                assert port == 25000

        asyncio.run(run())
