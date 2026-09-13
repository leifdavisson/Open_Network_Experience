Feature: Diagnostic Probes and EdTech Filtering
  As a ChromeOS network and systems administrator
  I want synthetic diagnostic probes running from the Chromebook client
  So that I can identify default gateway failures, DNS interception, bufferbloat, and EdTech filter degradation

  @REQ-PRB-003
  Scenario Outline: Local Gateway IP Derivation and Reachability
    Given a Chromebook client IPv4 address of "<client_ip>"
    When the default gateway IP is derived
    Then the derived gateway IP should be "<gateway_ip>"

    Examples:
      | client_ip     | gateway_ip   |
      | 10.200.4.155  | 10.200.4.1   |
      | 192.168.1.50  | 192.168.1.1  |
      | 172.16.20.99  | 172.16.20.1  |

  @REQ-PRB-004
  Scenario: Dual-Stack DNS Benchmark Evaluation
    Given Google DoH latency of 18 ms and Cloudflare DoH latency of 22 ms
    And local DNS resolution latency of 210 ms
    When dual-stack DNS benchmark health is evaluated
    Then DNS health should be flagged as "DEGRADED_LATENCY"
    And recommendation should suggest verifying local DNS server overload

  @REQ-PRB-005
  Scenario Outline: Bufferbloat Delta Latency Grading
    Given a baseline idle RTT of <idle_rtt> ms
    And a concurrent loaded RTT of <loaded_rtt> ms during micro-burst download
    When bufferbloat delta is calculated
    Then the bufferbloat grade should start with "<grade>"

    Examples:
      | idle_rtt | loaded_rtt | grade |
      | 25       | 35         | A     |
      | 30       | 70         | B     |
      | 25       | 150        | C     |
      | 20       | 200        | D     |
      | 30       | 380        | F     |

  @REQ-PRB-006
  Scenario: EdTech Multi-Agent Collision Detection
    Given installed filtering agents "Securly Filter" and "Lightspeed Systems Relay"
    When EdTech filter diagnostic suite is executed
    Then collision detected flag should be true
    And health status should be "COLLISION_DETECTED"
    And recommendation should warn against running multiple filtering agents

  @REQ-PRB-007
  Scenario: Classroom Educational Safe-List Pass-Through
    Given educational services "Google Classroom", "Canvas LMS", "Clever SSO", and "Kahoot"
    When classroom whitelist verification is performed through the filter proxy
    Then all services should report reachable
    And blocked count should be 0
