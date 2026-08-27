# Central Monitoring Platform (CMP) Server

This directory contains the FastAPI-based web server that acts as the orchestration backend and control plane for edge synthetic monitoring sensors.

---

## Technical Features

* **Dynamic Device Registration & Approval (TOFU):** Unapproved sensors register in a `pending` queue until approved by an administrator, receiving a unique cryptographic API key.
* **Test Scheduling Engine:** Distributes dynamic test parameters (CAASPP checks, CIPA frequency, scheduled bandwidth tests with bandwidth caps and maintenance windows) to edge sensors.
* **On-Demand Test Triggers:** Supports one-shot triggers (`/tests/bandwidth/trigger`) that instruct edge sensors to run tests immediately on their next check-in.
* **Credential Redaction:** Redacts Wi-Fi PSKs and passwords in administrative views (`SensorStatusResponseSafe`).
* **Auto-generated API Docs:** Serves Swagger UI and ReDoc interactive API documentation natively.
* **Remote Factory Reset Delivery:** Safely queues one-shot container wipes to remediate broken edge sensors.

---

## API Authentication & Security

All API endpoints are protected using API keys passed in the `X-API-Key` HTTP header:

* **Admin Key (`admin-noc-key-change-me`)**: Used by NOC administrators to approve devices, update test schedules, trigger bandwidth tests, and view sensor statuses.
* **Per-Sensor Edge Key (`sensor-key-...`)**: Generated dynamically during device approval. Required by each sensor to authenticate with `/api/v1/sensors/reconcile`.

---

## Key Endpoints

### Edge Facing
* `POST /api/v1/sensors/register` — Unauthenticated hardware registration (declares hostname, MAC, OS; enters `pending` state).
* `POST /api/v1/sensors/reconcile` — Authenticated check-in loop. Reports running containers and receives target Wi-Fi profiles, containers, and test schedules.

### Administrative Management (NOC)
* `GET /api/v1/sensors` — Lists all registered sensors, online states, and target configurations (Wi-Fi credentials redacted).
* `POST /api/v1/sensors/{sensor_id}/approve` — Approves a pending sensor and generates its unique API key.
* `POST /api/v1/sensors/{sensor_id}/reject` — Rejects or revokes a sensor, deleting its record and invalidating its key.
* `PUT /api/v1/sensors/{sensor_id}/config` — Updates Wi-Fi profiles, target containers, and dynamic test schedules.
* `POST /api/v1/sensors/{sensor_id}/tests/bandwidth/trigger` — Queues an immediate on-demand iperf3 bandwidth test on the sensor.
* `POST /api/v1/sensors/{sensor_id}/reset` — Queues a one-shot factory container wipe for the sensor.

---

## Interactive API Documentation

Once the server stack is running:
* **Swagger UI:** `http://<server-ip>:8000/docs`
* **ReDoc:** `http://<server-ip>:8000/redoc`
