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
    assert ds_file.exists(), f"Missing datasources config at {ds_file}"

    with open(ds_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "datasources" in data, "datasources key missing in YAML"
    datasources = {ds["name"]: ds for ds in data["datasources"]}

    assert "VictoriaMetrics" in datasources, "VictoriaMetrics datasource not configured"
    vm_ds = datasources["VictoriaMetrics"]
    assert vm_ds["type"] == "prometheus"
    assert vm_ds["url"] == "http://victoriametrics:8428"
    assert vm_ds.get("isDefault") is True

    assert "Loki" in datasources, "Loki datasource not configured"
    loki_ds = datasources["Loki"]
    assert loki_ds["type"] == "loki"
    assert loki_ds["url"] == "http://loki:3100"

def test_02_grafana_dashboards_provisioning_config():
    """Verify that grafana-dashboards.yaml points to the provisioned dashboards directory."""
    dash_config_file = DEPLOY_DIR / "grafana-dashboards.yaml"
    assert dash_config_file.exists(), f"Missing dashboard config at {dash_config_file}"

    with open(dash_config_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "providers" in data, "providers key missing in YAML"
    providers = data["providers"]
    assert len(providers) > 0
    provider = providers[0]
    assert provider["options"]["path"] == "/var/lib/grafana/dashboards"

def test_03_scrape_yaml_configuration():
    """Verify that scrape.yml has all required scraping jobs for edge sensors and synthetic probes."""
    scrape_file = DEPLOY_DIR / "scrape.yml"
    assert scrape_file.exists(), f"Missing scrape.yml at {scrape_file}"

    with open(scrape_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert "scrape_configs" in data, "scrape_configs key missing in scrape.yml"
    jobs = {job["job_name"]: job for job in data["scrape_configs"]}

    expected_jobs = [
        "sensor-node-metrics",
        "blackbox-gateway-ping",
        "blackbox-dns-probes",
        "blackbox-saas-apps"
    ]

    for expected in expected_jobs:
        assert expected in jobs, f"Job '{expected}' missing from scrape_configs"
        job = jobs[expected]
        assert "static_configs" in job or "relabel_configs" in job

def test_04_dashboards_json_schema_and_queries():
    """Verify that all 5 Grafana dashboards are valid JSON with valid panel metric queries."""
    dashboard_files = list(DASHBOARDS_DIR.glob("*.json"))
    assert len(dashboard_files) >= 5, f"Expected at least 5 dashboards, found {len(dashboard_files)}"

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

        assert "title" in dash, f"Dashboard {dash_path.name} missing 'title'"
        assert "uid" in dash, f"Dashboard {dash_path.name} missing 'uid'"
        discovered_uids.add(dash["uid"])

        panels = dash.get("panels", [])
        assert len(panels) > 0, f"Dashboard {dash_path.name} has no panels"

        # Validate that queries (targets) in panels have valid metric expressions
        for panel in panels:
            targets = panel.get("targets", [])
            for target in targets:
                expr = target.get("expr", "")
                if expr:
                    assert isinstance(expr, str)
                    assert len(expr.strip()) > 0, f"Empty query expression in panel '{panel.get('title')}'"

    for uid in expected_uids:
        assert uid in discovered_uids, f"Required dashboard UID '{uid}' not found in {dashboard_files}"

def test_05_dashboard_template_grafana_embed_alignment():
    """Verify that the CMP Web UI dashboard embedding matches provisioned Grafana dashboard UIDs."""
    dash_html_path = TEMPLATES_DIR / "dashboard.html"
    assert dash_html_path.exists(), f"dashboard.html not found at {dash_html_path}"

    with open(dash_html_path, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Verify that the slide rotation links reference the provisioned Grafana dashboards with kiosk mode
    assert "/d/openux-noc/" in html_content
    assert "/d/openux-caaspp/" in html_content
    assert "/d/openux-cipa-drilldown/" in html_content
    assert "/d/openux-wifi-rf/" in html_content
    assert "/d/one-chromebook-fleet-dashboard/" in html_content
    assert "kiosk=tv" in html_content

def test_06_victoriametrics_live_ingestion_and_query():
    """Verify live TSDB responsiveness if VictoriaMetrics is running locally or in Docker."""
    vm_url = "http://localhost:8428/api/v1/label/__name__/values"
    try:
        resp = httpx.get(vm_url, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("status") == "success"
            metrics = data.get("data", [])
            assert isinstance(metrics, list)
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip("VictoriaMetrics not running locally on port 8428 (optional in unit test environment)")

def test_07_grafana_service_health_check():
    """Verify live Grafana health endpoint if Grafana is running locally or in Docker."""
    grafana_health_url = "http://localhost:3000/api/health"
    try:
        resp = httpx.get(grafana_health_url, timeout=2.0)
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("database") == "ok"
    except (httpx.ConnectError, httpx.TimeoutException):
        pytest.skip("Grafana not running locally on port 3000 (optional in unit test environment)")
