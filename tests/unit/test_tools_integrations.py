from types import SimpleNamespace

import json
import pytest


def test_build_tool_create_kwargs_variants():
    from spds.tools import build_tool_create_kwargs, SubjectiveAssessment

    def create_legacy(function=None, name=None, description=None, return_model=None):
        return None

    def create_modern(func=None, name=None, description=None):
        return None

    class Unintrospectable:
        # Raises TypeError on inspect.signature
        def __call__(self, *args, **kwargs):
            pass

    # Legacy signature with return_model
    kw_legacy = build_tool_create_kwargs(
        create_legacy,
        lambda x: x,
        name="t",
        description="d",
        return_model=SubjectiveAssessment,
    )
    assert "function" in kw_legacy and kw_legacy["name"] == "t"
    assert kw_legacy.get("return_model") is SubjectiveAssessment

    # Modern signature using func=
    kw_modern = build_tool_create_kwargs(create_modern, lambda x: x, name="t2")
    assert "func" in kw_modern and kw_modern["name"] == "t2"

    # Fallback for unintrospectable create_fn: should default to legacy 'function='
    unintrospectable = Unintrospectable()
    kw_fallback = build_tool_create_kwargs(unintrospectable, lambda x: x, name="t3")
    assert "function" in kw_fallback and kw_fallback["name"] == "t3"


def test_registry_list_and_run_success_and_errors(monkeypatch):
    from spds.integrations.registry import Registry, ToolDescriptor

    class Prov:
        def provider_name(self):
            return "prov"

        def discover(self):
            return [ToolDescriptor(name="echo", description="e")]

        def run(self, tool_name, args=None):
            if tool_name != "echo":
                raise KeyError("missing")
            return {"ok": args}

    r = Registry()
    r.register(Prov())
    tools = r.list_tools()
    assert "prov.echo" in tools

    # Successful run
    result = r.run("prov.echo", {"x": 1})
    assert result == {"ok": {"x": 1}}

    # Bad provider
    with pytest.raises(KeyError):
        r.run("nope.echo", {})

    # Bad tool
    with pytest.raises(RuntimeError):
        r.run("prov.missing", {})


def test_get_external_tool_functions_disabled(monkeypatch):
    from spds.tools import get_external_tool_functions
    from spds import config

    monkeypatch.setattr(config, "get_integrations_enabled", lambda: False)
    funcs = get_external_tool_functions()
    assert funcs == {}


def test_get_external_tool_functions_with_fake_mcp(monkeypatch):
    from spds.tools import get_external_tool_functions
    from spds.integrations.registry import get_registry
    from spds import config

    # Enable integrations and fake providers
    monkeypatch.setattr(config, "get_integrations_enabled", lambda: True)
    monkeypatch.setattr(config, "get_integrations_allow_fake_providers", lambda: True)

    # Reset registry singleton
    monkeypatch.setattr(
        "spds.integrations.registry._registry", None, raising=False
    )

    funcs = get_external_tool_functions()
    # When fake MCP is allowed, expect at least one tool function present (translate/search)
    assert any(name.endswith("translate") or name.endswith("search") for name in funcs.keys())


def test_load_and_register_external_tools_registers(monkeypatch):
    from spds.tools import load_and_register_external_tools

    created = []

    def fake_create(**kwargs):
        created.append(kwargs)

    monkeypatch.setattr(
        "spds.tools.get_external_tool_functions", lambda: {"prov.t": lambda x: x}
    )
    load_and_register_external_tools(SimpleNamespace(), fake_create)
    assert created and created[0]["name"] == "prov.t"


def test_external_tool_wrapper_handles_plain_and_json_and_errors(monkeypatch):
    # Force integrations enabled and fake providers
    import spds.tools as tools_mod
    from spds import config

    monkeypatch.setattr(config, "get_integrations_enabled", lambda: True)
    monkeypatch.setattr(config, "get_integrations_allow_fake_providers", lambda: True)

    # Use a fake registry that will echo or raise
    class FakeRegistry:
        def __init__(self):
            self.calls = []

        def list_tools(self):
            # One tool registered
            from spds.integrations.registry import ToolDescriptor

            return {"prov.echo": ToolDescriptor(name="echo", description="e")}

        def run(self, fqname, args):
            self.calls.append((fqname, args))
            if args.get("mode") == "explode":
                raise RuntimeError("boom")
            return {"ok": True, "args": args}

    fake_registry = FakeRegistry()

    # Patch get_registry used inside get_external_tool_functions
    monkeypatch.setattr("spds.integrations.registry.get_registry", lambda: fake_registry)

    # Build tool functions
    funcs = tools_mod.get_external_tool_functions()
    echo = funcs["prov.echo"]

    # Plain text input becomes {"input": ...}
    out1 = json.loads(echo("hello"))
    assert out1["ok"] is True and out1["args"]["input"] == "hello"

    # JSON input parses into dict
    out2 = json.loads(echo('{"a":1}'))
    assert out2["args"]["a"] == 1

    # Error path returns error string
    err = echo('{"mode":"explode"}')
    assert "Error executing tool" in err


