# Testing Guide for SPDS

This document explains how to run tests and contribute new tests to the Subjective Priority-Driven Swarm (SPDS) project.

## Test Structure

The test suite is organized into three levels:

```
tests/
├── unit/           # Fast, isolated tests for individual components
├── integration/    # Tests for component interactions
├── e2e/           # End-to-end tests for complete user scenarios
├── conftest.py    # Shared fixtures and configuration
└── __init__.py
```

## Running Tests

### Prerequisites

Ensure you have the testing dependencies installed:
```bash
pip install -r requirements.txt
```

### Running All Tests

```bash
# Run the complete test suite
pytest

# Run with coverage report
pytest --cov=spds --cov-report=html

# Run with verbose output
pytest -v
```

### Running Specific Test Categories

```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run only end-to-end tests
pytest tests/e2e/

# Run tests by marker
pytest -m unit
pytest -m integration
pytest -m e2e
```

### Running Specific Test Files

```bash
# Run specific test file
pytest tests/unit/test_tools.py

# Run specific test class
pytest tests/unit/test_spds_agent.py::TestSPDSAgent

# Run specific test method
pytest tests/unit/test_tools.py::TestSubjectiveAssessment::test_valid_assessment_creation
```

### Test Options

```bash
# Stop on first failure
pytest -x

# Show local variables in tracebacks
pytest -l

# Run tests in parallel (with pytest-xdist)
pytest -n auto

# Run only tests that failed last time
pytest --lf

# Run tests that failed and were fixed
pytest --ff
```

## Test Categories

### Unit Tests (`tests/unit/`)

Fast, isolated tests that test individual components without external dependencies.

**Files:**
- `test_tools.py` - Tests for SubjectiveAssessment model and assessment logic
- `test_spds_agent.py` - Tests for SPDSAgent creation, configuration, and methods
- `test_swarm_manager.py` - Tests for SwarmManager initialization and orchestration

**Characteristics:**
- No external API calls
- Extensive use of mocks
- Fast execution (< 1 second per test)
- High coverage of edge cases

### Integration Tests (`tests/integration/`)

Tests that verify components work together correctly, especially the new model diversity features.

**Files:**
- `test_model_diversity.py` - Tests for per-agent model configuration and diverse swarms

**Characteristics:**
- Tests component interactions
- Mocked Letta server
- Focus on data flow between components
- Moderate execution time (1-5 seconds per test)

### End-to-End Tests (`tests/e2e/`)

Complete user scenario tests that simulate real usage patterns.

**Files:**
- `test_user_scenarios.py` - Full workflow tests from start to finish

**Characteristics:**
- Complete user scenarios
- Mocked external dependencies
- Tests CLI interfaces
- Longer execution time (5-15 seconds per test)

## Writing New Tests

### Test Naming Conventions

- Test files: `test_<module_name>.py`
- Test classes: `Test<ClassName>`
- Test methods: `test_<specific_behavior>`

### Using Fixtures

Common fixtures are available in `conftest.py`:

```python
def test_agent_creation(mock_letta_client, sample_agent_profiles):
    """Example test using shared fixtures."""
    # mock_letta_client and sample_agent_profiles are automatically available
    pass
```

### Mocking Guidelines

1. **Mock external dependencies** - Always mock Letta client calls
2. **Use realistic test data** - Base mocks on actual API responses
3. **Test error conditions** - Include tests for failure scenarios
4. **Verify call patterns** - Assert that mocks are called correctly

Example mocking pattern:
```python
@patch('spds.spds_agent.config')
def test_with_config_mock(self, mock_config, mock_letta_client):
    mock_config.DEFAULT_AGENT_MODEL = "test-model"
    # Test implementation
```

### Test Data

Use the shared fixtures for consistent test data:
- `sample_agent_profiles` - Standard agent configurations
- `sample_conversation_history` - Realistic conversation data
- `sample_assessment` - Valid SubjectiveAssessment instances
- `mock_letta_client` - Pre-configured Letta client mock

### Testing Model Diversity

When testing model diversity features:

```python
def test_diverse_models(self, mock_letta_client):
    profiles = [
        {
            "name": "Agent 1",
            "persona": "Test agent",
            "expertise": ["testing"],
            "model": "openai/gpt-4",
            "embedding": "openai/text-embedding-ada-002"
        },
        {
            "name": "Agent 2",
            "persona": "Another agent",
            "expertise": ["analysis"],
            "model": "anthropic/claude-3-5-sonnet-20241022",
            "embedding": "openai/text-embedding-ada-002"
        }
    ]
    # Test that different models are used correctly
```

## Coverage Requirements

- **Minimum overall coverage**: 85%
- **Critical components coverage**: 95%
  - `tools.py`
  - `spds_agent.py`
  - `swarm_manager.py`

## Targets by Group

Clear targets help keep our suite fast, reliable, and meaningful. These are the expectations per group and what they gate in CI.

### Unit Tests

- Purpose: Validate small units (functions/classes) in isolation with full mocking at boundaries.
- Runtime: Entire unit suite completes in under 60 seconds on CI; individual tests typically < 200 ms.
- Coverage targets:
    - New/changed code: ≥ 95% line coverage, ≥ 90% branch coverage where practical
    - Utilities and pure functions: aim for ~100% line coverage
- Flakiness: 0% tolerated (no retries). Tests must be deterministic (seed randomness where used).
- Isolation: No network, filesystem, or environment dependencies unless explicitly mocked.
- CI gating: Required on every PR and on main; failures block merges.

