"""Tests for JSON modification hooks."""

import json

import pytest
from aiohttp import web

from python_proxy.builtin_hooks import json_modify


@pytest.fixture
def mock_response():
    """Create a mock response with JSON content type."""
    response = web.Response()
    response.headers["Content-Type"] = "application/json"
    return response


@pytest.mark.asyncio
async def test_json_modify_set_field(mock_response):
    """Test setting a new field in JSON."""
    body = json.dumps({"user": {"name": "John"}}).encode()

    params = {"path": "user.email", "action": "set", "value": "john@example.com"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["user"]["email"] == "john@example.com"
    assert data["user"]["name"] == "John"  # Original field preserved


@pytest.mark.asyncio
async def test_json_modify_set_nested_field(mock_response):
    """Test setting a nested field (creates intermediate objects)."""
    body = json.dumps({"user": {"name": "John"}}).encode()

    params = {
        "path": "user.profile.avatar",
        "action": "set",
        "value": "avatar.png",
    }

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["user"]["profile"]["avatar"] == "avatar.png"
    assert data["user"]["name"] == "John"


@pytest.mark.asyncio
async def test_json_modify_delete_field(mock_response):
    """Test deleting a field from JSON."""
    body = json.dumps({"user": {"name": "John", "password": "secret"}}).encode()

    params = {"path": "user.password", "action": "delete"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert "password" not in data["user"]
    assert data["user"]["name"] == "John"


@pytest.mark.asyncio
async def test_json_modify_delete_nested_field(mock_response):
    """Test deleting a nested field."""
    body = json.dumps(
        {"data": {"user": {"name": "John", "internal": {"token": "abc123"}}}}
    ).encode()

    params = {"path": "data.user.internal", "action": "delete"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert "internal" not in data["data"]["user"]
    assert data["data"]["user"]["name"] == "John"


@pytest.mark.asyncio
async def test_json_modify_append_to_array(mock_response):
    """Test appending to an array."""
    body = json.dumps({"tags": ["python", "web"]}).encode()

    params = {"path": "tags", "action": "append", "value": "proxy"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["tags"] == ["python", "web", "proxy"]


@pytest.mark.asyncio
async def test_json_modify_append_object_to_array(mock_response):
    """Test appending an object to an array."""
    body = json.dumps({"users": [{"name": "John"}]}).encode()

    params = {
        "path": "users",
        "action": "append",
        "value": {"name": "Jane", "role": "admin"},
    }

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert len(data["users"]) == 2
    assert data["users"][1]["name"] == "Jane"
    assert data["users"][1]["role"] == "admin"


@pytest.mark.asyncio
async def test_json_modify_append_creates_array(mock_response):
    """Test appending creates array if field doesn't exist."""
    body = json.dumps({"user": {"name": "John"}}).encode()

    params = {"path": "user.tags", "action": "append", "value": "premium"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["user"]["tags"] == ["premium"]


@pytest.mark.asyncio
async def test_json_modify_increment_counter(mock_response):
    """Test incrementing a numeric value."""
    body = json.dumps({"post": {"views": 100, "likes": 5}}).encode()

    params = {"path": "post.views", "action": "increment", "value": 1}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["post"]["views"] == 101
    assert data["post"]["likes"] == 5


@pytest.mark.asyncio
async def test_json_modify_increment_default_value(mock_response):
    """Test increment with default value of 1."""
    body = json.dumps({"counter": 10}).encode()

    params = {"path": "counter", "action": "increment"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["counter"] == 11


@pytest.mark.asyncio
async def test_json_modify_decrement(mock_response):
    """Test decrementing with negative increment."""
    body = json.dumps({"stock": 100}).encode()

    params = {"path": "stock", "action": "increment", "value": -1}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["stock"] == 99


@pytest.mark.asyncio
async def test_json_modify_array_element(mock_response):
    """Test modifying an array element."""
    body = json.dumps({"items": [{"name": "item1", "qty": 5}, {"name": "item2"}]}).encode()

    params = {"path": "items[0].qty", "action": "set", "value": 10}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["items"][0]["qty"] == 10
    assert data["items"][0]["name"] == "item1"


@pytest.mark.asyncio
async def test_json_modify_delete_array_element(mock_response):
    """Test deleting an array element."""
    body = json.dumps({"items": ["a", "b", "c"]}).encode()

    params = {"path": "items[1]", "action": "delete"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["items"] == ["a", "c"]


@pytest.mark.asyncio
async def test_json_modify_non_json_content(mock_response):
    """Test that non-JSON content is returned unchanged."""
    mock_response.headers["Content-Type"] = "text/html"
    body = b"<html><body>Not JSON</body></html>"

    params = {"path": "user.name", "action": "set", "value": "John"}

    result = await json_modify(mock_response, body, params)

    assert result == body


@pytest.mark.asyncio
async def test_json_modify_invalid_json(mock_response):
    """Test that invalid JSON is returned unchanged."""
    body = b"{invalid json}"

    params = {"path": "user.name", "action": "set", "value": "John"}

    result = await json_modify(mock_response, body, params)

    assert result == body


@pytest.mark.asyncio
async def test_json_modify_missing_path(mock_response):
    """Test that missing path parameter returns unchanged body."""
    body = json.dumps({"user": {"name": "John"}}).encode()

    params = {"action": "set", "value": "value"}

    result = await json_modify(mock_response, body, params)

    assert result == body


@pytest.mark.asyncio
async def test_json_modify_nonexistent_path(mock_response):
    """Test modifying nonexistent path (for non-set actions)."""
    body = json.dumps({"user": {"name": "John"}}).encode()

    params = {"path": "user.nonexistent.field", "action": "delete"}

    result = await json_modify(mock_response, body, params)

    # Should return original body unchanged
    assert result == body


@pytest.mark.asyncio
async def test_json_modify_complex_nested_structure(mock_response):
    """Test modifying complex nested JSON structure."""
    body = json.dumps(
        {
            "data": {
                "users": [
                    {"id": 1, "name": "John", "meta": {"active": True}},
                    {"id": 2, "name": "Jane", "meta": {"active": False}},
                ]
            }
        }
    ).encode()

    params = {"path": "data.users[1].meta.active", "action": "set", "value": True}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["data"]["users"][1]["meta"]["active"] is True
    assert data["data"]["users"][0]["meta"]["active"] is True


@pytest.mark.asyncio
async def test_json_modify_overwrite_existing_value(mock_response):
    """Test overwriting an existing value."""
    body = json.dumps({"status": "pending", "value": 100}).encode()

    params = {"path": "status", "action": "set", "value": "completed"}

    result = await json_modify(mock_response, body, params)
    data = json.loads(result)

    assert data["status"] == "completed"
    assert data["value"] == 100
