Feature: Wi-Fi RF and Network Telemetry
  As a network administrator
  I want the Chromebook sensor to inspect Wi-Fi connection attributes
  So that I can diagnose RF issues and channel congestion

  @REQ-NET-001
  Scenario Outline: Frequency to Channel Conversion
    Given a Wi-Fi center frequency of <frequency> MHz
    When the channel calculation is performed
    Then the calculated channel should be <channel>

    Examples:
      | frequency | channel |
      | 2412      | 1       |
      | 2437      | 6       |
      | 2462      | 11      |
      | 2484      | 14      |
      | 5180      | 36      |
      | 5240      | 48      |
      | 5745      | 149     |
      | 5975      | 5       |

  @REQ-NET-002
  Scenario Outline: Signal Percentage to RSSI dBm
    Given a signal strength percentage of <percent>
    When the RSSI dBm is calculated
    Then the RSSI should be <rssi> dBm

    Examples:
      | percent | rssi |
      | 100     | -50  |
      | 50      | -75  |
      | 0       | -100 |

  @REQ-PRB-001
  Scenario: Captive Portal Detection
    Given a network probe endpoint returning HTTP 204
    When captive portal check is executed
    Then the status should be open and authenticated

  @REQ-PRB-002
  Scenario: Sticky Client Detection
    Given a connected client on 2.4GHz with RSSI of -74 dBm
    When Wi-Fi health is analyzed
    Then sticky client should be flagged as true
