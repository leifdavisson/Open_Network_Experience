# Contributing to Open Network Experience (ONE)

Thank you for your interest in contributing to the **Open Network Experience (ONE)** platform! This project is licensed under the **AGPLv3** license.

## Development Setup

### Prerequisites
- Python 3.11+
- Docker & Docker Compose
- Git

### Local Development
```bash
# Clone the repository
git clone https://github.com/<your-username>/Open_Network_Experience.git
cd Open_Network_Experience

# Start the CMP server stack
cd server/deploy
docker compose up --build -d

# Run the integration tests
cd ../..
python server/test_integration.py
```

### Code Style
- Follow PEP 8 for Python code
- All Python files must include module-level docstrings
- All public functions must include docstrings
- Use type hints where practical
- Target a Pylint score of 7.0 or higher

### Testing
Before submitting a pull request:
1. Ensure all Python files compile: `python -m py_compile <file>`
2. Ensure shell scripts parse: `bash -n <script>`
3. Run the integration test suite: `python server/test_integration.py`
4. Verify Docker images build: `docker build -t test server/`

### Pull Requests
1. Fork the repository and create a feature branch from `main`
2. Write clear commit messages describing the change
3. Include tests for new functionality
4. Update relevant documentation (READMEs, docstrings)
5. Ensure all CI checks pass before requesting review

## Reporting Issues
Use GitHub Issues to report bugs. Include:
- Steps to reproduce
- Expected vs actual behavior
- Sensor hardware (if applicable)
- Docker/OS version information
