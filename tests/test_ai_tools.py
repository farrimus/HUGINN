"""Tests for AI tools registry and handlers."""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.ai_tools import ai_tools


class TestAIToolsRegistry:
    """Test tool registration and basic execution."""

    def test_get_tools_for_claude(self):
        """Tools should be registered and exportable for Claude API."""
        tools = ai_tools.get_tools_for_claude()
        assert len(tools) > 0

        # Check required tools
        tool_names = {t["name"] for t in tools}
        assert "search_memory" in tool_names
        assert "get_memory_summary" in tool_names
        assert "assess_threat" in tool_names
        assert "get_system_intel" in tool_names
        assert "get_pilot_profile" in tool_names
        assert "radius_search" in tool_names

    def test_tool_schema_structure(self):
        """Tools should have valid schema structure."""
        tools = ai_tools.get_tools_for_claude()

        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"
            assert "properties" in tool["input_schema"]

    @pytest.mark.asyncio
    async def test_execute_tool_timeout(self):
        """Tool execution should timeout gracefully."""
        # Create a fake handler that sleeps
        async def slow_handler(inputs, context):
            await asyncio.sleep(10)
            return "done"

        # Manually register a slow tool (temporarily)
        ai_tools.tools["slow_test"] = {
            "name": "slow_test",
            "category": "test",
            "description": "Test slow tool",
            "input_schema": {},
            "handler": slow_handler,
        }

        try:
            result = await ai_tools.execute_tool("slow_test", {}, context=None)
            assert "timed out" in result.lower()
        finally:
            del ai_tools.tools["slow_test"]

    @pytest.mark.asyncio
    async def test_execute_tool_missing(self):
        """Executing missing tool should return error."""
        result = await ai_tools.execute_tool("nonexistent_tool", {}, context=None)
        assert "not found" in result.lower()

    @pytest.mark.asyncio
    async def test_search_memory_no_context(self):
        """search_memory should fail gracefully without structure_id."""
        result = await asyncio.wait_for(
            ai_tools.execute_tool("search_memory", {"keyword": "test"}, context=None),
            timeout=5
        )
        assert "requires structure_id" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_get_memory_summary_no_context(self):
        """get_memory_summary should fail gracefully without structure_id."""
        result = await asyncio.wait_for(
            ai_tools.execute_tool("get_memory_summary", {}, context=None),
            timeout=5
        )
        assert "requires structure_id" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_assess_threat_no_context(self):
        """assess_threat should fail gracefully without system_id."""
        result = await asyncio.wait_for(
            ai_tools.execute_tool("assess_threat", {}, context=None),
            timeout=5
        )
        assert "requires system_id" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_get_system_intel_no_context(self):
        """get_system_intel should fail gracefully without system_id."""
        result = await asyncio.wait_for(
            ai_tools.execute_tool("get_system_intel", {}, context=None),
            timeout=5
        )
        assert "requires system_id" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_get_pilot_profile_no_context(self):
        """get_pilot_profile should fail gracefully without structure_id."""
        result = await asyncio.wait_for(
            ai_tools.execute_tool("get_pilot_profile", {}, context=None),
            timeout=5
        )
        assert "requires structure_id" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_radius_search_no_center(self):
        """radius_search should fail gracefully without center_system."""
        result = await asyncio.wait_for(
            ai_tools.execute_tool("radius_search", {"radius_ly": 100}, context=None),
            timeout=5
        )
        assert "requires center_system" in result or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_radius_search_invalid_radius(self):
        """radius_search should fail gracefully with invalid radius."""
        result = await asyncio.wait_for(
            ai_tools.execute_tool("radius_search", {"center_system": "UR8-K7K", "radius_ly": -10}, context=None),
            timeout=5
        )
        assert "must be > 0" in result or "error" in result.lower()
