"""
Integrations Registry for dynamically exposing third-party tool providers.

This module provides a registry system that can dynamically expose third-party
tool providers (e.g., MCP, Composio) as callable functions that our existing
tool system can register and use. All code uses only Python stdlib to avoid
hard dependencies.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


logger = logging.getLogger(__name__)


@dataclass
class ToolDescriptor:
    """Descriptor for a tool provided by an integration.
    
    Attributes:
        name: The name of the tool
        description: Human-readable description of what the tool does
        input_schema: Optional JSON schema for input validation
        output_schema: Optional JSON schema for output validation
    """
    name: str
    description: str
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None


class ToolProvider(Protocol):
    """Protocol for tool providers that can be registered with the registry.
    
    This is a Protocol (structural typing) rather than an ABC to allow
    more flexible implementation while still providing type safety.
    """
    
    def provider_name(self) -> str:
        """Return the name of this provider (e.g., 'mcp', 'composio')."""
        ...
    
    def discover(self) -> List[ToolDescriptor]:
        """Discover and return a list of available tools from this provider."""
        ...
    
    def run(self, tool_name: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Run a specific tool with the given arguments.
        
        Args:
            tool_name: The name of the tool to run
            args: Optional dictionary of arguments for the tool
            
        Returns:
            The result from running the tool, typically a dict or string
            
        Raises:
            KeyError: If the tool_name is not found
            RuntimeError: If the tool execution fails
        """
        ...


class Registry:
    """Registry for managing tool providers and their tools.
    
    This registry allows dynamic registration of tool providers and provides
    a unified interface to discover and run tools from different providers.
    """
    
    def __init__(self):
        self._providers: Dict[str, ToolProvider] = {}
        self._tools: Dict[str, ToolDescriptor] = {}  # Fully qualified names
    
    def register(self, provider: ToolProvider) -> None:
        """Register a tool provider with the registry.
        
        Args:
            provider: The tool provider to register
            
        Raises:
            ValueError: If a provider with the same name is already registered
        """
        provider_name = provider.provider_name()
        if provider_name in self._providers:
            raise ValueError(f"Provider '{provider_name}' is already registered")
        
        self._providers[provider_name] = provider
        logger.info(f"Registered tool provider: {provider_name}")
    
    def list_providers(self) -> List[str]:
        """Return a list of registered provider names.
        
        Returns:
            List of provider names
        """
        return list(self._providers.keys())
    
    def list_tools(self) -> Dict[str, ToolDescriptor]:
        """Return a mapping of fully-qualified tool names to their descriptors.
        
        The fully-qualified tool names are in the format "provider.tool_name".
        
        Returns:
            Dictionary mapping "provider.tool_name" to ToolDescriptor
        """
        tools = {}
        for provider_name, provider in self._providers.items():
            try:
                discovered_tools = provider.discover()
                for tool in discovered_tools:
                    fq_name = f"{provider_name}.{tool.name}"
                    tools[fq_name] = tool
            except Exception as e:
                logger.warning(
                    f"Failed to discover tools from provider '{provider_name}': {e}"
                )
                continue
        
        return tools
    
    def run(self, tool_fqname: str, args: Optional[Dict[str, Any]] = None) -> Any:
        """Run a tool by its fully-qualified name.
        
        Args:
            tool_fqname: Fully-qualified tool name in format "provider.tool_name"
            args: Optional dictionary of arguments for the tool
            
        Returns:
            The result from running the tool
            
        Raises:
            KeyError: If the tool_fqname is not found
            RuntimeError: If the tool execution fails
        """
        if "." not in tool_fqname:
            raise KeyError(f"Invalid tool name '{tool_fqname}': must be in format 'provider.tool_name'")
        
        provider_name, tool_name = tool_fqname.split(".", 1)
        
        if provider_name not in self._providers:
            raise KeyError(f"Provider '{provider_name}' not found")
        
        provider = self._providers[provider_name]
        
        try:
            return provider.run(tool_name, args)
        except Exception as e:
            logger.error(f"Failed to run tool '{tool_fqname}': {e}")
            raise RuntimeError(f"Tool execution failed for '{tool_fqname}': {e}") from e


# Global registry instance
_registry: Optional[Registry] = None


def get_registry() -> Registry:
    """Get the global registry instance (singleton).
    
    Returns:
        The global Registry instance
    """
    global _registry
    if _registry is None:
        _registry = Registry()
    return _registry