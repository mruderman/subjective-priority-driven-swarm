"""
Unit tests for integrations registry and external tools functionality.
"""

import json
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from spds.integrations.composio import ComposioProvider
from spds.integrations.mcp import MCPProvider
from spds.integrations.registry import Registry, ToolDescriptor, get_registry
from spds.tools import get_external_tool_functions, load_and_register_external_tools


class TestRegistry:
    """Test cases for the integrations registry."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = Registry()
        assert registry.list_providers() == []
        assert registry.list_tools() == {}

    def test_register_provider(self):
        """Test provider registration."""
        registry = Registry()

        # Create a mock provider
        mock_provider = Mock()
        mock_provider.provider_name.return_value = "test_provider"
        mock_provider.discover.return_value = []

        # Register provider
        registry.register(mock_provider)

        assert "test_provider" in registry.list_providers()
        assert len(registry.list_providers()) == 1

    def test_register_duplicate_provider_raises_error(self):
        """Test that registering duplicate provider raises ValueError."""
        registry = Registry()

        # Create a mock provider
        mock_provider = Mock()
        mock_provider.provider_name.return_value = "test_provider"
        mock_provider.discover.return_value = []

        # Register provider
        registry.register(mock_provider)

        # Try to register same provider again
        with pytest.raises(
            ValueError, match="Provider 'test_provider' is already registered"
        ):
            registry.register(mock_provider)

    def test_discover_tools(self):
        """Test tool discovery."""
        registry = Registry()

        # Create a mock provider with tools
        mock_provider = Mock()
        mock_provider.provider_name.return_value = "test_provider"

        tool1 = ToolDescriptor(name="tool1", description="Test tool 1")
        tool2 = ToolDescriptor(name="tool2", description="Test tool 2")
        mock_provider.discover.return_value = [tool1, tool2]

        # Register provider
        registry.register(mock_provider)

        # Discover tools
        tools = registry.list_tools()

        assert len(tools) == 2
        assert "test_provider.tool1" in tools
        assert "test_provider.tool2" in tools
        assert tools["test_provider.tool1"].name == "tool1"
        assert tools["test_provider.tool2"].name == "tool2"

    def test_run_tool(self):
        """Test tool execution."""
        registry = Registry()

        # Create a mock provider
        mock_provider = Mock()
        mock_provider.provider_name.return_value = "test_provider"

        tool = ToolDescriptor(name="test_tool", description="Test tool")
        mock_provider.discover.return_value = [tool]
        mock_provider.run.return_value = {"result": "success"}

        # Register provider
        registry.register(mock_provider)

        # Run tool
        result = registry.run("test_provider.test_tool", {"arg": "value"})

        assert result == {"result": "success"}
        mock_provider.run.assert_called_once_with("test_tool", {"arg": "value"})

    def test_run_nonexistent_tool_raises_keyerror(self):
        """Test that running nonexistent tool raises KeyError."""
        registry = Registry()

        with pytest.raises(KeyError, match="Provider 'nonexistent' not found"):
            registry.run("nonexistent.tool")

    def test_run_tool_with_invalid_name_raises_keyerror(self):
        """Test that running tool with invalid name raises KeyError."""
        registry = Registry()

        with pytest.raises(KeyError, match="Invalid tool name"):
            registry.run("invalid_tool_name")

    def test_provider_discovery_error_handling(self):
        """Test that provider discovery errors are handled gracefully."""
        registry = Registry()

        # Create a mock provider that raises an exception during discovery
        mock_provider = Mock()
        mock_provider.provider_name.return_value = "failing_provider"
        mock_provider.discover.side_effect = Exception("Discovery failed")

        # Register provider
        registry.register(mock_provider)

        # Discover tools should not raise, but log warning
        tools = registry.list_tools()
        assert tools == {}  # No tools should be returned

    def test_tool_run_error_handling(self):
        """Test that tool execution errors are handled gracefully."""
        registry = Registry()

        # Create a mock provider that raises an exception during run
        mock_provider = Mock()
        mock_provider.provider_name.return_value = "test_provider"

        tool = ToolDescriptor(name="failing_tool", description="Test tool")
        mock_provider.discover.return_value = [tool]
        mock_provider.run.side_effect = Exception("Tool execution failed")

        # Register provider
        registry.register(mock_provider)

        # Run tool should raise RuntimeError
        with pytest.raises(RuntimeError, match="Tool execution failed"):
            registry.run("test_provider.failing_tool")

    def test_get_registry_singleton(self):
        """Test that get_registry returns a singleton."""
        registry1 = get_registry()
        registry2 = get_registry()

        assert registry1 is registry2

    def test_tool_descriptor_creation(self):
        """Test ToolDescriptor dataclass."""
        descriptor = ToolDescriptor(
            name="test_tool",
            description="A test tool",
            input_schema={"type": "object"},
            output_schema={"type": "string"},
        )

        assert descriptor.name == "test_tool"
        assert descriptor.description == "A test tool"
        assert descriptor.input_schema == {"type": "object"}
        assert descriptor.output_schema == {"type": "string"}


class TestMCPProvider:
    """Test cases for MCP provider."""

    def test_mcp_provider_initialization(self):
        """Test MCP provider initialization."""
        provider = MCPProvider()
        assert provider.provider_name() == "mcp"

    def test_mcp_provider_discover_without_fake_providers(self):
        """Test MCP provider discovery without fake providers."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=False
        ):
            provider = MCPProvider()
            tools = provider.discover()
            assert tools == []

    def test_mcp_provider_discover_with_fake_providers(self):
        """Test MCP provider discovery with fake providers enabled."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=True
        ):
            provider = MCPProvider()
            tools = provider.discover()
            assert len(tools) == 2
            assert any(tool.name == "translate" for tool in tools)
            assert any(tool.name == "search" for tool in tools)

    def test_mcp_provider_run_without_fake_providers(self):
        """Test MCP provider run without fake providers."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=False
        ):
            provider = MCPProvider()
            with pytest.raises(RuntimeError, match="MCP SDK not available"):
                provider.run("translate", {"text": "hello"})

    def test_mcp_provider_run_with_fake_providers(self):
        """Test MCP provider run with fake providers enabled."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=True
        ):
            provider = MCPProvider()

            # Test translate tool
            result = provider.run(
                "translate", {"text": "hello", "target_language": "es"}
            )
            assert "translated" in result["translated_text"]
            assert result["source_language"] == "en"

            # Test search tool
            result = provider.run("search", {"query": "test"})
            assert len(result["results"]) == 2
            assert result["count"] == 2

    def test_mcp_provider_run_nonexistent_tool(self):
        """Test MCP provider run with nonexistent tool."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=True
        ):
            provider = MCPProvider()
            with pytest.raises(KeyError, match="Fake MCP tool 'nonexistent' not found"):
                provider.run("nonexistent", {})


