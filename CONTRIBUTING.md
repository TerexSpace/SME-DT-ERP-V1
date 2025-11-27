# Contributing to SME-DT-ERP

Thank you for your interest in contributing to SME-DT-ERP! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)

## Code of Conduct

This project adheres to a code of conduct. By participating, you are expected to uphold this code. Please be respectful and constructive in all interactions.

## Getting Started

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/YOUR-USERNAME/sme-dt-erp.git
   cd sme-dt-erp
   ```
3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

## How to Contribute

### Reporting Bugs

- Check existing issues to avoid duplicates
- Use the bug report template
- Include: Python version, OS, steps to reproduce, expected vs actual behavior

### Suggesting Features

- Open an issue with the feature request template
- Describe the use case and expected behavior
- Explain how it benefits SME warehouse operations

### Contributing Code

1. Create a feature branch: `git checkout -b feature/your-feature-name`
2. Make your changes
3. Add tests for new functionality
4. Ensure all tests pass: `pytest tests/ -v`
5. Update documentation if needed
6. Submit a pull request

## Development Setup

### Prerequisites

- Python 3.9 or higher
- Git
- Docker (optional, for containerized testing)

### Installation

```bash
# Clone repository
git clone https://github.com/[username]/sme-dt-erp.git
cd sme-dt-erp

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e ".[dev]"

# Verify installation
python -c "from sme_dt_erp import SimulationConfig; print('OK')"
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=sme_dt_erp --cov-report=html

# Run specific test file
pytest tests/test_core.py -v

# Run specific test
pytest tests/test_core.py::TestSimulationConfig::test_default_values -v
```

## Coding Standards

### Python Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Maximum line length: 88 characters (Black default)
- Use descriptive variable and function names

### Code Formatting

We use the following tools:

```bash
# Format code with Black
black sme_dt_erp/ tests/

# Sort imports with isort
isort sme_dt_erp/ tests/

# Check style with flake8
flake8 sme_dt_erp/ tests/

# Type checking with mypy
mypy sme_dt_erp/
```

### Documentation

- All public functions must have docstrings (Google style)
- Update README.md for user-facing changes
- Add inline comments for complex logic

### Docstring Example

```python
def calculate_throughput(orders_completed: int, duration_hours: float) -> float:
    """Calculate warehouse throughput in orders per hour.

    Args:
        orders_completed: Total number of orders completed.
        duration_hours: Simulation duration in hours.

    Returns:
        Throughput rate in orders per hour.

    Raises:
        ValueError: If duration_hours is zero or negative.

    Example:
        >>> calculate_throughput(50, 8.0)
        6.25
    """
    if duration_hours <= 0:
        raise ValueError("Duration must be positive")
    return orders_completed / duration_hours
```

## Testing

### Test Requirements

- All new features must have corresponding tests
- Maintain test coverage above 80%
- Tests should be deterministic (use fixed random seeds)

### Test Categories

1. **Unit Tests**: Test individual functions and classes
2. **Integration Tests**: Test component interactions
3. **Performance Tests**: Ensure acceptable execution times

### Writing Tests

```python
import pytest
from sme_dt_erp import SimulationConfig, WarehouseDigitalTwin

class TestNewFeature:
    """Tests for the new feature."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        return SimulationConfig(simulation_time=60.0, random_seed=42)

    def test_feature_basic(self, config):
        """Test basic functionality."""
        # Arrange
        expected = 10

        # Act
        result = some_function(config)

        # Assert
        assert result == expected

    def test_feature_edge_case(self, config):
        """Test edge case handling."""
        with pytest.raises(ValueError):
            some_function(invalid_input)
```

## Submitting Changes

### Pull Request Process

1. Update documentation for any changed functionality
2. Add tests for new features
3. Ensure CI passes (all tests, linting, type checks)
4. Update CHANGELOG.md with your changes
5. Request review from maintainers

### Commit Messages

Follow conventional commits format:

```
type(scope): description

[optional body]

[optional footer]
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Examples:
- `feat(simulation): add support for multiple warehouse zones`
- `fix(erp-adapter): handle connection timeout gracefully`
- `docs(readme): add Docker installation instructions`

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Tests added/updated
- [ ] All tests pass locally

## Checklist
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] CHANGELOG.md updated
```

## Questions?

- Open an issue for questions
- Email: a.ospanov@astanait.edu.kz

Thank you for contributing!
