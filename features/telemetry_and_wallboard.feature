# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
Feature: Telemetry Ingestion, Wallboard Aggregation, and Evidence Lifecycle

  Scenario: Chromebook fleet telemetry forwarded to VictoriaMetrics TSDB
    Given a Chromebook extension reports telemetry with BSSID, RSSI, and app latencies
    When the CMP ingests the telemetry payload via POST /api/v1/sensors/{sensor_id}/report
    Then Prometheus-format metrics are generated with sensor_id and campus_id labels
    And the metrics are forwarded to VictoriaMetrics via HTTP POST to /api/v1/import/prometheus

  Scenario: Wallboard aggregates live PromQL metrics within 2 seconds
    Given VictoriaMetrics contains probe_duration_seconds and probe_success metrics
    When the wallboard endpoint GET /api/v1/wallboard/live-stats is queried
    Then the response must contain SaaS app health statuses derived from PromQL instant queries
    And the total query execution time must be <= 2000ms
    And unknown/unreachable TSDB states are reported as "UNKNOWN" rather than hardcoded defaults

  Scenario: TSDB spool queue persists metrics during VictoriaMetrics outage
    Given VictoriaMetrics is unreachable on all configured URLs
    When the CMP attempts to forward Prometheus metrics
    Then the metrics payload must be enqueued into the SQLite TSDB disk spool
    And the spool entry must include a retry attempt counter
    And the metrics are retried on subsequent forwarding attempts

  Scenario: Health endpoint reports accurate version and sensor counts
    Given 3 edge sensors are registered with last_seen within the past 120 seconds
    When GET /api/v1/health is queried
    Then the response must contain status "ok" and active_sensors count of 3
    And the version field must match the project's canonical version source