class TestComposioProvider:
    """Test cases for Composio provider."""

    def test_composio_provider_initialization(self):
        """Test Composio provider initialization."""
        provider = ComposioProvider()
        assert provider.provider_name() == "composio"

    def test_composio_provider_discover_without_fake_providers(self):
        """Test Composio provider discovery without fake providers."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=False
        ):
            provider = ComposioProvider()
            tools = provider.discover()
            assert tools == []

    def test_composio_provider_discover_with_fake_providers(self):
        """Test Composio provider discovery with fake providers enabled."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=True
        ):
            provider = ComposioProvider()
            tools = provider.discover()
            assert len(tools) == 3
            assert any(tool.name == "github_create_issue" for tool in tools)
            assert any(tool.name == "slack_send_message" for tool in tools)
            assert any(tool.name == "gmail_send_email" for tool in tools)

    def test_composio_provider_run_without_fake_providers(self):
        """Test Composio provider run without fake providers."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=False
        ):
            provider = ComposioProvider()
            with pytest.raises(RuntimeError, match="Composio SDK not available"):
                provider.run(
                    "github_create_issue", {"repo": "test/repo", "title": "Test"}
                )

    def test_composio_provider_run_with_fake_providers(self):
        """Test Composio provider run with fake providers enabled."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=True
        ):
            provider = ComposioProvider()

            # Test GitHub create issue tool
            result = provider.run(
                "github_create_issue",
                {"repo": "test/repo", "title": "Test Issue", "body": "Test body"},
            )
            assert result["issue_number"] == 123
            assert "test/repo" in result["issue_url"]
            assert result["status"] == "created"

            # Test Slack send message tool
            result = provider.run(
                "slack_send_message", {"channel": "test-channel", "message": "Hello"}
            )
            assert result["message_id"] == "msg_123456"
            assert result["status"] == "sent"

            # Test Gmail send email tool
            result = provider.run(
                "gmail_send_email",
                {"to": "test@example.com", "subject": "Test", "body": "Hello"},
            )
            assert result["message_id"] == "msg_789"
            assert result["status"] == "sent"

    def test_composio_provider_run_nonexistent_tool(self):
        """Test Composio provider run with nonexistent tool."""
        with patch(
            "spds.config.get_integrations_allow_fake_providers", return_value=True
        ):
            provider = ComposioProvider()
            with pytest.raises(
                KeyError, match="Fake Composio tool 'nonexistent' not found"
            ):
                provider.run("nonexistent", {})


