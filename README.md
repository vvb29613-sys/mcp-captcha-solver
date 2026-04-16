# MCP captcha solver for AI agents

![2cap_mcp](image/2cap_mcp.svg)

Minimal local demo project for showing the architecture:

`Agent -> browser/captcha MCP tools -> Selenium helpers -> structured result`

The demo page is used as a convenient test stand, while the core idea is a generic `reCAPTCHA v2` capability plus browser tools orchestrated by the agent.

## Purpose

This repository is a demo for an article and local experiments with MCP plus Selenium. The key idea is:

- the agent performs a higher-level web task
- browser tools handle generic page interaction
- captcha tools remove a `reCAPTCHA v2` obstacle when it appears
- tools use Selenium internally and return normalized results

The agent does not execute low-level browser steps itself.

## Current Scope

Current implementation is structured as two capability groups:

- browser capabilities for the agent's main task flow
- captcha capabilities for removing `reCAPTCHA v2` on the current page

Reference test page:

- `https://2captcha.com/demo/recaptcha-v2`

The structure is designed so additional workflows such as Turnstile can be added later without changing the overall architecture.

## Project Structure

```text
app/
  browser/
    driver_factory.py
    page_utils.py
  services/
    config.py
    result_models.py
    session_store.py
    solver_client.py
    workflow_catalog.py
  workflows/
    _common.py
    browser.py
    recaptcha_v2.py

mcp_server/
  server.py
```

## How It Works

Responsibilities are split by layer:

- `app/browser/`: Selenium driver lifecycle, waits, screenshots, and small browser helpers
- `app/services/`: config loading, normalized result models, and external solver adapters
- `app/workflows/`: workflow layer split into generic browser tools and `reCAPTCHA v2` capability
- `mcp_server/server.py`: MCP tools that expose workflows to the agent

This keeps the MCP layer thin and keeps Selenium details out of the agent prompt.

## Requirements

- Python 3.11+
- Google Chrome installed locally
- a compatible ChromeDriver available to Selenium
- 2Captcha API key for the demo workflow

## What Needs To Be Installed And Prepared

Before the project can run on another machine, prepare the following:

### 1. Python

Install Python `3.11+`.

Check:

```bash
python3 --version
```

### 2. Google Chrome

Install a local Chrome browser.

Check on macOS:

```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --version
```

### 3. Compatible ChromeDriver

Selenium must be able to start a Chrome instance that matches the installed
browser version.

Check:

```bash
chromedriver --version
```

If the browser and driver major versions do not match, Selenium may fail with
`SessionNotCreatedException`.

### 4. Python Dependencies

Create a virtual environment and install dependencies from
[`requirements.txt`](/Users/Maksim/Desktop/Работа/projects/example_for_mcp/requirements.txt).

### 5. Environment Variables

Create a local `.env` file from [`.env.example`](/Users/Maksim/Desktop/Работа/projects/example_for_mcp/.env.example).

At minimum, set:

- `APIKEY_2CAPTCHA`
- `BROWSER_NAME`
- `BROWSER_HEADLESS`
- `SCREENSHOT_DIR`
- `RESULT_DIR`
- `CAPTURE_STEP_SCREENSHOTS` if you want intermediate screenshots

### 6. 2Captcha API Key

The `captcha_solve_recaptcha_v2` tool depends on a valid 2Captcha API key.

Without it the browser tools will still work, but captcha-solving will return
an error.

### 7. Optional: Claude Desktop Or Another MCP Client

If someone wants to test the full agent-driven scenario rather than only start
the MCP server manually, they also need:

- an MCP-capable client
- for example Claude Desktop
- local MCP server configuration pointing to this project

Without an MCP client, the server can still be launched, but there will be no
agent connected to call tools.

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then copy and fill the environment file:

```bash
cp .env.example .env
```

## Configuration

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

Environment variables:

- `APIKEY_2CAPTCHA`: API key for 2Captcha
- `BROWSER_NAME`: currently `chrome`
- `BROWSER_HEADLESS`: `true` or `false`
- `SCREENSHOT_DIR`: where screenshots are stored
- `RESULT_DIR`: where extracted verification JSON artifacts are stored
- `CAPTURE_STEP_SCREENSHOTS`: `true` or `false`; when `false`, screenshots are
  captured mainly for errors and final extraction steps

## Quick Start Checklist

Before the first run, make sure all of the following are true:

- Python is installed
- Chrome is installed
- ChromeDriver is compatible with the installed Chrome version
- dependencies from `requirements.txt` are installed
- `.env` exists and contains a valid `APIKEY_2CAPTCHA`
- the machine can open a local Chrome browser
- if using an agent, the MCP client is configured to launch this server

## Running The MCP Server

Start the server locally over stdio:

