# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

**Please do NOT open a public GitHub issue for security vulnerabilities.**

Instead, report vulnerabilities privately using one of these methods:

1. **GitHub Security Advisories** (preferred): Use the "Report a vulnerability" button on the [Security tab](../../security/advisories) of this repository.
2. **Email**: Send details to the repository maintainer listed in the GitHub profile.

### What to Include
- Description of the vulnerability
- Steps to reproduce
- Affected component (sensor agent, CMP server, Docker configuration)
- Potential impact assessment
- Suggested fix (if any)

### Response Timeline
- **Acknowledgment**: Within 48 hours
- **Initial Assessment**: Within 7 days
- **Fix or Mitigation**: Within 30 days for critical issues

### Scope
The following components are in scope for security reports:
- CMP FastAPI server authentication and authorization
- Sensor API key generation and storage
- Wi-Fi credential handling (PSK/EAP secrets in transit and at rest)
- Docker container configurations and exposed ports
- Prometheus/Grafana/Loki access controls
- Sensor registration approval workflow (TOFU)

### Out of Scope
- Vulnerabilities in upstream dependencies (report these to the upstream project directly)
- Denial-of-service attacks against lab/development deployments
- Social engineering
