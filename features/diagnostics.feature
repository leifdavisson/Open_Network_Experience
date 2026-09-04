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