```bash
python -m mcp_server.server
```

## Connecting In Claude Desktop

If you want to test the full agent-driven flow in Claude Desktop, the local MCP
server must also be registered in Claude's config.

### 1. Find Claude Desktop config

On macOS the config file is typically:

[`claude_desktop_config.json`](/Users/Maksim/Library/Application%20Support/Claude/claude_desktop_config.json)

### 2. Add this MCP server

Add an entry like this to the `mcpServers` section:

```json
{
  "mcpServers": {
    "mcp-captcha-demo": {
      "command": "/usr/bin/env",
      "args": [
        "python3",
        "/Users/Maksim/Desktop/Работа/projects/example_for_mcp/mcp_server/server.py"
      ],
      "env": {
        "PYTHONPATH": "/Users/Maksim/Desktop/Работа/projects/example_for_mcp",
        "APIKEY_2CAPTCHA": "YOUR_2CAPTCHA_API_KEY",
        "BROWSER_NAME": "chrome",
        "BROWSER_HEADLESS": "true",
        "SCREENSHOT_DIR": "/Users/Maksim/Desktop/Работа/projects/example_for_mcp/artifacts/screenshots",
        "RESULT_DIR": "/Users/Maksim/Desktop/Работа/projects/example_for_mcp/artifacts/results",
        "CAPTURE_STEP_SCREENSHOTS": "false"
      }
    }
  }
}
```

Notes:

- use absolute paths
- if the project lives in a different directory, update all paths accordingly
- if you already store `APIKEY_2CAPTCHA` in `.env`, you can omit it here
- `PYTHONPATH` should point to the project root so imports like `app.*` work

### 3. Restart Claude Desktop

After editing the config:

- fully quit Claude Desktop
- open it again
- go to `Settings -> Developer -> Local MCP servers`
- confirm that `mcp-captcha-demo` is visible and connected

### 4. Verify tool loading

In a new Claude chat, ask something like:

```text
Call healthcheck and list_available_workflows.
```

If the server is connected correctly, Claude should see the exposed browser and
captcha tools.

### 5. Recommended permission behavior

Claude Desktop may ask for permission before tool calls.

For smoother testing:

- allow tool usage for `mcp-captcha-demo`
- prefer `Always allow` during local demo sessions

Otherwise Claude may pause before almost every browser or captcha action, which
makes the agent flow look much less autonomous.

## Available Tools

- `healthcheck`
- `list_available_workflows`
- `browser_open_page`
- `browser_get_page_state`
- `browser_find_elements`
- `browser_click`
- `browser_extract_text`
- `browser_extract_json`
- `browser_click_verify`
- `browser_extract_verification_json`
- `browser_close_page`
- `browser_close_page_on_error`
- `captcha_solve_recaptcha_v2`

## Agent Flow

The preferred agent scenario is:

1. Call `browser_open_page` with the target URL
2. Call `browser_get_page_state`
3. If a challenge blocks the task, call `captcha_solve_recaptcha_v2`
4. Continue the main task through generic browser tools such as `browser_find_elements`, `browser_click`, `browser_extract_text`, or `browser_extract_json`
5. Optionally use `browser_click_verify` and `browser_extract_verification_json` for the current 2captcha demo page
6. Call `browser_close_page`

The target page URL should come from the user task or agent prompt rather than
from server-side default configuration.

## Tool Result Format

Tools return a normalized shape like:

```json
{
  "status": "success",
  "workflow": "browser_recaptcha_tools",
  "challenge_type": "recaptcha_v2",
  "page_url": "https://2captcha.com/demo/recaptcha-v2",
  "message": "Verification JSON extracted from the page.",
  "session_id": "18d22b7f3f13485f8f5e3d4f7c9db201",
  "screenshot_path": "artifacts/screenshots/browser_recaptcha_tools-verification-json-20260402-120000.png",
  "verification_payload": {
    "success": true,
    "challenge_ts": "2026-04-06T13:28:26.925Z",
    "hostname": "2captcha.com"
  },
  "verification_result_path": "artifacts/results/browser_recaptcha_tools-verification-20260402-120000.json",
  "details": {
    "verification_payload_present": true
  }
}
```

On failure, `status` becomes `error`, `message` contains a readable explanation, and `screenshot_path` is included when available.

## Extending The Project

To add a new supported challenge type:

1. Add more generic browser tools when the agent needs richer continuation actions
2. Keep generic Selenium primitives in `app/browser/`
3. Add provider-specific solving logic to `app/services/` only if needed
4. Expose a new `captcha_*` tool in `mcp_server/server.py` only if a new captcha type is needed
5. Let the agent continue orchestrating browser tools and captcha tools together

The intended model is agent orchestration over two capability sets: generic browser steps and a specialized `reCAPTCHA v2` solving capability.
