# License: GNU AGPLv3 (GNU Affero General Public License v3.0)
Feature: Zero-Trust Security and Administrative Access Control

  Scenario: Rejecting default API keys in production mode
    Given the CMP environment variable "ENVIRONMENT" is set to "production"
    And the administrative key is set to "admin-noc-key-change-me"
    When the CMP server starts up
    Then the server must abort execution with a SystemExit and raise a critical configuration error

  Scenario: Constant-time API key verification
    Given an administrative API key "noc-secret-key-12345"
    When a request provides an invalid key "wrong-key-99999"
    Then the validation must execute in constant time using secrets.compare_digest
    And the API endpoint must return HTTP 401 Unauthorized

  Scenario: Session token generation and validation
    Given a valid admin login request with username "admin"
    When the login endpoint authenticates the credentials
    Then an HMAC-SHA256 signed session token is generated
    And the token is delivered via an HttpOnly SameSite=lax cookie
