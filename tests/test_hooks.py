"""Tests for hooks module."""

import tempfile
from pathlib import Path

import pytest

from python_proxy.hooks import HookManager, after_response, before_request


def test_hook_manager_no_directory():
    """Test hook manager with no directory."""
    manager = HookManager()
    manager.load_hooks()
    assert len(manager.before_request_hooks) == 0
    assert len(manager.after_response_hooks) == 0


def test_hook_manager_empty_directory():
    """Test hook manager with empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = HookManager(tmpdir)
        manager.load_hooks()
        assert len(manager.before_request_hooks) == 0
        assert len(manager.after_response_hooks) == 0


def test_hook_manager_loads_hooks():
    """Test hook manager loads hooks from files."""
    hook_code = '''
async def before_request(request, request_data):
    return request_data

async def after_response(response, body):
    return body
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        hook_file = Path(tmpdir) / "test_hook.py"
        hook_file.write_text(hook_code)

        manager = HookManager(tmpdir)
        manager.load_hooks()

        assert len(manager.before_request_hooks) == 1
        assert len(manager.after_response_hooks) == 1


def test_hook_manager_ignores_private_files():
    """Test hook manager ignores files starting with underscore."""
    hook_code = '''
async def before_request(request, request_data):
    return request_data
'''
    with tempfile.TemporaryDirectory() as tmpdir:
        hook_file = Path(tmpdir) / "_private.py"
        hook_file.write_text(hook_code)

        manager = HookManager(tmpdir)
        manager.load_hooks()

        assert len(manager.before_request_hooks) == 0


def test_hook_decorators():
    """Test hook decorators mark functions correctly."""
    @before_request
    def my_before_hook(request, data):
        return data

    @after_response
    def my_after_hook(response, body):
        return body

    assert hasattr(my_before_hook, "_before_request_hook")
    assert my_before_hook._before_request_hook is True

    assert hasattr(my_after_hook, "_after_response_hook")
    assert my_after_hook._after_response_hook is True


@pytest.mark.asyncio
async def test_execute_before_request():
    """Test executing before_request hooks."""
    async def hook1(request, data):
        data["modified"] = True
        return data

    async def hook2(request, data):
        data["count"] = data.get("count", 0) + 1
        return data

    manager = HookManager()
    manager.before_request_hooks = [hook1, hook2]

    request_data = {"url": "http://example.com"}
    result = await manager.execute_before_request(None, request_data)

    assert result["modified"] is True
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_execute_after_response():
    """Test executing after_response hooks."""
    async def hook1(response, body):
        return body.replace(b"old", b"new")

    async def hook2(response, body):
        return body.upper()

    manager = HookManager()
    manager.after_response_hooks = [hook1, hook2]

    body = b"old text"
    result = await manager.execute_after_response(None, body)

    assert result == b"NEW TEXT"
