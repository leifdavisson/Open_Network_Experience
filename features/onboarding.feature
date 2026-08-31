# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
Feature: Edge Sensor Zero-Touch Provisioning and Onboarding

  Scenario: Automatic subnet-based TOFU sensor approval
    Given a subnet auto-enrollment rule configured for CIDR "10.142.10.0/24" targeting "West High School"
    When an unregistered edge sensor checks in from IP "10.142.10.55"
    Then the sensor status must transition from "pending" to "approved"
    And the sensor is assigned campus ID "CAMPUS-WEST-HIGH"
    And an API key is generated and returned to the sensor

  Scenario: In-Memory USB Staging Kit Generation
    Given a request to download the USB staging kit with site "Ridgeview High" and Wi-Fi SSID "District-Staff"
    When the GET /api/v1/onboarding/usb-kit.zip endpoint is called
    Then an in-memory zip archive is returned with "one-bootstrap.json"
    And the JSON manifest contains site "Ridgeview High" and Wi-Fi SSID "District-Staff"
    And the zip contains all required synthetic probe scripts and onboarding runners
