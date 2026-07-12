# Data Protocol v1.0

This document is the backend data-flow module's current protocol draft.

## Who Should Read What

Communication / PM:
- Basic rules
- ZMQ input rules
- `driver_input`
- `comm_state`

Vehicle algorithm student A:
- Basic rules
- `train_state`
- `alarm_event`
- `dashboard_snapshot.trains`

Signal / ATO algorithm student B:
- Basic rules
- `signal_state`
- `ma_state`
- `alarm_event`
- `dashboard_snapshot.sections/signals/switches/trains.ma_limit`

Backend student C:
- All sections
- Especially input parsing, state storage, and `dashboard_snapshot`

Frontend student D:
- `dashboard_snapshot`
- `trains`, `driver_inputs`, `sections`, `signals`, `switches`, `power`, `communication`, `alarms`
- `GET /data/line-layout.json`

## Basic Rules

- Use JSON.
- Prefer protocol field names below.
- Every ZMQ message should include `type` and `timestamp`.
- Field naming uses `snake_case`.
- External formal protocols are adapted before entering data_flow. For example,
  vehicle UDP/API, driver desk TCP, signal UDP, power adapters, and view-system
  packets should be parsed by their own adapter modules first, then published to
  the internal topics described here.
- data_flow is the platform aggregation layer. It stores the latest normalized
  states, marks data freshness, and exposes dashboard snapshots to the frontend.
  It does not own subsystem algorithms or raw binary protocol parsing.
- Management topics such as `add_train`, `remove_train`, `clear_trains`, and
  `reset_trains` are consumed by vehicle-management modules. data_flow ignores
  them as dashboard state and waits for the resulting `train_state` messages.
- Command result topics such as `command_ack`, `vehicle_management_result`, and
  `train_registry` can be published by subsystem modules after a command is
  actually applied. data_flow caches these acknowledgements in the dashboard
  snapshot so the frontend does not need to trust `published=true` alone.
- Snapshot records can include `source`, `protocol`, `adapter`, `received_at`,
  `stale_after_seconds`, and `is_stale` so reviewers can distinguish mock data,
  internal ZMQ data, and formal-protocol adapter data.
- In ZMQ mode, `zmq_connected` means data_flow recently received a valid module
  message. A socket subscription alone is not treated as a healthy connection.
- Fields with explicit units are converted at the data_flow boundary:
  `km_post`/`kilometerPost` are kilometers to meters, `*Cm` fields are
  centimeters to meters, `*Mps` speed fields are m/s to km/h, `voltageKv` is kV
  to V, `currentKa` is kA to A, and `powerMw` is MW to kW.
- Units:
  - `position`, `start`, `end`, `ma_limit`: meters
  - `speed`, `target_speed`: km/h
  - `acceleration`: m/s^2
  - `energy_kwh`: kWh
  - `stop_distance`: meters
  - `stop_error_cm`: centimeters
  - `voltage`: V
  - `current`: A
  - `power`: kW
  - `timestamp`: Unix timestamp in seconds

## External Protocol Adapter Mapping

The current platform uses ZMQ JSON as its internal bus. Formal protocol packets
from the requirement document should enter data_flow through adapters:

| External input | Adapter responsibility | Internal topic |
| --- | --- | --- |
| Vehicle UDP 20 ms / API 500 ms | Decode train slots, speed, acceleration, mileage, direction, active cab | `train_state` / `driver_input` |
| Driver desk PLC TCP | Decode handle, door, brake, ATO/ATP, parking state | `driver_input` / `train_state` |
| Signal subsystem | Convert route, switch, signal, section, MA results | `signal_state` / `ma_state` |
| Traction power subsystem | Convert voltage, current, power, fault flags | `power_state` |
| Track/view subsystem | Convert section, edge, signal, switch and visible-train state | `track_info` / `signal_state` / `train_state` |

Recommended metadata values:

| Source | Protocol | Adapter |
| --- | --- | --- |
| `vehicle_udp` | `formal_vehicle_udp` | `vehicle_udp_codec` |
| `vehicle_api` | `formal_vehicle_api` | `vehicle_api_codec` |
| `driver_tcp` | `formal_driver_plc_tcp` | `driver_desk_source` |
| `signal_zmq` | `internal_signal_zmq` | `signal_zmq_adapter` |
| `power_adapter` | `power_adapter` | `power_adapter` |
| `track_adapter` | `track_adapter` | `track_adapter` |

## ZMQ Input Messages

The preferred scheme is strict protocol fields at the top level:

```json
{
  "type": "train_state",
  "timestamp": 1720000000.123,
  "source": "vehicle_algo",
  "vehicle_id": "TRAIN-001",
  "position": 1234.5,
  "speed": 62.4
}
```

The backend also accepts a compatibility wrapper:

```json
{
  "type": "train_state",
  "timestamp": 1720000000.123,
  "source": "vehicle_algo",
  "data": {
    "vehicle_id": "TRAIN-001",
    "position": 1234.5,
    "speed": 62.4
  }
}
```

