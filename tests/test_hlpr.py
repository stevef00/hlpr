import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import argparse
import builtins
import sys
from types import SimpleNamespace

import pytest

from hlpr import read_file, parse_args, repl_run, print_stats


class DummyUsage:
    def __init__(self):
        self.input_tokens = 1
        self.output_tokens = 2
        self.input_tokens_details = SimpleNamespace(cached_tokens=0)
        self.total_tokens = 3


class DummyResponse:
    def __init__(self, text="dummy"):
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
