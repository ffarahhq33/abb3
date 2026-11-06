# ABB3 Production Tracker and Smart Checksheet Integration

This repository is for **ABB 3 (ABB3)**. The production entry point is
`abb3.py`, which sets `LINE_CODE = "ABB3"`. All configuration examples below
apply to ABB3.

ABB3 runs on a Raspberry Pi. It counts products from the GPIO sensor, exchanges
commands and live values with Node-RED over local MQTT, writes production records
to Google Sheets, and saves recovery state and durable events in SQLite.
An independent relay can forward events to the Smart Checksheet backend on the
AI PC; see [CHECKSHEET-SETUP.md](CHECKSHEET-SETUP.md).

## ABB3 identifiers

| Setting | ABB3 value |
| --- | --- |
| Repository | https://github.com/ffarahhq33/abb3 |
| Sensor service entry point | `abb3.py` |
| Line code | `ABB3` |
| MQTT status topic | `abb3/status` |
| Live snapshot topic | `smartchecksheet/live` |
| Live hourly topic | `smartchecksheet/hourly` |
| Default SQLite database | `runtime/abb3_state.db`, relative to `abb3.py` |
| Database override | `ABB3_SQLITE_PATH` |
| Analytics API settings | `ABB3_API_ENABLED`, `ABB3_API_EVENTS_URL`, `ABB3_API_KEY` |

The generic command and live-data topics require a separate broker for each
machine. Keep ABB3 connected to its own broker when configuring the multi-line
Checksheet backend.

## How data flows

```text
ABB3 production sensor (BCM GPIO 17)
  -> abb3.py
     -> local MQTT broker (Node-RED and live Checksheet data)
     -> Google Apps Script (production checksheet and PDF)
     -> SQLite recovery state and outbox_events
        -> existing analytics API sender, when configured and enabled
        -> independent Checksheet event relay
           -> AI PC /api/integrations/events
```

The analytics sender and Checksheet relay have separate configuration and delivery
tracking. Do not replace an existing analytics destination with the Checksheet
endpoint. Pulling the repository does not enable the Checksheet connection by
itself.

## Repository contents

- `abb3.py` — production sensor loop, MQTT, Google queue, state and events.
- `abb3_persistence.py` — ABB3 SQLite recovery and analytics outbox sender.
- `abb3_shift_schedule.py` — shift-end and time-slot calculations.
- `abb3_downtime_session.py` — shared downtime session state transitions.
- `appscript.js` — Google Apps Script source.
- `requirements.txt` — Raspberry Pi Python dependencies.
- `tests/test_abb3_startup_smoke.py` — startup and runtime regression checks with mocked hardware/network.
- `deploy/checksheet_event_relay.py` — independent durable Checksheet relay.
- `deploy/checksheet-relay@.service` — systemd template for the relay.
- `deploy/test_checksheet_event_relay.py` — relay tests.
- [CHECKSHEET-SETUP.md](CHECKSHEET-SETUP.md) — ABB3 commissioning and AI PC connection instructions.

The production service imports the prefixed `abb3_persistence.py` and
`abb3_shift_schedule.py` modules. The unprefixed `persistence.py` and
`shift_schedule.py` are legacy copies.

### Legacy files that still need adaptation

Despite its filename, `abb3_sqlite_status.py` currently contains ABB7 line and
database settings. Do not use it to assess ABB3 health until its implementation
has been corrected. The legacy `sql_lite_recovery.md` also describes ABB7;
use the ABB3 configuration in this README and CHECKSHEET-SETUP.md instead.

This repository does not include an ABB3 sensor-service systemd unit, a
Node-RED flow updater, or the Node-RED/Apps Script test tools described in the
previous README. The included `checksheet-relay@.service` runs only the event
relay; it does not run the sensor service.

## Raspberry Pi requirements

- Raspberry Pi OS with Python 3 and access to BCM GPIO pin `17`.
- A local MQTT broker at `localhost:1883`.
- The existing ABB3 Node-RED flow and matching Google Apps Script deployment.
- Writable SQLite storage for recovery and durable delivery.
- The Pi and Node-RED configured for Malaysia time (`Asia/Kuala_Lumpur`).