## driver_input

Sent by the communication module after parsing UDP/driver-console input.

```json
{
  "type": "driver_input",
  "timestamp": 1720000000.123,
  "source": "udp",
  "vehicle_id": "TRAIN-001",
  "traction_level": 3,
  "brake_level": 0,
  "direction": "forward",
  "control_mode": "manual",
  "emergency_button": false
}
```

Allowed values:
- `source`: `udp`, `mock`, `zmq`
- `direction`: `forward`, `backward`, `neutral`
- `control_mode`: `manual`, `ato`

## comm_state

Sent by the communication module.

```json
{
  "type": "comm_state",
  "timestamp": 1720000000.123,
  "source": "udp",
  "driver_console_connected": true,
  "udp_connected": true,
  "zmq_connected": true,
  "latency_ms": 12.5,
  "packet_loss_count": 0,
  "last_message_at": 1720000000.001
}
```

## train_state

Sent by vehicle algorithm student A.

```json
{
  "type": "train_state",
  "timestamp": 1720000000.123,
  "source": "vehicle_algo",
  "vehicle_id": "TRAIN-001",
  "line_id": "LINE-1",
  "position": 1234.5,
  "speed": 62.4,
  "acceleration": 0.32,
  "mode": "ato",
  "is_running": true,
  "emergency_brake": false,
  "energy_kwh": 52.5,
  "stop_distance": 120.0,
  "station_name": "中心站",
  "parking_phase": "approaching",
  "stop_error_cm": 45.0,
  "platform_id": "PF-01"
}
```

Allowed `mode` values:
- `manual`
- `ato`
- `atp`
- `emergency`
- `unknown`

Allowed `parking_phase` values:
- `cruising`
- `approaching`
- `braking`
- `docking`
- `stopped`

## signal_state

Sent by signal / ATO algorithm student B.

```json
{
  "type": "signal_state",
  "timestamp": 1720000000.123,
  "source": "signal_algo",
  "system_mode": "normal",
  "sections": [
    {
      "section_id": "SEG-01",
      "track_seg_id": "T01",
      "start": 0,
      "end": 500,
      "occupied": true,
      "vehicle_id": "TRAIN-001",
      "occupied_by": "TRAIN-001",
      "aspect": "red",
      "condition": "normal"
    }
  ],
  "signals": [
    {
      "signal_id": "SIG-01",
      "position": 500,
      "state": "green",
      "signal_type": "区间"
    }
  ],
  "switches": [
    {
      "switch_id": "SW-01",
      "position": "normal",
      "turnout_id": "SW-01",
      "routing": "normal",
      "state": "normal",
      "locked": true,
      "related_section": "SEG-03"
    }
  ]
}
```

Allowed values:
- signal `state`: `red`, `yellow`, `green`, `unknown`
- section `condition`: `normal`, `warning`, `fault`
- switch `position`: `normal`, `reverse`, `unknown`

`sections.aspect` should be `red`, `yellow`, `green`, or `unknown`; if omitted, the backend derives `red` from `occupied=true` and `green` otherwise.

## ma_state

Sent by signal / ATO algorithm student B.

```json
{
  "type": "ma_state",
  "timestamp": 1720000000.123,
  "source": "signal_algo",
  "ma_limits": [
    {
      "vehicle_id": "TRAIN-001",
      "route_id": "R_MAIN",
      "ma_limit": 1600,
      "permission": "allow",
      "signal_state": "green",
      "speed_limit": 60,
      "target_speed": 60,
      "reason": "front_train"
    }
  ]
}
```

## power_state

Sent by a power module, or generated by backend Mock mode before the real module is ready.

```json
{
  "type": "power_state",
  "timestamp": 1720000000.123,
  "source": "power_algo",
  "substation_id": "SS-01",
  "voltage": 1500,
  "current": 300,
  "power": 450,
  "is_fault": false
}
```

## alarm_event

Sent by any module.

```json
{
  "type": "alarm_event",
  "timestamp": 1720000000.123,
  "alarm_id": "ALM-001",
  "level": "warning",
  "source": "ATP",
  "vehicle_id": "TRAIN-001",
  "message": "Train is close to MA limit"
}
```

Allowed `level` values:
- `info`
- `warning`
- `critical`

## Frontend Output: dashboard_snapshot

Frontend should read only the backend-normalized snapshot.

REST:

```text
GET /api/v1/dashboard/snapshot
```

Static line layout:

```text
GET /data/line-layout.json
```

WebSocket:

```text
ws://localhost:8000/ws/dashboard
```

Output shape:

```json
{
  "type": "dashboard_snapshot",
  "protocol_version": "1.0",
  "timestamp": 1720000000.123,
  "system": {
    "status": "running",
    "system_mode": "normal",
    "data_source": "mock",
    "zmq_connected": false,
    "websocket_clients": 1
  },
  "communication": {},
  "driver_inputs": [],
  "trains": [],
  "sections": [],
  "signals": [],
  "switches": [],
  "power": {},
  "alarms": []
}
```
