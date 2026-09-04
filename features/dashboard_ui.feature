Feature: NOC WebUI Dashboard Interactions
  As a NOC Engineer
  I want a unified, single-page application dashboard
  So that I can configure probes, schedules, and trigger diagnostics without reloading the page

  Scenario: Navigating between views
    Given the dashboard is loaded with the admin API key
    When I click the navigation link for "Live Diagnostics"
    Then the "view-monitor-ondemand" section becomes visible
    And all other view sections are hidden
    And the sidebar active state is updated

  Scenario: Populating Live Diagnostics Dropdowns
    Given a custom probe exists with id "taco-bell"
    When the dashboard data finishes loading via "loadDashboardData()"
    Then the "diag-custom-probes-optgroup" in the Live Diagnostics view contains an option for "taco-bell"
    And the "sch-custom-probes-optgroup" in the Schedule view contains an option for "taco-bell"

  Scenario: Live Diagnostic Failure Handling
    Given I am on the Live Diagnostics view
    And I select a sensor and target probe "taco-bell"
    When I click "Run Diagnostic On Sensor"
    And the backend API returns a 422 Unprocessable Entity error
    Then an alert dialog is shown with the validation error message
    And the diagnostic results table remains unchanged

  Scenario: Chromebook Fleet Lock Toggle
    Given a Chromebook is displayed in the Chromebook Fleet table
    And its settings_locked state is false
    When I view the Chromebook Fleet table
    Then the lock toggle button for that Chromebook displays "🔒 Lock"
    When its settings_locked state changes to true
    Then the lock toggle button for that Chromebook displays "🔓 Unlock"

  Scenario: Chromebook Fleet Identity Binding
    Given a Chromebook sensor checks in with hostname "chromebook-agent" and a valid MAC address
    When I view the Chromebook Fleet table
    Then the second column displays the hostname "chromebook-agent"
    And the second column displays the MAC address in monospace font
    And it does not display "DEV-SIM-SERIAL"

  Scenario: EasyBuilder Probe Validation Error
    Given I open the "Create Custom Probe" modal
    And I enter a malformed URL "bad-domain" in the Target Endpoint field
    When I click "Save Probe"
    And the API responds with a 422 Validation Error
    Then the modal does not close silently
    And a Javascript alert displays the specific API error to the user
