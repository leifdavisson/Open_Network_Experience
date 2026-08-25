# Central Monitoring Platform (CMP) Server

This directory contains the FastAPI-based web server that acts as the orchestration backend (the control plane) for the edge synthetic monitoring sensors.

---

## Technical Features

* **API Key Authentication:** Secures both edge check-in and administration endpoints via HTTP headers.
* **Credential Redaction:** Uses safe response schemas to prevent sensitive Wi-Fi PSK and passwords from appearing in administrative views.
* **Pydantic Schema Validation:** Standardizes edge-reporting schemas and target configuration manifests.
* **Auto-generated API Docs:** Serves Swagger and Redoc interactive API documentation endpoints natively.
* **State Reconciliation Engine:** Manages software versions, Wi-Fi profiles, and registers device status.
* **On-Demand Remote Wipes:** Sends state cleanup instructions to faulty sensors.

---

## API Authentication & Security

All API endpoints are protected using API keys passed in the `X-API-Key` HTTP header. 

* **Edge Key (`sensor-edge-key-change-me`)**: Used by edge sensors to authenticate with the `/api/v1/sensors/reconcile` endpoint.
* **Admin Key (`admin-noc-key-change-me`)**: Used by NOC administrators and dashboard backends to authenticate with administrative endpoints.

> [!IMPORTANT]
> In production, change the default keys defined in `server/main.py` and pass them securely via environment variables or secret management systems.


---

## Installation & Setup

### 1. Provision Virtual Environment
Create a clean python virtual environment and activate it:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Server
Launch the server daemon locally using Uvicorn:

```bash
python3 main.py
```

The service will bind to `0.0.0.0:8000`.

---

## API Documentation

Once the server is running, you can explore and test the endpoints interactively:

* **Interactive Swagger UI:** `http://localhost:8000/docs`
* **Alternative ReDoc UI:** `http://localhost:8000/redoc`

---

## Key Endpoints

### Edge Facing
* `POST /api/v1/sensors/reconcile`
  * **Auth:** Edge API Key (`X-API-Key`)
  * **Description:** Invoked by edge sensors to report status and retrieve desired state configuration profiles.

### Administrative Management (NOC)
* `GET /api/v1/sensors`
  * **Auth:** Admin API Key (`X-API-Key`)
  * **Description:** Lists online states, container runtimes, configuration drift, and target configurations with Wi-Fi credentials redacted (returns `SensorStatusResponseSafe`).
* `PUT /api/v1/sensors/{sensor_id}/config`
  * **Auth:** Admin API Key (`X-API-Key`)
  * **Description:** Updates target configurations (Wi-Fi credential parameters, or container versions).
* `POST /api/v1/sensors/{sensor_id}/reset`
  * **Auth:** Admin API Key (`X-API-Key`)
  * **Description:** Forces the specified sensor to execute a local factory reset on its next call.

