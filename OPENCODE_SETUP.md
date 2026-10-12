# Local OpenCode Go setup

The active gateway and custom provider configuration use these roles:

| Roles | Model |
| --- | --- |
| assistant, primary_agent, simple, simple_json, reflector, searcher, enricher, installer | deepseek-v4.1-flash |
| coder, generator, refiner | muse-spark-1.3-contributor |
| adviser, pentester | glm-5.3-flash |

The model picker also offers three named chat presets: **DeepSeek V4.1
Flash**, **GLM 5.3 Flash**, and **Muse Spark 1.3 Contributor**. They choose
the assistant model; all retain the specialist mapping above. Install them
idempotently with `python install_opencode_presets.py` (local admin user 1).
The original `custom` preset is displayed as **Default configuration** and
uses DeepSeek for the assistant.

The picker is editable while idle. The selected model takes effect on the
next message in the **same assistant and message chain**, retaining stored
conversation and tool history. The provider change is persisted, so it also
survives a reload or service restart. Model changes are disabled during a
running request. Changing Use Agents also keeps the same conversation.

**Use Agents off**: the selected assistant works directly with its tools.
**Use Agents on**: the selected assistant may delegate to specialists, which
use the configured role models. Delegation is optional and adds model calls.

`LLM_SERVER_PROVIDER` must be **empty**. It is a LiteLLM model prefix, not
a provider display name. Setting it to `opencode` sends
`opencode/deepseek-v4.1-flash`, which OpenCode rejects as unavailable.
Keep the API key in `.env`; the gateway forwards it without logging it.

The gateway injects its own user agent and supplies a session header when
one is absent. It forwards Chat Completions streams immediately. Muse
requests are translated to Responses, including function definitions,
function results, images, token usage, completion status and streaming deltas.
Muse currently accepts only `tool_choice: auto`; unsupported choices fail
explicitly rather than being silently weakened. Muse uses low reasoning
effort and a 16K output budget for these roles.

OpenCode documents that the Muse Contributor tier permits training on
prompts and completions, and is not a zero-retention tier:
https://dev.opencode.ai/v2/docs/console/go

## Configure a fresh checkout

Requires Docker Desktop, Python 3.12+, Go 1.26.5 and Node/pnpm matching
`frontend/.nvmrc` and `frontend/package.json`. Copy `.env.example` to `.env`
only if you do not already have one. Replace the custom-provider settings
with those in `.env.opencode.example`, then set your own `LLM_SERVER_KEY`
in the private `.env`. Keep `LLM_SERVER_PROVIDER` empty.

Build the backend and frontend using the commands below **before** starting
this fork for the first time. `docker-compose.override.yml` automatically
selects the local image, so a fresh checkout needs these build artifacts.
`start.bat` works from any checkout folder and checks these prerequisites.

## Start and validate

```powershell
docker compose up -d --build
python install_opencode_presets.py
python -m unittest test_opencode_responses.py
python verify_opencode.py
```

The live verification consumes a small amount of provider quota and tests
only arithmetic tool calls. No targets are scanned. Upstream model access,
quota, regions and availability can change.

After changing the Python gateway, restart `opencode-proxy`. After changing
the YAML or `.env`, recreate `pentagi` so its provider is reloaded.

## UI changes

The local Compose override packages the locally built backend and UI.
It displays submitted messages immediately, adds startup feedback and
recovery actions, and supports cancellation before a worker is registered.
AI replies use transparent backgrounds. To rebuild:

```powershell
cd frontend
pnpm install --frozen-lockfile
pnpm run build
cd ..
cd backend
New-Item -ItemType Directory -Force ../local-build | Out-Null
$env:GOOS = 'linux'
$env:GOARCH = 'amd64'
$env:CGO_ENABLED = '0'
go build -trimpath -ldflags '-X pentagi/pkg/version.PackageName=pentagi -X pentagi/pkg/version.PackageVer=ce -X pentagi/pkg/version.PackageEdition=ce' -o ../local-build/pentagi ./cmd/pentagi
Remove-Item Env:GOOS, Env:GOARCH, Env:CGO_ENABLED
cd ..
docker compose build pentagi
docker compose up -d pentagi
```

The first message of a new flow requires image/language/title/tool setup.
The observed first session needed about 36 seconds of setup; subsequent
messages answered in about 2 seconds. Enter submits a message, while
Shift+Enter inserts a newline. Stop means work is in progress.
Stop during startup cancels preparation; create a new assistant to continue.
Stop during an active turn cancels that turn and keeps the conversation usable.
Wait until active work is idle before recreating the application container.

## Recovery

Create a new flow if setup failed before a primary container was registered.
Do not blindly set failed rows to `waiting`: a worker cannot load without its
container and message chain. The old failed flow is retained as history.
For a failed assistant on a healthy flow, use **Create new assistant**.

## Thinking and completion feedback

The assistant composer offers verified levels for the configured models:
DeepSeek: None, Low, Medium, High; GLM: Low, High; Muse: Minimal, Low, Medium, High.
None is the initial choice when supported. Muse rejects None, so its initial
choice is Minimal. GLM requires reasoning with tools, so its initial choice is Low. The choice applies to the next assistant turn, retaining
conversation identity. Setup and delegated specialists retain their own
configured reasoning settings. Unknown models do not receive guessed levels.

Muse reasoning summaries are forwarded separately from answer text. Thinking
is displayed only when the provider actually supplies it. Drafting remains
available while busy; sending and model controls wait for completion. Busy
assistant status is refreshed every two seconds to recover missed events.

Conversation summarization occurs before the next assistant turn rather than
holding the composer busy after a completed answer. Initial container setup,
provider time to first token and tool execution still take time.

Provider-supplied thinking now stays inline by default while streaming and after completion. Hide/Show is manual; receiving answer text or clearing search does not collapse it.
