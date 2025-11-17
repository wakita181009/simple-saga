# CI/CD Setup Guide

This document explains the CI/CD pipeline for the Simple Saga library using GitHub Actions.

## Overview

The CI/CD pipeline consists of two main workflows:

1. **CI Workflow** (`.github/workflows/ci.yml`) - Runs on every push and pull request
2. **Publish Workflow** (`.github/workflows/publish.yml`) - Runs on version tags to publish to PyPI

## CI Workflow

### Triggers

- Push to `main` or `dev` branches
- Pull requests targeting `main` or `dev` branches

### Jobs

#### 1. Lint
- Runs `ruff check` to check code quality
- Runs `ruff format --check` to verify code formatting
- Uses Python 3.10

#### 2. Type Check
- Runs `mypy` for static type checking
- Uses Python 3.10

#### 3. Test
- Runs tests with `pytest` (if tests exist)
- Tests on Python 3.10, 3.11, 3.12, and 3.13
- Uses matrix strategy for parallel execution

#### 4. Build
- Builds the package using Poetry
- Uploads build artifacts for verification

### Caching

The workflow uses caching for Poetry virtual environments to speed up builds:
- Cache key: `venv-${{ runner.os }}-${{ matrix.python-version }}-${{ hashFiles('**/poetry.lock') }}`
- Cached path: `.venv`

## Publish Workflow

### Triggers

- Push of version tags matching pattern `v*.*.*` (e.g., `v0.1.0`, `v1.2.3`)

### Jobs

#### 1. Test
- Runs full test suite on all supported Python versions
- Includes linting and type checking
- Must pass before building

#### 2. Build
- Builds distribution packages (wheel and sdist)
- Stores artifacts for publishing

#### 3. Publish to PyPI
- Publishes to PyPI using **Trusted Publishing** (recommended)
- No API tokens required
- Automatic signature verification

#### 4. GitHub Release
- Creates a GitHub release for the tag
- Uploads distribution files to the release

## Setup Instructions

### 1. Configure PyPI Trusted Publishing (Recommended)

Trusted Publishing is the most secure way to publish to PyPI. It uses OpenID Connect (OIDC) to authenticate without API tokens.

1. Go to your PyPI account: https://pypi.org/manage/account/
2. Scroll to "Publishing" section
3. Click "Add a new pending publisher"
4. Fill in the form:
   - **PyPI Project Name**: `simple-saga`
   - **Owner**: Your GitHub username or organization
   - **Repository name**: `simple-saga`
   - **Workflow name**: `publish.yml`
   - **Environment name**: `pypi`
5. Click "Add"

**Note**: For first-time publishing, you need to create the project on PyPI first. After the first release, the trusted publisher will handle subsequent releases automatically.

### Alternative: Using API Token

If you prefer using an API token instead of Trusted Publishing:

1. Generate a PyPI API token:
   - Go to https://pypi.org/manage/account/token/
   - Create a token with scope for your project
2. Add it to GitHub Secrets:
   - Go to your repository settings
   - Navigate to "Secrets and variables" > "Actions"
   - Click "New repository secret"
   - Name: `PYPI_API_TOKEN`
   - Value: Your PyPI API token

3. Modify `.github/workflows/publish.yml`:
   ```yaml
   - name: Publish distribution to PyPI
     uses: pypa/gh-action-pypi-publish@release/v1
     with:
       password: ${{ secrets.PYPI_API_TOKEN }}
   ```

### 2. Configure GitHub Environments (Optional but Recommended)

For additional security, configure a GitHub environment:

1. Go to repository "Settings" > "Environments"
2. Click "New environment"
3. Name it `pypi`
4. Add protection rules:
   - Required reviewers (optional)
   - Deployment branches: Only `main` or specific tags
5. Click "Configure environment"

## Release Process

### Step-by-Step Guide

1. **Update Version**
   ```bash
   # Edit pyproject.toml and update version
   # Example: version = "0.1.0" -> version = "0.2.0"
   ```

2. **Update CHANGELOG** (when created)
   ```markdown
   ## [0.2.0] - 2024-XX-XX
   ### Added
   - New feature X
   ```

