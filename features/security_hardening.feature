# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
Feature: Security Hardening — Shell Injection Prevention, CORS, and Evidence Authentication

  Scenario: Shell metacharacter sanitization in install script generator
    Given the onboarding install script endpoint at GET /install.sh
    When a request includes site parameter containing shell injection payload "; rm -rf /; echo "
    Then the generated script must contain the payload wrapped in shlex.quote() escaping
    And the bash variable assignment must be safe for execution
    And no shell metacharacters (;, |, &, $, `) appear unescaped in variable values

  Scenario: All query parameters are sanitized before shell injection
    Given the install script generator accepts parameters: site, building, room, district, notes, token, wifi_ssid, wifi_psk
    When each parameter contains the test payload "test$(whoami)"
    Then every occurrence in the output script must be escaped to prevent command substitution
    And the literal string "test$(whoami)" appears as a safe quoted value

  Scenario: CORS wildcard origins rejected when credentials are enabled
    Given the CMP server is configured with ENVIRONMENT=production
    And CORS_ORIGINS is not set (defaulting to wildcard)
    When the CORS middleware is initialized
    Then allow_credentials must be set to False when allow_origins contains "*"
    Or allow_origins must be restricted to explicitly enumerated domains

  Scenario: Evidence vault endpoint requires authentication
    Given an unauthenticated HTTP client with no X-API-Key header
    When the client sends GET /api/v1/evidence
    Then the response status code must be 401 Unauthorized
    And no evidence bundle metadata is returned in the response body

  Scenario: Evidence vault accessible with valid admin API key
    Given an authenticated HTTP client with a valid X-API-Key header
    When the client sends GET /api/v1/evidence
    Then the response status code must be 200
    And the response contains a list of evidence bundle records
