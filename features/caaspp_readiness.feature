# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
Feature: CAASPP/ELPAC State Testing Readiness Validation

  Scenario: All critical Cambium TDS endpoints reachable and SSL-clean
    Given the edge sensor has active internet connectivity
    And the CAASPP endpoint list contains 8 official Cambium/ETS/SmarterBalanced URLs
    When the readiness checker probes each endpoint with a 4.0 second timeout
    Then all critical endpoints must return HTTP 200 or 302 within 1500ms
    And the TLS certificate chain must not contain injected MITM inspection certificates
    And the metric caaspp_endpoint_status is emitted as 1 for each passing endpoint

  Scenario: SSL inspection bypass detection via certificate chain validation
    Given the firewall is performing SSL deep inspection on Cambium TDS traffic
    When the readiness checker validates the certificate for "ca.cambiumtds.com"
    Then the checker must detect that the issuer is NOT a recognized Cambium/DigiCert CA
    And the endpoint is marked as MITM-intercepted with ssl_inspection_detected=1
    And the overall CAASPP readiness score is degraded below 100%

  Scenario: Graceful degradation when internet connectivity is offline
    Given the edge sensor cannot reach the internet connectivity check endpoint
    When the readiness checker runs the full CAASPP validation suite
    Then all endpoint statuses must be reported as "UNKNOWN"
    And the metric caaspp_internet_online is emitted as 0
    And no false-positive compliance failures are generated

  Scenario: Partial endpoint failure with mixed critical and non-critical results
    Given 6 of 8 CAASPP endpoints are reachable
    And 2 critical endpoints (Cambium TDS Student, Cambium TDS Admin) are blocked
    When the readiness checker computes the overall score
    Then the readiness score must be 0.75 (6/8)
    And the critical readiness score must be less than 1.0
    And an alert-eligible metric caaspp_critical_failure is emitted as 1
