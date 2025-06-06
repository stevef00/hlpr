# Simple OpenAI Chat REPL

A simple Python command-line application that provides an interactive chat REPL (Read-Eval-Print Loop) interface using the OpenAI API.

---

## Features

- Interactive chat interface for conversation with OpenAI models.
- Supports multiple predefined OpenAI GPT-4 variants.
- Load and discuss contents of one or more files as part of the conversation.
- Option to list allowed models.
- Optional token usage statistics display after each response.
- Graceful exit handling on `exit`, `quit`, Ctrl+C, or Ctrl+D.

---

## Supported Models

The application currently supports these models:

- gpt-4o-mini
- gpt-4o
- gpt-4.1-nano
- gpt-4.1-mini
- gpt-4.1

---

## Installation

1. Clone the repository or download the `hlpr.py` script.

2. Install the requirements:

```bash
pip install -r requirements.txt
```

*Note*: Make sure you have Python 3.7+ installed.

3. Set your OpenAI API key in your environment:

```bash
export OPENAI_API_KEY="your-api-key"
```

---

## Usage

Run the script with:

```bash
python hlpr.py [options]
```

### Options

- `-m, --model`: Specify which model to use (default: `gpt-4o-mini`).

- `-l, --list-models`: List all available models.

- `-f, --file`: Include contents of one or more files in the conversation context. You can specify this option multiple times to add multiple files.

- `-s, --stats`: Show token usage statistics after each response.

### Examples

- Start chat with default model:

```bash
python hlpr.py
```

- List available models:

```bash
python hlpr.py --list-models
```

- Start chat with a specific model and include file content:

```bash
python hlpr.py --model gpt-4o --file example.txt
```

- Show token usage stats during chat:

```bash
python hlpr.py --stats
```

---

## How it Works

- Initiates a conversational REPL loop where you enter messages.
- Sends the conversation history plus optional file contents to the OpenAI model.
- Prints the assistant's response to the terminal.
- Tracks the conversation by maintaining a message list with roles and contents.
- Exits cleanly when typing `exit`, `quit`, or on keyboard interrupts.

---

## License

This project is licensed under the MIT License.

---

## Disclaimer

This tool depends on the OpenAI API and requires a valid API key to function. Usage costs apply according to OpenAI's pricing.

---

If you have any questions or issues, feel free to open an issue or contact the maintainer.