class TestExternalToolsLoader:
    """Test cases for external tools loader functionality."""

    def test_get_external_tool_functions_disabled(self):
        """Test get_external_tool_functions when integrations are disabled."""
        with patch("spds.config.get_integrations_enabled", return_value=False):
            tools = get_external_tool_functions()
            assert tools == {}

    def test_get_external_tool_functions_enabled_no_providers(self):
        """Test get_external_tool_functions when integrations are enabled but no providers available."""
        with patch("spds.config.get_integrations_enabled", return_value=True):
            with patch(
                "spds.config.get_integrations_allow_fake_providers", return_value=False
            ):
                tools = get_external_tool_functions()
                assert tools == {}

    def test_get_external_tool_functions_with_fake_providers(self):
        """Test get_external_tool_functions with fake providers enabled."""
        with patch("spds.config.get_integrations_enabled", return_value=True):
            with patch(
                "spds.config.get_integrations_allow_fake_providers", return_value=True
            ):
                tools = get_external_tool_functions()

                # Should have tools from both MCP and Composio
                assert len(tools) > 0
                assert "mcp.translate" in tools
                assert "mcp.search" in tools
                assert "composio.github_create_issue" in tools
                assert "composio.slack_send_message" in tools
                assert "composio.gmail_send_email" in tools

    def test_external_tool_function_execution(self):
        """Test execution of external tool functions."""
        with patch("spds.config.get_integrations_enabled", return_value=True):
            with patch(
                "spds.config.get_integrations_allow_fake_providers", return_value=True
            ):
                tools = get_external_tool_functions()

                # Test MCP translate tool function
                translate_func = tools["mcp.translate"]
                result = translate_func('{"text": "hello", "target_language": "es"}')
                result_dict = json.loads(result)
                assert "translated" in result_dict["translated_text"]

                # Test Composio GitHub tool function
                github_func = tools["composio.github_create_issue"]
                result = github_func('{"repo": "test/repo", "title": "Test"}')
                result_dict = json.loads(result)
                assert result_dict["issue_number"] == 123
                assert result_dict["status"] == "created"

    def test_external_tool_function_plain_text_input(self):
        """Test external tool function with plain text input."""
        with patch("spds.config.get_integrations_enabled", return_value=True):
            with patch(
                "spds.config.get_integrations_allow_fake_providers", return_value=True
            ):
                tools = get_external_tool_functions()

                # Test with plain text input
                translate_func = tools["mcp.translate"]
                result = translate_func("hello world")
                result_dict = json.loads(result)
                assert "translated" in result_dict["translated_text"]

    def test_load_and_register_external_tools(self):
        """Test load_and_register_external_tools helper function."""
        mock_client = Mock()
        mock_create_fn = Mock()

        with patch("spds.tools.get_external_tool_functions") as mock_get_tools:
            # Mock external tools
            mock_tools = {
                "mcp.translate": lambda x: json.dumps({"result": "translated"}),
                "composio.github_create_issue": lambda x: json.dumps({"issue": 123}),
            }
            mock_get_tools.return_value = mock_tools

            # Call load_and_register_external_tools
            load_and_register_external_tools(mock_client, mock_create_fn)

            # Verify create_fn was called for each tool
            assert mock_create_fn.call_count == 2
            mock_create_fn.assert_any_call(
                function=mock_tools["mcp.translate"],
                name="mcp.translate",
                description="External tool from integration: mcp.translate",
            )
            mock_create_fn.assert_any_call(
                function=mock_tools["composio.github_create_issue"],
                name="composio.github_create_issue",
                description="External tool from integration: composio.github_create_issue",
            )

    def test_load_and_register_external_tools_empty(self):
        """Test load_and_register_external_tools when no external tools available."""
        mock_client = Mock()
        mock_create_fn = Mock()

        with patch("spds.tools.get_external_tool_functions", return_value={}):
            load_and_register_external_tools(mock_client, mock_create_fn)

            # create_fn should not be called
            assert not mock_create_fn.called

    def test_load_and_register_external_tools_with_errors(self):
        """Test load_and_register_external_tools when some registrations fail."""
        mock_client = Mock()
        mock_create_fn = Mock()
        mock_create_fn.side_effect = [Exception("Registration failed"), None]

        with patch("spds.tools.get_external_tool_functions") as mock_get_tools:
            # Mock external tools
            mock_tools = {
                "mcp.translate": lambda x: json.dumps({"result": "translated"}),
                "mcp.search": lambda x: json.dumps({"results": ["result1"]}),
            }
            mock_get_tools.return_value = mock_tools

            # Call load_and_register_external_tools
            load_and_register_external_tools(mock_client, mock_create_fn)

            # create_fn should be called for both tools, even if one fails
            assert mock_create_fn.call_count == 2


