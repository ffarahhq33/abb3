# Connect ABB3 to Smart Checksheet

The AI PC hosts the Checksheet backend. The ABB3 Pi keeps running its existing
Python sensor service, local MQTT broker, Google Sheets and analytics integration.
Pulling this update does not enable a connection by itself.

## Update the existing Python service

Before updating, identify the actual service name, working directory, service
user and live SQLite path (including any `ABB3_SQLITE_PATH` override). Back up
the source, service environment and database with the sensor service stopped.
Preserve all existing credentials, runtime data and local production settings.

In the ABB3 checkout, inspect `git status` and resolve local changes before
running `git pull --ff-only`. Restart the existing service after updating; do
not launch a second sensor process. The update adds the prefixed persistence
and shift modules already imported by `abb3.py`, fixes the persistence class
name and includes `line_code: ABB3` in live MQTT snapshots.

## Private MQTT access

Allow the AI PC to reach ABB3's broker using an authenticated private listener,
private VPN/forwarding, or verified TLS. Preserve Python and Node-RED access.
ABB3 must use its own broker: generic command topics are shared across lines.

The Checksheet broker account needs write access to `nodered/newshift`,
`nodered/modeltarget`, `nodered/mode`, `nodered/adjust_count`, `nodered/reject`,
`noderedparam/condition` and `nodered/downtime_session`; it needs read access to
`smartchecksheet/live`, `smartchecksheet/hourly` and `abb3/#`.

## AI PC configuration

Update the AI PC Checksheet backend to the version supporting per-line machine
connections. Preserve existing attendance settings and other commissioned lines.
Add this entry to its machine configuration, substituting the actual address:

```json
{
  "line": "ABB3",
  "mqttUrl": "mqtt://ABB3_PI_PRIVATE_IP:1883",
  "catalogPath": "abb3-catalog.json",
  "productionLine": "Line 3"
}
```

The configuration file is an array of entries. Verify `productionLine` against
the existing ABB3 Node-RED shift form; do not change the shift ID convention.
Supply a verified ABB3 model/manpower catalog beside that file.

Set backend-only environment values:

```dotenv
APP_MODE=live
MACHINE_CONNECTIONS_PATH=/app/config/machines.json
ABB3_MQTT_USERNAME=checksheet
ABB3_MQTT_PASSWORD=REPLACE_WITH_PRIVATE_BROKER_PASSWORD
ABB3_INGEST_TOKEN=REPLACE_WITH_UNIQUE_LONG_RANDOM_TOKEN
```

The shown path is for the Checksheet Docker config mount; a native installation
must use its actual machine config path. Use a production database separate from
demo and a bootstrap password of at least 12 characters. Rebuild/restart the
backend with the updated environment and assign the operator account ABB3 access.

## Durable events relay

The independent relay reads ABB3's existing `outbox_events` and adds its own
`checksheet_deliveries` ledger in the same SQLite database. It does not change
analytics delivery statuses. It retries events after outages and requires an
acknowledgement from the Checksheet receiver. It never publishes machine commands.

Copy the supplied relay and unit on the ABB3 Pi:

```bash
sudo install -d /opt/smartchecksheet
sudo install -m 644 deploy/checksheet_event_relay.py /opt/smartchecksheet/checksheet_event_relay.py
sudo install -m 644 deploy/checksheet-relay@.service /etc/systemd/system/checksheet-relay@.service
```

Create `/etc/smartchecksheet-relay.env` privately, with these actual values:

```dotenv
CHECKSHEET_LINE=ABB3
CHECKSHEET_SQLITE_PATH=/actual/path/to/existing/abb3_state.db
CHECKSHEET_EVENTS_URL=http://AI_PC_PRIVATE_IP:3700/api/integrations/events
CHECKSHEET_TOKEN=THE_SAME_VALUE_AS_ABB3_INGEST_TOKEN
```

The service user must have access to the database and its directory. Run one
relay per database. The Pi must reach the AI PC endpoint over a private network
or HTTPS; a loopback-only server/port bind is not reachable from the Pi.

```bash
sudo chmod 600 /etc/smartchecksheet-relay.env
sudo systemctl daemon-reload
sudo systemctl enable --now checksheet-relay@YOUR_EXISTING_SERVICE_USER
sudo journalctl -u checksheet-relay@YOUR_EXISTING_SERVICE_USER -n 40 --no-pager
```

Do not replace the existing `ABB3_API_EVENTS_URL` destination: analytics delivery
remains independent. Keep tokens, populated env files and runtime databases out
of Git.

## Verify during commissioning

Check `/api/health` on the AI PC and open ABB3 in the tablet app. Confirm actual
counts and status appear only under ABB3 before testing writes. Then verify
setup, mode, reject, parameter and downtime actions against Python. Controls
require fresh telemetry (within eight seconds) and production commands need
confirmation. Check the machine before resubmitting an unconfirmed command.
Confirm existing OEE/Sheets remain operational and relay delivery recovers after
a network interruption. This update has not been tested on the physical Pi.

Local tests, with mocked hardware/network:

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s deploy -p 'test_*.py' -v
```
