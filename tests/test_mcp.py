import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest

from campus_assistant.api import create_app
from campus_assistant.config import Config
from campus_assistant.models import ItemIn
from campus_assistant.mcp_server import Backend, create_mcp
from campus_assistant.store import Store


def test_mcp_tools_scope_pagination_and_freshness(tmp_path):
    cfg = Config(data_dir=tmp_path)
    store = Store(cfg.db_path)
    for source in ("outlook", "brightspace:splms", "brightspace:lms"):
        store.upsert(ItemIn(source=source, kind="course", external_id="1", title="Test course",
                            data={"raw": {"secret": "hidden"}, "meta": {"path": "/private"}}))
    store.set_meta("brightspace:last_sync", {"errors": ["needs attention"]})
    app = create_app(cfg, store, schedule=False, analyze=False)
    server = create_mcp(Backend("http://test", httpx.ASGITransport(app=app)))

    async def call(name, args):
        result = await server.call_tool(name, args)
        return result[1] if isinstance(result, tuple) else json.loads(result[0].text)

    async def scenario():
        tools = await server.list_tools()
        assert len(tools) == 6
        assert all(t.annotations.readOnlyHint and not t.annotations.destructiveHint for t in tools)
        result = await call("list_courses", {"limit": 1})
        assert result["next_offset"] == 1
        assert len(result["items"]) == 1
        assert result["items"][0]["data"] == {}
        assert result["freshness"]["last_sync"]["errors"] == ["needs attention"]
        second = await call("list_courses", {"limit": 1, "offset": 1})
        assert second["next_offset"] is None
        assert second["items"][0]["id"] != result["items"][0]["id"]
        found = await call("search_items", {"query": "Test"})
        assert len(found["items"]) == 2
        detail = await call("get_item", {"item_id": found["items"][0]["id"]})
        assert "raw" not in str(detail["item"])
        changes = await call("recent_changes", {"since": "2000-01-01T00:00:00Z"})
        assert len(changes["items"]) == 2
        assert all(r["source"].startswith("brightspace:") for r in changes["items"])
        for name, args in [("get_item", {"item_id": "outlook:course:1"}),
                           ("get_item", {"item_id": "brightspace:../settings"}),
                           ("list_courses", {"limit": 0}),
                           ("recent_changes", {"since": "2026-01-01"})]:
            with pytest.raises(Exception):
                await call(name, args)
        due = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        for source in ("outlook", "brightspace:splms"):
            store.upsert(ItemIn(source=source, kind="assignment", external_id="2", title="Due", due_at=due))
        upcoming = await call("upcoming_deadlines", {})
        assert len(upcoming["items"]) == 1
    asyncio.run(scenario())


def test_incomplete_fetch_never_becomes_complete_list():
    from campus_assistant.brightspace.client import BrightspaceClient
    async def scenario():
        client = BrightspaceClient(None, "test")
        pages = iter([{"Objects": [{"Id": 1}], "Next": "/page2"}, None])
        async def get(*args, **kwargs):
            return next(pages)
        client.get_json = get
        assert await client.quizzes("1") is None
        pages = iter([{"Items": [], "PagingInfo": {"HasMoreItems": True, "Bookmark": "2"}}, None])
        with pytest.raises(RuntimeError, match="incomplete"):
            await client.my_courses()
    asyncio.run(scenario())


def test_sync_start_failure_is_persisted(tmp_path, monkeypatch):
    from campus_assistant import runner
    async def fail(*args):
        raise RuntimeError("browser unavailable")
    monkeypatch.setattr(runner, "sync_brightspace", fail)
    store = Store(tmp_path / "test.db")
    run = runner.BrightspaceRunner(store, Config(data_dir=tmp_path))
    result = asyncio.run(run.sync())
    assert result.errors == ["Sync failed: browser unavailable"]
    assert store.get_meta("brightspace:last_sync")["finished_at"]
    assert run.auth()["state"] == "unknown"
    assert run.activity is None
