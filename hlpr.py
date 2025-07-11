#!/usr/bin/env python3

import argparse
import sys
import os
import readline
import subprocess
import textwrap
import tempfile
from datetime import datetime, timezone
from openai import OpenAI
from spinner import Spinner
from tool import Tool


# Available models
ALLOWED_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-nano",
    "gpt-4.1-mini",
    "gpt-4.1"
]


def get_current_datetime_utc():
    """Return the current UTC datetime as a string."""
    return str(datetime.now(timezone.utc))


def get_uname():
    """Return the uname command output"""
    result = subprocess.run(["uname", "-a"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


def get_uptime():
    """Return the uptime command output"""
    result = subprocess.run(["uptime"], capture_output=True, text=True, check=True)
    return result.stdout.strip()


TOOLS = [
    Tool(get_current_datetime_utc, {
            "type": "function",
            "name": "get_current_datetime_utc",
            "description": "Get the current date and time in UTC",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
                "required": []
            }
        }),
    Tool(get_uptime, {
            "type": "function",
            "name": "get_uptime",
            "description": "Get the system uptime",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
                "required": []
            }
        }),
    Tool(get_uname, {
            "type": "function",
            "name": "get_uname",
            "description": "Get the system uname output",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
                "required": []
            }
        })
]


def read_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except OSError as e:
        print(f"Error reading file: {str(e)}")
        sys.exit(1)


def print_stats(usage):
    input_tokens = usage.input_tokens
    output_tokens = usage.output_tokens
    cached_tokens = usage.input_tokens_details.cached_tokens
    total_tokens = usage.total_tokens
    print(f"stats: input_tokens={input_tokens} output_tokens={output_tokens} "
          f"cached_tokens={cached_tokens} total_tokens={total_tokens}")


def parse_args():
    parser = argparse.ArgumentParser(description="Simple OpenAI Chat REPL")
    parser.add_argument("-m", "--model", default="gpt-4o-mini",
        help="Model to use for chat")
    parser.add_argument("-l", "--list-models", action="store_true",
        help="List available models")
    parser.add_argument("-f", "--file", action="append",
        help="Include file contents in conversation")
    parser.add_argument("-s", "--stats", action="store_true",
        help="Show token usage statistics")
    parser.add_argument("-w", "--web", action="store_true",
        help="Enable web search")

    return parser.parse_args()


def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80  # Default width if we can't get terminal size


def handle_edit_command():
    """Handle the :edit command by opening an editor and returning the edited text."""
    editor = os.getenv("EDITOR", "vi")
    with tempfile.NamedTemporaryFile(suffix=".txt", mode="w+", delete=False) as tmp:
        tmp.flush()
        subprocess.run([editor, tmp.name], check=True)
        tmp.close()  # Ensure file is closed before reading
        with open(tmp.name, 'r', encoding="utf-8") as f:
            user_input = f.read().strip()
        os.unlink(tmp.name)  # Clean up the temp file
    return user_input


def handle_show_command(setting, args):
    """Print the value of the requested setting."""
    if setting == "model":
        print(f"model={args.model}")
    elif setting == "web":
        print(f"web={args.web}")
    elif setting == "stats":
        print(f"stats={args.stats}")
    else:
        print(f"error: unknown :show parameter '{setting}'")


def enable_web_search(create_args):
    """Add the web search tool if it isn't already present."""
    tools = create_args.setdefault("tools", [])

    if not any(tool.get("type") == "web_search_preview" for tool in tools):
        tools.append({
            "type": "web_search_preview",
            "search_context_size": "low",
        })


def disable_web_search(create_args):
    """Remove any web search tools from the API request."""
    create_args["tools"] = [
        tool for tool in create_args.get("tools", [])
        if tool.get("type") != "web_search_preview"
    ]


def handle_set_command(setting, args, create_args):
    """Update runtime settings from a ":set" command."""
    if setting.startswith("model="):
        model = setting.split("=", 1)[1].strip()
        if model not in ALLOWED_MODELS:
            print(f"Error: Model '{model}' not in allowed list.")
            return
        args.model = model
        create_args["model"] = model

    elif setting.startswith("web="):
        value = setting.split("=", 1)[1].strip().lower()
        args.web = value in ("1", "true", "on", "yes")
        if args.web:
            enable_web_search(create_args)

        else:
            disable_web_search(create_args)

    elif setting.startswith("stats="):
        value = setting.split("=", 1)[1].strip().lower()
        args.stats = value in ("1", "true", "on", "yes")

    else:
        print(f"error: unknown :set parameter '{setting}'")


def responses_create(client, create_args, messages):
    while True:
        # This uses the **new** responses API -- don't change this to
        #   client.chat.completions.create()
        with Spinner("Thinking"):
            response = client.responses.create(**create_args)

        response_type = response.output[0].type

        if response_type in [ "message", "web_search_call" ]:
            break
        if response_type == "function_call":
            tool_call = response.output[0]
            function_name = tool_call.name

            tool = next((tool for tool in TOOLS if tool.function_name() == function_name), None)
            result = tool.call()

            messages.append(tool_call)
            messages.append({
                "type": "function_call_output",
                "call_id": tool_call.call_id,
                "output": result
            })
        else:
            print(f"error: don't know what to do with response type: {response_type}",
                  file=sys.stderr)
            sys.exit(1)


    assistant_text = response.output_text
    messages.append({"role": "assistant", "content": assistant_text})
    return assistant_text, response.usage


def repl_run(client, messages, args):
    create_args = {
        "model": args.model,
        "input": messages,
        "tools": []
    }

    for tool in TOOLS:
        create_args["tools"].append(tool.definition)

    if args.web:
        create_args["tools"].append({
            "type": "web_search_preview",
            "search_context_size": "low",
        })

    try:
        while True:
            user_input = input("prompt> ").strip()

            if user_input == "":
                continue
            if user_input.lower() in ["exit", "quit"]:
                break
            if user_input == ":edit":
                user_input = handle_edit_command()
                if not user_input:
                    continue
            if user_input.startswith(":show "):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    handle_show_command(parts[1].lstrip(), args)
                continue
            if user_input.startswith(":set "):
                parts = user_input.split(maxsplit=1)
                if len(parts) > 1:
                    handle_set_command(parts[1].lstrip(), args, create_args)
                continue

            messages.append({"role": "user", "content": user_input})

            assistant_text, usage = responses_create(client, create_args, messages)

            width = get_terminal_width() - 1
            print("-" * width)
            for line in assistant_text.splitlines():
                wrapped = textwrap.fill(line, width=width)
                print(wrapped)

            if args.stats:
                print_stats(usage)

    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        sys.exit(0)


def main():
    args = parse_args()

    if args.list_models:
        print("Available models:")
        for model in ALLOWED_MODELS:
            print(f"- {model}")
        return

    if args.model not in ALLOWED_MODELS:
        print(f"Error: Model '{args.model}' not in allowed list.")
        print("Use --list-models to see available options.")
        return

    developer_message = "You're a helpful and friendly assistant."

    # Include file contents if specified
    if args.file:
        for file_path in args.file:
            file_content = read_file(file_path)
            developer_message += (
                f"\nThe user wants to discuss the contents of the file '{file_path}'\n"
                f"Here is the file content:\n{file_content}\n"
            )

    client = OpenAI()

    messages = [
        {
            "role": "developer",
            "content": developer_message
        }
    ]

    repl_run(client, messages, args)


if __name__ == "__main__":
    main()
