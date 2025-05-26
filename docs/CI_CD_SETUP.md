# CI/CD Setup Documentation

This document describes the Continuous Integration and Continuous Deployment (CI/CD) setup for the Enterprise RAG Searcher project.

## Overview

The project uses GitHub Actions for CI/CD with multiple workflows designed for different purposes:

1. **Main CI/CD Pipeline** (`.github/workflows/ci.yml`) - Comprehensive testing and deployment
2. **Pull Request Checks** (`.github/workflows/pr-checks.yml`) - Fast feedback for PRs

## Workflows

### 1. Main CI/CD Pipeline (`ci.yml`)

**Triggers:**
- Push to `main` or `develop` branches
- Pull requests to `main` or `develop` branches

**Jobs:**

#### Backend Tests & Quality
- **Services:** PostgreSQL, Redis, MinIO
- **Python Version:** 3.11
- **Steps:**
  - Code formatting check (Black)
  - Import sorting check (isort)
  - Linting (flake8)
  - Security scanning (bandit)
  - Dependency vulnerability check (safety)
  - Unit tests with coverage
  - Integration tests
  - Coverage upload to Codecov

#### Frontend Tests & Quality
- **Node Version:** 18
- **Steps:**
  - TypeScript type checking
  - ESLint linting
  - Prettier formatting check
  - Unit tests with Jest
  - Build verification

#### Security Scanning
- **Tools:** Trivy vulnerability scanner
- **Output:** SARIF format uploaded to GitHub Security tab

#### Docker Build & Push
- **Condition:** Only on `main` branch
- **Images:** Backend and Frontend
- **Registry:** Docker Hub
- **Caching:** GitHub Actions cache

#### Performance Testing
- **Tool:** k6 load testing
- **Condition:** Only on `main` branch after successful build

#### Deployment
- **Environment:** Staging
- **Condition:** Only on `main` branch
- **Includes:** Smoke tests and Slack notifications

### 2. Pull Request Checks (`pr-checks.yml`)

**Purpose:** Fast feedback for pull requests

**Jobs:**

#### PR Validation
- Quick code quality checks
- Formatting and linting validation
- No external services required

#### Quick Tests
- **Services:** PostgreSQL, Redis (minimal setup)
- Fast unit tests only
- Fail-fast approach (`--maxfail=5 -x`)

#### Build Check
- Frontend build verification
- Docker build validation

## Configuration Files

### Backend Configuration

#### `core-api/pyproject.toml`
- **Black:** Code formatting (line length: 100)
- **isort:** Import sorting
- **pytest:** Test configuration and markers
- **coverage:** Coverage reporting configuration
- **bandit:** Security scanning configuration
- **mypy:** Type checking configuration

### Frontend Configuration

#### `frontend/package.json`
- **Scripts:** Added CI/CD specific scripts
  - `type-check`: TypeScript validation
  - `format:check`: Prettier validation
  - `test:ci`: Jest with coverage for CI

#### `frontend/.prettierrc`
- Code formatting configuration
- 100 character line length
- Single quotes, trailing commas

#### `frontend/jest.config.js`
- Jest testing configuration
- Coverage thresholds (70% minimum)
- Next.js integration

#### `frontend/jest.setup.js`
- Test environment setup
- Mocks for Next.js router and browser APIs

## Performance Testing

### Load Testing with k6

**File:** `tests/performance/load-test.js`

**Test Scenarios:**
- Health check endpoints
- Authentication flows
- File listing operations
- Search functionality
- Chat interactions

**Configuration:**
- Ramp up: 10 → 20 users over 16 minutes
- Thresholds:
  - 95% of requests < 2 seconds
  - Error rate < 10%

## Required GitHub Secrets

For full CI/CD functionality, configure these secrets in your GitHub repository:

### Docker Hub Integration
```
DOCKER_USERNAME=your_dockerhub_username
DOCKER_PASSWORD=your_dockerhub_password
```

### Performance Testing (Optional)
```
K6_CLOUD_TOKEN=your_k6_cloud_token
```

### Deployment Notifications (Optional)
```
SLACK_WEBHOOK=your_slack_webhook_url
```

## Local Development

### Backend Code Quality

```bash
cd core-api

# Install development dependencies
pip install black isort flake8 bandit safety pytest-cov

# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/ --max-line-length=100 --ignore=E203,W503

# Security check
bandit -r src/

# Run tests with coverage
pytest tests/unit/ --cov=src --cov-report=html
```

### Frontend Code Quality

```bash
cd frontend

# Install dependencies
npm install

# Type check
npm run type-check

# Lint
npm run lint

# Format
npm run format

# Test
npm run test
```

## Monitoring and Alerts

### Coverage Reporting
- **Tool:** Codecov
- **Threshold:** Configured per project needs
- **Reports:** HTML, XML, and terminal output

### Security Scanning
- **Tools:** Bandit (Python), Trivy (containers)
- **Integration:** GitHub Security tab
- **Format:** SARIF for security findings

### Performance Monitoring
- **Tool:** k6 performance tests
- **Metrics:** Response times, error rates, throughput
- **Thresholds:** Configurable per environment

## Deployment Strategy

### Staging Environment
- **Trigger:** Successful builds on `main` branch
- **Process:** Automated deployment with smoke tests
- **Rollback:** Manual process (documented separately)

### Production Environment
- **Trigger:** Manual approval after staging validation
- **Process:** Blue-green deployment (when configured)
- **Monitoring:** Health checks and performance metrics

## Troubleshooting

### Common Issues

#### Test Failures
1. **Database Connection:** Ensure PostgreSQL service is healthy
2. **Import Errors:** Check Python path configuration
3. **Type Errors:** Run `npm run type-check` locally

#### Build Failures
1. **Docker Build:** Verify Dockerfile syntax
2. **Dependencies:** Check for version conflicts
3. **Environment Variables:** Ensure all required vars are set

#### Performance Test Failures
1. **Timeouts:** Adjust k6 thresholds
2. **Authentication:** Verify test user credentials
3. **Service Availability:** Check endpoint accessibility

### Debug Commands

```bash
# Check workflow status
gh workflow list

# View workflow runs
gh run list

# Download artifacts
gh run download <run-id>

# View logs
gh run view <run-id> --log
```

## Best Practices

### Code Quality
1. **Always run local checks** before pushing
2. **Write tests** for new functionality
3. **Keep coverage** above configured thresholds
4. **Follow formatting** standards consistently

### Security
1. **Never commit secrets** to repository
2. **Use GitHub secrets** for sensitive data
3. **Review security scan results** regularly
4. **Update dependencies** frequently

### Performance
1. **Monitor test execution times** and optimize slow tests
2. **Use caching** effectively in workflows
3. **Parallelize jobs** where possible
4. **Optimize Docker builds** with multi-stage builds

## Future Enhancements

### Planned Improvements
1. **Matrix Testing:** Multiple Python/Node versions
2. **Environment Promotion:** Automated production deployment
3. **Advanced Monitoring:** Prometheus/Grafana integration
4. **Chaos Engineering:** Resilience testing
5. **Mobile Testing:** Cross-platform validation

### Integration Opportunities
1. **Code Quality Gates:** SonarQube integration
2. **Security Scanning:** Additional SAST/DAST tools
3. **Performance Monitoring:** APM tool integration
4. **Documentation:** Automated API documentation updates 