3. **Commit Changes**
   ```bash
   git add pyproject.toml CHANGELOG.md
   git commit -m "Bump version to 0.2.0"
   git push origin main
   ```

4. **Create and Push Tag**
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

5. **Monitor Workflow**
   - Go to "Actions" tab in GitHub
   - Watch the "Publish to PyPI" workflow
   - Verify all jobs complete successfully

6. **Verify Publication**
   - Check PyPI: https://pypi.org/project/simple-saga/
   - Check GitHub Releases: https://github.com/yourusername/simple-saga/releases

### Automated Release Script

You can create a helper script for releases:

```bash
#!/bin/bash
# release.sh

set -e

VERSION=$1

if [ -z "$VERSION" ]; then
  echo "Usage: ./release.sh VERSION"
  echo "Example: ./release.sh 0.2.0"
  exit 1
fi

# Update version in pyproject.toml
poetry version "$VERSION"

# Commit and tag
git add pyproject.toml
git commit -m "Bump version to $VERSION"
git push origin main

git tag "v$VERSION"
git push origin "v$VERSION"

echo "✅ Released version $VERSION"
echo "Monitor the workflow at: https://github.com/yourusername/simple-saga/actions"
```

Usage:
```bash
chmod +x release.sh
./release.sh 0.2.0
```

## Troubleshooting

### Build Fails on CI

1. **Lint errors**
   ```bash
   # Run locally to fix issues
   poetry run ruff check simple_saga --fix
   poetry run ruff format simple_saga
   ```

2. **Type check errors**
   ```bash
   # Run locally to identify issues
   poetry run mypy simple_saga
   ```

3. **Test failures**
   ```bash
   # Run tests locally
   poetry run pytest tests/ -v
   ```

### PyPI Publishing Fails

1. **Trusted Publishing not configured**
   - Verify setup at https://pypi.org/manage/account/publishing/
   - Ensure environment name matches (`pypi`)

2. **Version already exists**
   - PyPI doesn't allow re-uploading same version
   - Bump version number and create new tag

3. **Package name conflict**
   - Verify package name in `pyproject.toml`
   - Check if name is available on PyPI

### GitHub Release Fails

1. **Insufficient permissions**
   - Verify workflow has `contents: write` permission
   - Check repository settings for workflow permissions

2. **Tag already exists**
   - Delete tag locally and remotely:
     ```bash
     git tag -d v0.1.0
     git push origin :refs/tags/v0.1.0
     ```

## Best Practices

### Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes (e.g., `1.0.0` → `2.0.0`)
- **MINOR**: New features (e.g., `1.0.0` → `1.1.0`)
- **PATCH**: Bug fixes (e.g., `1.0.0` → `1.0.1`)

### Pre-release Testing

Before tagging:
1. Run full test suite locally
2. Test installation in clean environment:
   ```bash
   python -m venv test_env
   source test_env/bin/activate
   pip install dist/simple_saga-*.whl
   python -c "from simple_saga import SimpleSaga; print('OK')"
   ```

### Changelog Maintenance

Keep CHANGELOG.md updated:
- Document all changes between versions
- Group changes by type (Added, Changed, Fixed, etc.)
- Link to GitHub issues/PRs when relevant

## Monitoring

### GitHub Actions Dashboard

- View all workflow runs: https://github.com/yourusername/simple-saga/actions
- Set up notifications for failed workflows
- Review logs for debugging

### PyPI Statistics

- Download statistics: https://pypistats.org/packages/simple-saga
- Monitor for issues or unexpected downloads

## Security Considerations

1. **Never commit API tokens** - Use GitHub Secrets or Trusted Publishing
2. **Use environment protection** - Require reviews for production deployments
3. **Pin action versions** - Use specific versions (e.g., `v4` not `@latest`)
4. **Audit dependencies** - Regularly update and audit Poetry dependencies
5. **Code signing** - Consider signing releases with GPG

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Poetry Publishing](https://python-poetry.org/docs/libraries/#publishing-to-pypi)
- [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/)
- [Semantic Versioning](https://semver.org/)
- [Keep a Changelog](https://keepachangelog.com/)

## Support

For issues with CI/CD:
- Check GitHub Actions logs
- Review this documentation
- Open an issue at https://github.com/yourusername/simple-saga/issues