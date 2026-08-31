# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
Feature: Synthetic Quality and Network Compliance Probing

  Scenario: CIPA content filter restriction enforcement
    Given an edge sensor on the student access VLAN
    When the prober tests a restricted URL containing an adult or threat verification token
    And the network firewall or web proxy returns HTTP 403 Forbidden or drops the TCP connection
    Then the test result is marked COMPLIANT (1)
    And the metric cipa_compliance_status is emitted as 1

  Scenario: Voice and video media quality MOS calculation
    Given an active UDP RTP media stream simulation
    When round-trip time is 25.0ms, jitter is 1.5ms, and packet loss is 0.0%
    Then the calculated ITU-T G.107 Mean Opinion Score must be >= 4.35
    And the metric openux_voip_mos_score is emitted as a gauge

  Scenario: Multi-Resolver DNS query benchmarking
    Given local nameserver "10.0.0.2" and public nameserver "8.8.8.8"
    When the multi-resolver prober queries benchmark domain "caaspp-elpac.org"
    Then query latencies in milliseconds and RCODE status are measured per resolver
    And openux_dns_query_duration_seconds metrics are written atomically
