# CyLine

CyLine is a Python project for registering VALORANT Cypher lineups from Discord
and from a GitHub Pages front end.

## Current scope

- Discord slash command registration.
- Optional title and description.
- Choices for ability, jump, and map.
- Screenshot storage under `docs/assets/lineups/`.
- JSON storage under `docs/data/lineups/` plus `docs/data/index.json`.
- Optional Discord notification.
- Optional Git commit and push after each registration.
- GitHub Pages map viewer and web registration form.
- Minimap position estimate with manual correction.
- Discord lineup search.
- Admin-only edit page for correcting lineup metadata and coordinates.

## Important security note

GitHub Pages is static hosting. Do not put a GitHub token, Discord token, or
web API secret in `docs/` JavaScript. The web form posts to a Python API, and
the Python API writes files and runs Git.

If `CYLINE_WEB_API_TOKEN` is empty, the web API accepts public submissions. That
is convenient for testing but can be abused. The committed GitHub Pages front
end does not send a secret token, because public JavaScript would expose it.

Admin edits require `CYLINE_ADMIN_TOKEN`. Do not put this token in `docs/`
files; enter it only in the admin page when using the tool.

## Requirements

This project targets Python 3.11 or later. The current workspace syntax check
was run with Python 3.12.13 from the Codex bundled runtime, but the dependency
range is kept compatible with Python 3.11.

Install dependencies:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If the existing `.venv` already runs the Discord bot, you do not need to replace
Python itself. Reinstall dependencies after pulling updates:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Configure

Copy `.env.example` to `.env`, then fill the values:

```powershell
Copy-Item .env.example .env
```

Required for the Discord bot:

```env
CYLINE_DISCORD_TOKEN=your_discord_bot_token
```

Use the raw GitHub `docs/` URL for Discord image links:

```env
CYLINE_ASSET_BASE_URL=https://raw.githubusercontent.com/yss19411208/CyLine/refs/heads/main/docs/
```

Recommended for development:

```env
CYLINE_DISCORD_GUILD_ID=your_test_server_id
CYLINE_AUTO_GIT_COMMIT=true
CYLINE_AUTO_GIT_PUSH=false
CYLINE_ADMIN_TOKEN=your_admin_edit_token
```

Set `CYLINE_AUTO_GIT_PUSH=true` only after the Git remote and branch are ready.

## Run Discord bot

Run the Discord bot in its own PowerShell window. `cyline-api` does not start
the bot.

```powershell
.\.venv\Scripts\Activate.ps1
cyline-bot
```

Use the slash command:

```text
/register screenshot:<image> ability:<camera|cage|wire> jump:<true|false> map:<map>
```

Search registered lineups:

```text
/search map:<map> ability:<camera|cage|wire> jump:<true|false> keyword:<text>
```

Search results show a numbered map preview when a map is selected. Select a
result in Discord to see the image URL and details.

Optional fields:

- `title`
- `description`
- `position_x`
- `position_y`

Manual registration positions and admin coordinate corrections use 0 to 100
percent on the displayed map image.

## Run web registration API

Run the web registration API in a second PowerShell window if the Discord bot is
already running.

```powershell
.\.venv\Scripts\Activate.ps1
cyline-api
```

The API listens on:

```text
http://127.0.0.1:8000
```

Opening that URL should return a small JSON status response. The registration
form sends submissions to `http://127.0.0.1:8000/api/lineups`.

The admin update API listens on:

```text
PATCH http://127.0.0.1:8000/api/admin/lineups/<id>
```

It requires `CYLINE_ADMIN_TOKEN` through the `X-CyLine-Admin-Token` header.

`docs/config.js` is set to this local API URL by default. For GitHub Pages usage
from another device or from other users, deploy this API separately and replace
`apiBaseUrl` in `docs/config.js` with the public HTTPS API URL.

## GitHub Pages

Publish the repository using the `docs/` folder as the GitHub Pages source.
The page reads:

```text
docs/data/index.json
```

The GitHub Pages site is still used for the HTML viewer. Discord image links use
the raw GitHub URL configured in `CYLINE_ASSET_BASE_URL`, for example:

```text
https://raw.githubusercontent.com/yss19411208/CyLine/refs/heads/main/docs/assets/lineups/example.png
```

Local preview with Node.js:

```powershell
node tools/static_server.mjs 8080 docs
```

Open:

```text
http://127.0.0.1:8080/
```

Open the admin editor:

```text
http://127.0.0.1:8080/admin.html
```

The admin editor loads the same static JSON as the viewer, then sends updates
to `cyline-api`. Use the map preview click target to correct bad coordinates.

## Map assets

Map metadata and display icons come from the non-official Valorant-API map
endpoint:

```text
https://valorant-api.com/v1/maps
```

The HTML viewer can use remote `displayIcon` URLs from `docs/data/maps.json`.
To cache map images under `docs/assets/maps/`, run:

```powershell
$env:PYTHONPATH='src'
python tools/sync_valorant_maps.py
```

Map pins are stored against the same map image orientation used by the HTML
viewer. The current default is the Valorant-API `displayIcon` orientation.

## Minimap detection status

The detector is intentionally conservative. It tests several top-left minimap
candidates, matches the selected map template while considering rotation, flips,
and scale differences, then searches inside the matched map area for the
red/white player pin instead of the yellow spike icon. The result is saved with
`confidence` and `needs_review`.

If OpenCV is unavailable or matching confidence is low, the lineup is saved with
`needs_review=true` and can still be manually corrected.

## Data shape

Each lineup record includes:

- `id`
- `map`
- `ability`
- `jump`
- `title`
- `description`
- `image_path`
- `detected_position`
- `map_position`
- `author`
- `created_at`
