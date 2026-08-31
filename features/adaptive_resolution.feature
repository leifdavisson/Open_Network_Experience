# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
Feature: Adaptive Resolution State Machine and Incident PCAP Triggering

  Scenario: Transitioning to AMBER state on latency degradation
    Given a baseline check interval of 15 seconds
    When gateway round-trip latency increases above 80ms
    Then the probing state machine transitions to "AMBER"
    And the polling sleep interval decreases to 5 seconds

  Scenario: Triggering incident PCAP slice on diagnostic anomaly
    Given the rolling RAM ring buffer is capturing 128-byte packet headers
    When a probe detects an anomaly with reason "caaspp_failure"
    Then the rolling ring buffer is merged and sliced into an incident .pcap file
    And metadata JSON is written alongside the PCAP snapshot
    And an openux_pcap_last_trigger_timestamp metric is emitted