Keep populated Node-RED exports, credentials, environment files, SQLite databases
and generated production reports out of Git.

## Get the source and dependencies

For a new checkout:

```bash
cd "$HOME"
git clone https://github.com/ffarahhq33/abb3.git abb3
cd abb3
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
```

Install/configure the local MQTT broker and Node-RED separately if they are not
already available. Verify `WEB_APP_URL` in `abb3.py` against the actual ABB3
Google Sheets deployment and use `appscript.js` in that matching deployment.

On an existing production Pi, update the existing checkout and sensor service.
Identify its actual service name, service user, working directory, environment
and live database path first. Do not start a second sensor process.

## ABB3 environment configuration

The sensor service reads these process environment variables:

```dotenv
# Use the existing production database path when updating an installed Pi.
ABB3_SQLITE_PATH=/actual/path/to/existing/abb3_state.db

# Analytics sending is disabled by default.
ABB3_API_ENABLED=false
ABB3_API_EVENTS_URL=
ABB3_API_KEY=
```

Without a database override, the default is `runtime/abb3_state.db` beside
`abb3.py`. Preserve the existing database location so recovery continues using
the same state. The service user needs write access to the database directory.

`abb3.py` does not automatically load a `.env` file. Supply these values through
the existing service's environment configuration (for example, its systemd
`EnvironmentFile`) or the process environment. Preserve working production
values; enable analytics sending only with the verified destination and private
key for that installation.

For the independent Checksheet relay, follow
[CHECKSHEET-SETUP.md](CHECKSHEET-SETUP.md). Its `CHECKSHEET_*` settings are separate
from the sensor service's `ABB3_*` analytics settings.

## Update an existing ABB3 Pi

1. Identify the current service, checkout, environment and SQLite path.
2. Stop the existing sensor service and back up the source, environment and
   database before updating.
3. In that checkout, inspect `git status` and resolve local changes before pulling.
4. Pull the update and install dependencies:

```bash
# Run from the existing ABB3 checkout.
git pull --ff-only origin main
.venv/bin/python -m pip install -r requirements.txt
```

5. Restart the existing sensor service using its actual service name and inspect
   its logs. Use the Python environment configured by that service if it differs
   from `.venv`.
6. Confirm counts, shift details, Node-RED, Google Sheets and existing analytics
   still work under ABB3.

Do not reset or discard production changes or replace the live database with an
empty one. The relay has its own installation and restart steps in
CHECKSHEET-SETUP.md.

## Verify ABB3 live data

On the ABB3 Pi, inspect the local MQTT topics:

```bash
mosquitto_sub -h localhost -t 'abb3/status' -v
mosquitto_sub -h localhost -t 'smartchecksheet/live' -v
```

Run each subscription separately. Live snapshots identify the machine with
`line_code: ABB3`. Use the broker's configured credentials if required.

Inspect the existing sensor service logs for successful SQLite recovery and
connection errors. Do not rely on the legacy status helper listed above.

When commissioning Smart Checksheet, verify that ABB3 data appears under ABB3
on the AI PC, that the relay can recover after a network interruption, and that
the existing Google Sheets and analytics paths remain operational. Full setup
and commissioning steps are in CHECKSHEET-SETUP.md.

## Shift handling and recovery

Python calculates shift endings from the submitted working hours and applies
the 08:00 production-day boundary. Early shift forms can be held pending until
their scheduled start. The 30-minute late-entry window buffers activity while
waiting for the next shift form; after the window expires, unassigned activity
is discarded.

SQLite saves counters, shift state, pending forms and downtime session state for
restart recovery. Durable events remain available for delivery after a network
outage. Recovery does not reconstruct sensor counts or machine operating time
while the service was stopped. On restart, sensor counting stays blocked until
the sensor is observed clear.

Dashboard behavior also depends on the actual deployed ABB3 Node-RED flow.
This repository does not supply a flow migration tool; verify that flow alongside
the Python service during commissioning.

## Local checks

Run from the repository root with Python 3:

```bash
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m unittest discover -s deploy -p 'test_*.py' -v
```

These checks use mocked hardware/network or local test data. They do not replace
verification on the physical ABB3 Pi.