### Integration Tests

- Purpose: Verify component interactions and data flow across modules (mock external services only).
- Runtime: Full integration suite ≤ 5 minutes on CI; individual tests typically ≤ 5 seconds.
- Coverage targets:
    - Not line-coverage driven, but ensure each critical interaction path is exercised.
    - Aim for ≥ 80% coverage on integration-focused modules where feasible.
- Flakiness: < 0.5% (no flaky known failures). Retries disabled by default; fix root causes.
- Environment: Use shared fixtures and temporary resources; no real network calls.
- CI gating: Required on every PR and on main; failures block merges.

### End-to-End (E2E) Tests

- Purpose: Validate complete user scenarios through CLI and key workflows with external dependencies mocked.
- Runtime: Full E2E pack ≤ 10 minutes on CI; a smoke subset ≤ 2 minutes for PRs.
- Coverage targets: Scenario coverage over line coverage; ensure top user journeys are covered and remain stable.
- Flakiness: < 2% tolerated. One retry allowed in CI; capture logs/artifacts for failures.
- Scope: Prefer a compact set of stable scenarios; avoid brittle UI timing assumptions.
- CI gating:
    - PRs: Run a smoke subset (fast) and gate merges.
    - Nightly/On main: Run full E2E suite; failures create alerts/issues.

### General Targets (All Groups)

- No external network calls (use mocks/fakes); tests must be deterministic.
- Parallel-safe: Tests should pass with `-n auto`.
- Clear diagnostics: Failures must show actionable messages; prefer `assert …, "why"`.
- Keep per-test runtime small; prefer more granular tests over large slow ones.

### Checking Coverage

```bash
# Generate coverage report
pytest --cov=spds --cov-report=html

# View HTML report
open htmlcov/index.html

# Terminal coverage report
pytest --cov=spds --cov-report=term-missing
```

## Continuous Integration

Tests should pass in CI environments. Key considerations:

- **No external dependencies** - All tests use mocks
- **Deterministic behavior** - Tests should not rely on random behavior
- **Fast execution** - Unit tests complete in under 30 seconds total
- **Clear failure messages** - Tests should clearly indicate what failed

## Debugging Test Failures

### Common Issues

1. **Import errors** - Ensure PYTHONPATH includes project root
2. **Mock configuration** - Verify mocks are set up before usage
3. **Async/await issues** - Use `pytest-asyncio` for async tests
4. **Fixture scope** - Check fixture scope matches test needs

### Debugging Commands

```bash
# Run with pdb debugger
pytest --pdb

# Capture stdout (for debugging print statements)
pytest -s

# Run specific failing test with verbose output
pytest -vvs tests/unit/test_spds_agent.py::TestSPDSAgent::test_create_new_agent
```

### Test Isolation

If tests are interfering with each other:

```bash
# Run tests without pytest cache
pytest --cache-clear

# Run in random order to detect dependencies
pytest --random-order
```

## Contributing New Tests

### Before Writing Tests

1. **Understand the requirement** - What behavior needs testing?
2. **Choose the right level** - Unit, integration, or E2E?
3. **Check existing tests** - Avoid duplication
4. **Plan test data** - Use or extend shared fixtures

### Test Development Workflow

1. **Write a failing test** - Red phase
2. **Make it pass** - Green phase
3. **Refactor** - Clean up code and tests
4. **Verify coverage** - Ensure new code is covered

### Code Review Checklist

- [ ] Tests are in the correct directory
- [ ] Test names clearly describe the behavior
- [ ] Mocks are used appropriately
- [ ] Edge cases are covered
- [ ] Tests are independent and can run in any order
- [ ] Documentation is updated if needed

## Performance Testing

For performance-critical changes:

```bash
# Time test execution
pytest --durations=10

# Profile memory usage (with pytest-memray)
pytest --memray

# Benchmark tests (with pytest-benchmark)
pytest --benchmark-only
```

## Test Configuration

### pytest.ini Settings

The project uses these pytest configurations:
- **Test discovery**: Automatic detection of test files
- **Coverage**: Integrated coverage reporting
- **Async support**: Enabled for async/await tests
- **Markers**: Organized test categorization

### Environment Variables

Tests may use these environment variables:
- `PYTEST_CURRENT_TEST` - Available during test execution
- `CI` - Detects CI environment for conditional test behavior

## Troubleshooting

### Common Test Failures

1. **Mock not called** - Verify the code path actually uses the mocked function
2. **Assertion mismatch** - Check that expected vs actual values are correct type
3. **Fixture not found** - Ensure fixtures are imported or defined in conftest.py
4. **Async/sync mismatch** - Use appropriate async fixtures for async code

### Getting Help

- **Check test output** - Pytest provides detailed failure information
- **Use print statements** - Add temporary debugging output with `-s` flag
- **Run subset of tests** - Isolate the failing test
- **Check git history** - See what changed recently in failing tests

## Best Practices

1. **Test behavior, not implementation** - Focus on what the code does, not how
2. **Keep tests simple** - One concept per test
3. **Use descriptive names** - Test names should explain the scenario
4. **Arrange, Act, Assert** - Structure tests clearly
5. **Mock at the boundary** - Mock external dependencies, not internal logic
6. **Test edge cases** - Include boundary conditions and error scenarios
7. **Maintain tests** - Update tests when behavior changes
