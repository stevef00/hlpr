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


def get_current_datetime_utc_tool():
    tool_definition = {
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
        }
    return tool_definition


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

def responses_create(client, create_args, messages):
    while True:
        # This uses the **new** responses API -- don't change this to
        #   client.chat.completions.create()
        with Spinner("Thinking"):
            response = client.responses.create(**create_args)

        response_type = response.output[0].type

        if response_type == "message":
            break
        elif response_type == "function_call":
            tool_call = response.output[0]
            function_name = tool_call.name

            result = get_current_datetime_utc()

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

    create_args["tools"].append(get_current_datetime_utc_tool())

    if args.web:
        create_args["tools"].append({
            "type": "web_search_preview",
            "search_context_size": "low",
        })

    try:
        while True:
            user_input = input("prompt> ").strip()

            if user_input.lower() in ["exit", "quit"]:
                break
            if user_input == ":edit":
                user_input = handle_edit_command()
                if not user_input:
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
