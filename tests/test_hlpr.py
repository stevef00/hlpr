import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import argparse
import builtins
import sys
import datetime
import tempfile
import subprocess
import os
import contextlib
from types import SimpleNamespace

import pytest

from hlpr import (
    read_file,
    parse_args,
    repl_run,
    print_stats,
    get_current_datetime_utc,
    get_current_datetime_utc_tool,
    handle_edit_command,
    responses_create,
)
import hlpr


class DummyUsage:
    def __init__(self):
        self.input_tokens = 1
        self.output_tokens = 2
        self.input_tokens_details = SimpleNamespace(cached_tokens=0)
        self.total_tokens = 3


class DummyOutput:
    def __init__(self, type="message", name=None, call_id="1"):
        self.type = type
        self.name = name
        self.call_id = call_id


class DummyResponse:
    def __init__(self, text="dummy"):
        self.output = [DummyOutput("message")]
        self.output_text = text
        self.usage = DummyUsage()


class DummyClient:
    def __init__(self, text="dummy"):
        self._response = DummyResponse(text)
        self.responses = SimpleNamespace(create=self._create)
        self.calls = []

    def _create(self, model, input, tools):
        self.calls.append((model, input, tools))
        return self._response


def test_parse_args_defaults(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hlpr"])
    args = parse_args()
    assert args.model == "gpt-4o-mini"
    assert args.list_models is False
    assert args.file is None
    assert args.stats is False
    assert args.web is False


def test_parse_args_custom(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hlpr", "--model", "gpt-4o"])
    args = parse_args()
    assert args.model == "gpt-4o"

def test_parse_args_web(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["hlpr", "--web"])
    args = parse_args()
    assert args.web is True

def test_read_file(tmp_path):
    f = tmp_path / "sample.txt"
    content = "hello"
    f.write_text(content)
    assert read_file(str(f)) == content


def test_read_file_missing(monkeypatch, tmp_path):
    missing = tmp_path / "missing.txt"
    def fake_exit(code):
        raise SystemExit(code)
    monkeypatch.setattr(sys, "exit", fake_exit)
    with pytest.raises(SystemExit):
        read_file(str(missing))


def test_print_stats(capsys):
    usage = DummyUsage()
    print_stats(usage)
    out = capsys.readouterr().out
    assert "input_tokens=1" in out
    assert "output_tokens=2" in out
    assert "cached_tokens=0" in out
    assert "total_tokens=3" in out


def test_repl_run(monkeypatch):
    client = DummyClient("hi")
    args = argparse.Namespace(model="gpt-4o-mini", stats=False, web=False)
    messages = []

    inputs = iter(["hello", "exit"])
    monkeypatch.setattr(builtins, "input", lambda _: next(inputs))

    repl_run(client, messages, args)

    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "hello"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == "hi"
    assert client.calls[0][0] == "gpt-4o-mini"


def test_repl_run_with_web(monkeypatch):
    client = DummyClient("hi")
    args = argparse.Namespace(model="gpt-4o-mini", stats=False, web=True)
    messages = []

    inputs = iter(["hello", "exit"])
    monkeypatch.setattr(builtins, "input", lambda _: next(inputs))

    repl_run(client, messages, args)

    # Verify the API call included the web search tool
    assert len(client.calls) > 0
    model, input_text, tools = client.calls[0]
    assert model == "gpt-4o-mini"
    assert tools is not None
    assert len(tools) == 2
    assert tools[1]["type"] == "web_search_preview"
    assert tools[1]["search_context_size"] == "low"


def test_get_current_datetime_utc(monkeypatch):
    fixed = datetime.datetime(2024, 1, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    monkeypatch.setattr(hlpr, "datetime", SimpleNamespace(now=lambda tz=None: fixed))
    result = get_current_datetime_utc()
    assert "2024-01-01 12:00:00+00:00" in result


def test_get_current_datetime_utc_tool():
    tool = get_current_datetime_utc_tool()
    assert tool["type"] == "function"
    assert tool["name"] == "get_current_datetime_utc"
    assert tool["parameters"]["type"] == "object"


def test_handle_edit_command(monkeypatch):
    def fake_run(cmd, check):
        with open(cmd[1], "w", encoding="utf-8") as f:
            f.write("edited")

    tmp_paths = []
    original = tempfile.NamedTemporaryFile

    def fake_tmp(*args, **kwargs):
        tmp = original(*args, **kwargs)
        tmp_paths.append(tmp.name)
        return tmp

    monkeypatch.setattr(tempfile, "NamedTemporaryFile", fake_tmp)
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = handle_edit_command()
    assert result == "edited"
    assert not os.path.exists(tmp_paths[0])


def test_responses_create_function_call(monkeypatch):
    class SeqClient:
        def __init__(self, responses):
            self._responses = responses
            self.responses = SimpleNamespace(create=self._create)
            self.calls = []

        def _create(self, model=None, input=None, tools=None):
            self.calls.append((model, input, tools))
            return self._responses.pop(0)

    # First response triggers the function call
    func_call = DummyOutput("function_call", name="get_current_datetime_utc", call_id="1")
    r1 = DummyResponse()
    r1.output = [func_call]
    r1.output_text = ""

    # Second response returns the assistant message
    r2 = DummyResponse("done")

    client = SeqClient([r1, r2])

    monkeypatch.setattr(hlpr, "Spinner", lambda msg: contextlib.nullcontext())
    monkeypatch.setattr(hlpr, "get_current_datetime_utc", lambda: "utc")

    messages = [{"role": "user", "content": "hi"}]
    create_args = {"model": "gpt-4o-mini", "input": messages, "tools": [get_current_datetime_utc_tool()]}

    text, usage = responses_create(client, create_args, messages)

    assert text == "done"
    # Function call output should have been appended
    assert isinstance(messages[1], DummyOutput)
    assert messages[1].type == "function_call"
    assert messages[2]["type"] == "function_call_output"


def test_repl_run_set_model(monkeypatch):
    client = DummyClient("hi")
    args = argparse.Namespace(model="gpt-4o-mini", stats=False, web=False)
    messages = []

    inputs = iter([":set model=gpt-4o", "hello", "exit"])
    monkeypatch.setattr(builtins, "input", lambda _: next(inputs))

    repl_run(client, messages, args)

    assert args.model == "gpt-4o"
    assert client.calls[0][0] == "gpt-4o"


def test_repl_run_set_web_and_show(monkeypatch, capsys):
    client = DummyClient("hi")
    args = argparse.Namespace(model="gpt-4o-mini", stats=False, web=False)
    messages = []

    inputs = iter([":set web=on", ":show web", "hello", "exit"])
    monkeypatch.setattr(builtins, "input", lambda _: next(inputs))

    repl_run(client, messages, args)

    out = capsys.readouterr().out
    assert "web=True" in out
    assert args.web is True
    # Web search tool should be included in the API call
    _, _, tools = client.calls[0]
    assert any(t.get("type") == "web_search_preview" for t in tools)


def test_repl_run_set_stats(monkeypatch, capsys):
    client = DummyClient("hi")
    args = argparse.Namespace(model="gpt-4o-mini", stats=False, web=False)
    messages = []

    inputs = iter([":set stats=on", "hello", "exit"])
    monkeypatch.setattr(builtins, "input", lambda _: next(inputs))

    repl_run(client, messages, args)

    out = capsys.readouterr().out
    assert "input_tokens=" in out