class TestIntegrationRegistration:
    """Test cases for integration provider registration."""

    def test_mcp_maybe_register_with(self):
        """Test MCP maybe_register_with function."""
        from spds.integrations.mcp import maybe_register_with

        registry = Registry()
        maybe_register_with(registry)

        # Should register successfully (even if SDK not available)
        assert "mcp" in registry.list_providers()

    def test_composio_maybe_register_with(self):
        """Test Composio maybe_register_with function."""
        from spds.integrations.composio import maybe_register_with

        registry = Registry()
        maybe_register_with(registry)

        # Should register successfully (even if SDK not available)
        assert "composio" in registry.list_providers()

    def test_full_integration_flow_with_fake_providers(self):
        """Test complete integration flow with fake providers enabled."""
        with patch("spds.config.get_integrations_enabled", return_value=True):
            with patch(
                "spds.config.get_integrations_allow_fake_providers", return_value=True
            ):
                # Get external tool functions
                tools = get_external_tool_functions()

                # Verify we have tools
                assert len(tools) > 0

                # Test a few tool executions
                translate_result = json.loads(
                    tools["mcp.translate"]('{"text": "hello"}')
                )
                assert "translated" in translate_result["translated_text"]

                github_result = json.loads(
                    tools["composio.github_create_issue"]('{"repo": "test/repo"}')
                )
                assert github_result["issue_number"] == 123


class TestEnvironmentConfiguration:
    """Test cases for environment variable configuration."""

    def test_get_integrations_enabled_default(self):
        """Test get_integrations_enabled default behavior."""
        from spds.config import get_integrations_enabled

        # Default should be False
        assert get_integrations_enabled() is False

    def test_get_integrations_enabled_true(self):
        """Test get_integrations_enabled when set to true."""
        from spds.config import get_integrations_enabled

        with patch.dict(os.environ, {"SPDS_ENABLE_INTEGRATIONS": "true"}):
            assert get_integrations_enabled() is True

        with patch.dict(os.environ, {"SPDS_ENABLE_INTEGRATIONS": "True"}):
            assert get_integrations_enabled() is True

    def test_get_integrations_allow_fake_providers_default(self):
        """Test get_integrations_allow_fake_providers default behavior."""
        from spds.config import get_integrations_allow_fake_providers

        # Default should be False
        assert get_integrations_allow_fake_providers() is False

    def test_get_integrations_allow_fake_providers_true(self):
        """Test get_integrations_allow_fake_providers when set to true."""
        from spds.config import get_integrations_allow_fake_providers

        with patch.dict(os.environ, {"SPDS_ALLOW_FAKE_PROVIDERS": "true"}):
            # Should log a warning
            with patch("spds.config.logger.warning") as mock_warning:
                result = get_integrations_allow_fake_providers()
                assert result is True
                assert mock_warning.called
                assert "Fake providers are enabled" in mock_warning.call_args[0][0]
