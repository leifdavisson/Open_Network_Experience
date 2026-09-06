Feature: On-Demand Sensor Diagnostics Routing
  As a network operator
  I want the diagnostic API to correctly route test types
  So that I get accurate feedback for built-in suites and custom probes

  Scenario: Route built-in diagnostic test
    Given a valid sensor check-in state
    When the diagnostic endpoint receives test_type "iperf3"
    Then the system executes the built-in iPerf3 bandwidth suite

  Scenario: Route custom probe test
    Given a custom probe exists in PROBES_DB with id "taco-bell" and type "http"
    When the diagnostic endpoint receives test_type "taco-bell"
    Then the system executes an HTTP probe against the custom target
    And if the HTTP probe fails, the final status is FAIL

  Scenario: Unknown test falls back to default suite
    Given no custom probe exists with id "unknown-junk"
    When the diagnostic endpoint receives test_type "unknown-junk"
    Then the system executes the default 7-Layer OSI and SaaS suite

  Scenario: Dynamic gateway derivation for sensor subnet
    Given a sensor with IP address "10.98.2.141"
    When the diagnostic endpoint receives test_type "gateway" without target_override
    Then the default gateway target is dynamically set to "10.98.2.1" rather than "10.0.0.1"

  Scenario: Route Wi-Fi RF flapping diagnostic test
    Given a valid sensor check-in state
    When the diagnostic endpoint receives test_type "wifi_flapping"
    Then the system executes the dedicated Wi-Fi RF flapping and DARRP channel monitoring suite

  Scenario: Accurate probe attribution string formatting
    Given an HTTP diagnostic probe that fails to connect to "10.98.2.1"
    When the probe details are formatted
    Then the diagnostic attribution string reflects unreachable status rather than claiming HTTP 200 success
