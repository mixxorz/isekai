# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Testing
- Run all tests: `uv run pytest`
- Run specific test file: `uv run pytest tests/test_seeders.py`
- Run specific test: `uv run pytest tests/test_seeders.py::TestCSVSeeder::test_csv_seeder`
- Run tests with network recording: `uv run pytest --record-mode=once`

### Code Quality
- Lint code: `uv run tox -e lint`
- Format code: `uv run ruff format .`
- Type check: `uv run tox -e type`
- Run all quality checks: `uv run tox -e lint,type`

### Django Development Environment
- Start Django shell: `PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py shell`
- Run migrations: `PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py migrate`
- Check Django setup: `PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py check`
- Import test: `PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py shell -c "from isekai.models import AbstractResource; print('isekai import successful')"`

### ETL Operations
- Run full pipeline: `PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py isekai`
- Skip confirmation prompt: `PYTHONPATH=/Users/mixxorz/Projects/isekai uv run python dev/manage.py isekai --no-input`

### Multi-Environment Testing
- Test across Python/Django versions: `uv run tox`
- Test specific environment: `uv run tox -e py311-django51`

## Architecture Overview

### Core Concept: ETL Pipeline for Resources
Isekai is a Django package that implements an ETL (Extract, Transform, Load) pipeline for processing resources through distinct status phases:

1. **SEEDED** → **EXTRACTED** → **MINED** → **TRANSFORMED** → **LOADED**

Each resource has a unique key (like `url:https://example.com` or `file:document.pdf`) and progresses through these statuses via controlled transitions.

### Key Components

#### AbstractResource Model (`isekai/models.py`)
- Abstract Django model that apps must subclass to create concrete Resource models
- Tracks resource lifecycle with status transitions and timestamps
- Stores both text and binary data with FileField for blobs
- Uses GenericForeignKey to link to target objects
- **Critical**: Apps must create a concrete subclass in their models.py

#### Extractor System (`isekai/extractors.py`)
- `BaseExtractor`: Abstract base class for data extraction
- `HTTPExtractor`: Fetches data from HTTP URLs, handles MIME type detection
- **Pattern**: Extractors are assigned to Resource models via class attribute
- Supports both text and binary data with intelligent content-type detection

#### Seeder System (`isekai/seeders.py`)
- `BaseSeeder`: Abstract base for generating resource keys
- `CSVSeeder`: Reads resource keys from CSV files with `type,value` columns
- `SitemapSeeder`: Extracts URLs from XML sitemap files
- **Pattern**: Supports both constructor parameters and class attributes for configuration

#### Operations (`isekai/operations.py`)
- `extract()`: Processes SEEDED resources through their extractor, transitions to EXTRACTED
- Uses bulk operations for efficiency
- Comprehensive error handling with `last_error` tracking

#### Management Commands (`isekai/management/commands/`)
- `isekai`: Runs the full ETL pipeline (seed → extract → mine → transform → load)
- Supports `--no-input` flag to skip the confirmation prompt

### Development Patterns

#### Resource Model Pattern
Apps must create a concrete Resource model:
```python
from isekai.models import AbstractResource
from isekai.extractors import HTTPExtractor

class Resource(AbstractResource):
    extractor = HTTPExtractor()
```

#### Type System
- Uses modern Python typing with `|` union syntax
- Critical types: `ResourceData`, `BinaryData`, `TransitionError`
- Strict type checking with pyright

#### Testing Approach
- Uses pytest with Django integration
- VCR.py for HTTP request recording (`pytest-recording`)
- Network isolation by default (`--block-network`)
- Mock external services with `responses` library

#### Code Style Guidelines

##### 🚨 CRITICAL - Import Rules (FREQUENTLY VIOLATED)
- **NEVER EVER use inline imports** - ALL imports must be at the top of files, never inside functions or methods. This is a strict rule with no exceptions.
- **❌ WRONG - Inline imports:**
  ```python
  def test_something():
      from django.contrib.contenttypes.models import ContentType  # NEVER DO THIS
      from isekai.types import BlobRef  # NEVER DO THIS
  ```
- **✅ CORRECT - Top-level imports:**
  ```python
  from django.contrib.contenttypes.models import ContentType
  from isekai.types import BlobRef

  def test_something():
      # Use imports here
  ```

##### Pre-Code Checklist (CHECK EVERY TIME)
Before writing any code:
- [ ] Are ALL imports at the top of the file?
- [ ] Am I about to write `from ... import ...` inside a function? (If yes, STOP and move it to top)
- [ ] If I need a new import, did I add it to the top immediately?

##### Other Style Rules
- **Avoid excessive comments** - Only add comments when code behavior isn't obvious from reading it. Avoid "what this does" comments that just repeat the code
- Follow existing code conventions and patterns in the codebase

### Project Structure Notes
- `dev/`: Contains test Django project for development
- `tests/`: Test suite separate from Django test project
- `isekai/`: Main package code
- Uses `uv` for dependency management
- Multi-Python/Django version testing via tox

### Utility Functions
- `get_resource_model()`: Discovers concrete AbstractResource subclass at runtime
- Essential for operations that need to work with user's Resource model
