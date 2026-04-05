# Subnet Dashboard

This repo now includes a small web dashboard that:

- runs `btcli subnet show --netuid ... --network ...`
- parses the UID and emission rows
- exposes the data through a JSON API
- serves a frontend leaderboard that refreshes automatically

## Run it

Set the subnet values in your Linux shell:

```bash
export NETUID="2"
export ENDPOINT="ws://127.0.0.1:9944"
```

Then start the app:

```bash
uvicorn subnet_dashboard.app:app --host 0.0.0.0 --port 8000
```

Open:

- `http://localhost:8000/` for the leaderboard UI
- `http://localhost:8000/api/subnet-stats` for raw JSON

## Optional environment variables

- `NETUID`: supported directly and used as a fallback for `SUBNET_NETUID`
- `ENDPOINT`: supported directly and used as a fallback for `SUBNET_NETWORK`
- `SUBNET_CLI`: CLI executable name. Default: `btcli`
- `SUBNET_STATS_COMMAND`: override the exact command as a JSON array string.
- `SUBNET_CACHE_TTL`: cache duration in seconds. Default: `45`
- `SUBNET_COMMAND_TIMEOUT`: subprocess timeout in seconds. Default: `30`
- `SUBNET_DASHBOARD_TITLE`: custom page title
- `SUBNET_DASHBOARD_DEBUG`: set to `true` to enable Starlette debug mode

Example custom command:

```bash
export SUBNET_STATS_COMMAND='["btcli","subnet","show","--netuid","2","--network","ws://127.0.0.1:9944"]'
```

## Notes

- If your CLI can emit JSON, prefer that by using `SUBNET_STATS_COMMAND`.
- The parser now supports the standard `btcli subnet show` terminal table, including the UID, hotkey, coldkey, stake, and emissions columns.
- The frontend polls the backend every 30 seconds and supports filtering by role or hotkey.
