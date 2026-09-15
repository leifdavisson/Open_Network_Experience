"""
Open Network Experience (ONE) — Grafana & VictoriaMetrics Telemetry Verification Test Suite
License: GNU AGPLv3
Tests provisioning configurations, scrape configs, dashboard query expressions,
and the live TSDB ingestion pipeline.
"""

import json
import yaml
import pytest
import httpx
from pathlib import Path

DEPLOY_DIR = Path(__file__).resolve().parent / "deploy"
DASHBOARDS_DIR = DEPLOY_DIR / "dashboards"
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

def test_01_grafana_datasources_provisioning_config():
    """Verify that grafana-datasources.yaml is valid and configures VictoriaMetrics & Loki."""
    ds_file = DEPLOY_DIR / "grafana-datasources.yaml"
    assert ds_file.exists(), f"Missing datasources config at {ds_file}"  # nosec B101

    with open(ds_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "datasources" in data, "datasources key missing in YAML"  # nosec B101
    datasources = {ds["name"]: ds for ds in data["datasources"]}

    assert "VictoriaMetrics" in datasources, "VictoriaMetrics datasource not configured"  # nosec B101
    vm_ds = datasources["VictoriaMetrics"]
    assert vm_ds["type"] == "prometheus"  # nosec B101
    assert vm_ds["url"] == "http://victoriametrics:8428"  # nosec B101
    assert vm_ds.get("isDefault") is True  # nosec B101

    assert "Loki" in datasources, "Loki datasource not configured"  # nosec B101
    loki_ds = datasources["Loki"]
    assert loki_ds["type"] == "loki"  # nosec B101
    assert loki_ds["url"] == "http://loki:3100"  # nosec B101

def test_02_grafana_dashboards_provisioning_config():
    """Verify that grafana-dashboards.yaml points to the provisioned dashboards directory."""
    dash_config_file = DEPLOY_DIR / "grafana-dashboards.yaml"
    assert dash_config_file.exists(), f"Missing dashboard config at {dash_config_file}"  # nosec B101

    with open(dash_config_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "providers" in data, "providers key missing in YAML"  # nosec B101
    providers = data["providers"]
    assert len(providers) > 0  # nosec B101
    provider = providers[0]
    assert provider["options"]["path"] == "/var/lib/grafana/dashboards"  # nosec B101

def test_03_scrape_yaml_configuration():
    """Verify that scrape.yml has all required scraping jobs for edge sensors and synthetic probes."""
    scrape_file = DEPLOY_DIR / "scrape.yml"
    assert scrape_file.exists(), f"Missing scrape.yml at {scrape_file}"  # nosec B101

    with open(scrape_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "scrape_configs" in data, "scrape_configs key missing in scrape.yml"  # nosec B101
    jobs = {job["job_name"]: job for job in data["scrape_configs"]}

    expected_jobs = [
        "sensor-node-metrics",
        "blackbox-gateway-ping",
        "blackbox-dns-probes",
        "blackbox-saas-apps"
    ]

    for expected in expected_jobs:
        assert expected in jobs, f"Job '{expected}' missing from scrape_configs"  # nosec B101
        job = jobs[expected]
        assert "static_configs" in job or "relabel_configs" in job or "http_sd_configs" in job  # nosec B101

def test_08_prometheus_http_service_discovery_endpoint():
    """Verify that /api/v1/telemetry/prometheus-sd dynamically exposes approved Linux edge sensors."""
    from fastapi.testclient import TestClient
    from server.main import app
    from server.state import SENSORS_DB
    from server.schemas import LocationSpec

    client = TestClient(app)

    # Save initial state
    orig_sensors = dict(SENSORS_DB)
    try:
        # Populate test fixtures:
        # 1. Approved Linux sensor with IP
        SENSORS_DB["sensor-approved-linux-1"] = {
            "sensor_id": "sensor-approved-linux-1",
            "status": "approved",
            "hostname": "edge-sensor-alpha",
            "ip_address": "10.98.2.243",
            "os": "Linux 6.8-generic",
            "campus_id": "CAMPUS-NORTH",
            "location": LocationSpec(
                district="Unified School District",
                campus="North Campus",
                site="Building A",
                room="Room 101"
            )
        }
        # 2. Approved Linux sensor with IP and custom port
        SENSORS_DB["sensor-approved-linux-2"] = {
            "sensor_id": "sensor-approved-linux-2",
            "status": "approved",
            "hostname": "edge-sensor-beta",
            "ip_address": "10.98.2.141:9100",
            "os": "Linux 6.8-generic",
            "campus_id": "CAMPUS-SOUTH",
            "location": LocationSpec(
                district="Unified School District",
                campus="South Campus",
                site="Building B",
                room="Room 202"
            )
        }
        # 3. Pending Linux sensor (should be excluded)
        SENSORS_DB["sensor-pending-linux"] = {
            "sensor_id": "sensor-pending-linux",
            "status": "pending",
            "hostname": "edge-sensor-gamma",
            "ip_address": "10.98.2.199",
            "os": "Linux",
            "campus_id": "CAMPUS-NORTH"
        }
        # 4. Approved Chromebook sensor (should be excluded from node_exporter scraping)
        SENSORS_DB["sensor-chromebook-1"] = {
            "sensor_id": "sensor-chromebook-1",
            "status": "approved",
            "hostname": "chromebook-cart-1",
            "ip_address": "10.98.2.250",
            "os": "ChromeOS 128.0",
            "sensor_type": "chromebook",
            "campus_id": "CAMPUS-WEST"
        }

        from server.routers.telemetry import invalidate_prometheus_sd_cache
        invalidate_prometheus_sd_cache()

        resp = client.get("/api/v1/telemetry/prometheus-sd")
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"  # nosec B101
        data = resp.json()
        assert isinstance(data, list), "Expected list of target groups"  # nosec B101

        # Check target mappings
        targets_by_id = {tg["labels"]["sensor_id"]: tg for tg in data if "labels" in tg and "sensor_id" in tg["labels"]}
        
        # Verify approved Linux sensors are present
        assert "sensor-approved-linux-1" in targets_by_id  # nosec B101
        assert targets_by_id["sensor-approved-linux-1"]["targets"] == ["10.98.2.243:9100"]  # nosec B101
        assert targets_by_id["sensor-approved-linux-1"]["labels"]["hostname"] == "edge-sensor-alpha"  # nosec B101
        assert targets_by_id["sensor-approved-linux-1"]["labels"]["site"] == "Building A"  # nosec B101
        assert targets_by_id["sensor-approved-linux-1"]["labels"]["room"] == "Room 101"  # nosec B101
        assert targets_by_id["sensor-approved-linux-1"]["labels"]["campus_id"] == "CAMPUS-NORTH"  # nosec B101

        assert "sensor-approved-linux-2" in targets_by_id  # nosec B101
        assert targets_by_id["sensor-approved-linux-2"]["targets"] == ["10.98.2.141:9100"]  # nosec B101

        # Verify pending sensor and chromebook are excluded
        assert "sensor-pending-linux" not in targets_by_id, "Pending sensor must not be scraped"  # nosec B101
        assert "sensor-chromebook-1" not in targets_by_id, "Chromebook must not be included in node_exporter SD"  # nosec B101

        # Also verify alias endpoint /telemetry/prometheus-sd returns cached response
        alias_resp = client.get("/telemetry/prometheus-sd")
        assert alias_resp.status_code == 200  # nosec B101
        assert alias_resp.json() == data  # nosec B101

        # Verify cache TTL behavior: mutating SENSORS_DB without invalidating returns cached data
        SENSORS_DB["sensor-approved-linux-3"] = {
            "sensor_id": "sensor-approved-linux-3",
            "status": "approved",
            "hostname": "edge-sensor-cached",
            "ip_address": "10.98.2.199",
            "os": "Linux"
        }
        cached_resp = client.get("/api/v1/telemetry/prometheus-sd")
        assert len(cached_resp.json()) == len(data), "Expected cached response within 15s TTL"  # nosec B101

        # Verify invalidating cache forces reload
        invalidate_prometheus_sd_cache()
        refreshed_resp = client.get("/api/v1/telemetry/prometheus-sd")
        assert len(refreshed_resp.json()) == len(data) + 1, "Expected refreshed response after cache invalidation"  # nosec B101
    finally:
        from server.routers.telemetry import invalidate_prometheus_sd_cache
        invalidate_prometheus_sd_cache()
        SENSORS_DB.clear()
        SENSORS_DB.update(orig_sensors)

def test_09_scrape_yaml_http_sd_configuration():
    """Verify that scrape.yml uses http_sd_configs for sensor-node-metrics pointing to CMP."""
    scrape_file = DEPLOY_DIR / "scrape.yml"
    with open(scrape_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    jobs = {job["job_name"]: job for job in data["scrape_configs"]}
    sensor_job = jobs["sensor-node-metrics"]

    assert "http_sd_configs" in sensor_job, "sensor-node-metrics job must use http_sd_configs for dynamic discovery"  # nosec B101
    http_sd = sensor_job["http_sd_configs"]
    assert len(http_sd) > 0  # nosec B101
    sd_entry = http_sd[0]
    assert "/api/v1/telemetry/prometheus-sd" in sd_entry["url"], f"Unexpected SD URL: {sd_entry.get('url')}"  # nosec B101

def test_10_chromebook_dashboard_templating_and_filtering():
    """Verify chromebook_fleet_dashboard.json has $sensor_id templating variable and panel filters."""
    cb_dash_path = DASHBOARDS_DIR / "chromebook_fleet_dashboard.json"
    with open(cb_dash_path, "r", encoding="utf-8") as f:
        dash = json.load(f)

    assert "templating" in dash, "chromebook_fleet_dashboard.json must have 'templating' block"  # nosec B101
    templating = dash["templating"]
    variables = {v["name"]: v for v in templating.get("list", [])}

    assert "sensor_id" in variables, "$sensor_id variable missing from chromebook dashboard templating"  # nosec B101
    sensor_id_var = variables["sensor_id"]
    assert sensor_id_var["type"] == "query"  # nosec B101
    assert "label_values(chromebook_wifi_connected, sensor_id)" in sensor_id_var.get("definition", "")  # nosec B101
    assert sensor_id_var.get("multi") is True  # nosec B101
    assert sensor_id_var.get("includeAll") is True  # nosec B101

    # Verify timeseries and stat panels filter on $sensor_id
    filtered_panels = 0
    for panel in dash.get("panels", []):
        for target in panel.get("targets", []):
            expr = target.get("expr", "")
            if "sensor_id=~\"$sensor_id\"" in expr or "sensor_id=~\\\"$sensor_id\\\"" in expr:
                filtered_panels += 1

    assert filtered_panels >= 3, f"Expected at least 3 panels with sensor_id filter, found {filtered_panels}"  # nosec B101


def test_04_dashboards_json_schema_and_queries():
    """Verify that all 5 Grafana dashboards are valid JSON with valid panel metric queries."""
    dashboard_files = list(DASHBOARDS_DIR.glob("*.json"))
    assert len(dashboard_files) >= 5, f"Expected at least 5 dashboards, found {len(dashboard_files)}"  # nosec B101

    expected_uids = {
        "openux-caaspp",
        "openux-cipa-drilldown",
        "one-chromebook-fleet-dashboard",
        "openux-noc",
        "openux-wifi-rf"
    }

    discovered_uids = set()

    for dash_path in dashboard_files:
        with open(dash_path, "r", encoding="utf-8") as f:
            dash = json.load(f)

        assert "title" in dash, f"Dashboard {dash_path.name} missing 'title'"  # nosec B101
        assert "uid" in dash, f"Dashboard {dash_path.name} missing 'uid'"  # nosec B101
        discovered_uids.add(dash["uid"])

        panels = dash.get("panels", [])
        assert len(panels) > 0, f"Dashboard {dash_path.name} has no panels"  # nosec B101

        # Validate that queries (targets) in panels have valid metric expressions
        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                if expr:
                    assert isinstance(expr, str)  # nosec B101
                    assert len(expr.strip()) > 0, f"Empty query expression in panel '{panel.get('title')}'"  # nosec B101

    for uid in expected_uids:
        assert uid in discovered_uids, f"Required dashboard UID '{uid}' not found in {dashboard_files}"  # nosec B101

def test_05_dashboard_template_grafana_embed_alignment():
    """Verify that the CMP Web UI dashboard embedding matches provisioned Grafana dashboard UIDs."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    main_js_path = TEMPLATES_DIR.parent / "static" / "js" / "modules" / "main.js"
    assert dash_html_path.exists(), f"dashboard.html not found at {dash_html_path}"  # nosec B101

    with open(dash_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    with open(main_js_path, "r", encoding="utf-8") as f:
        html_content += f.read()

    # Verify that the slide rotation links reference the provisioned Grafana dashboards with kiosk mode
    assert "/d/openux-noc/" in html_content  # nosec B101
    assert "/d/openux-caaspp/" in html_content  # nosec B101
    assert "/d/openux-cipa-drilldown/" in html_content  # nosec B101
    assert "/d/openux-wifi-rf/" in html_content  # nosec B101
    assert "/d/one-chromebook-fleet-dashboard/" in html_content  # nosec B101
    assert "kiosk=tv" in html_content  # nosec B101

def test_06_victoriametrics_live_ingestion_and_query():
    """Verify live TSDB responsiveness if VictoriaMetrics is running locally or in Docker."""
    vm_url = "http://localhost:8428/api/v1/label/__name__/values"
    try:
        resp = httpx.get(vm_url, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "success"  # nosec B101
            metrics = data.get("data", [])
            assert isinstance(metrics, list)  # nosec B101
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip("VictoriaMetrics not running locally on port 8428 (optional in unit test environment)")

def test_07_grafana_service_health_check():
    """Verify live Grafana health endpoint if Grafana is running locally or in Docker."""
    grafana_health_url = "http://localhost:3000/api/health"
    try:
        resp = httpx.get(grafana_health_url, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("database") == "ok"  # nosec B101
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip("Grafana not running locally on port 3000 (optional in unit test environment)")
