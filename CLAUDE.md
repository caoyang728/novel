# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Novel Agent is a Django 5.2 web app that helps authors build novel outlines, volumes, chapters, characters, world-building settings, and timelines through chat-style AI interaction. It uses an OpenAI-compatible LLM API (defaults to DeepSeek) via LangChain for all AI features, with Server-Sent Events (SSE) for streaming responses.

## Commands

```bash
# Activate virtual environment and run dev server
source .venv/Scripts/activate
python manage.py runserver

# Database migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Running a single test file
python manage.py test apps.<app_name>.tests

# Install dependencies
pip install -r requirements.txt
```

## Architecture

### URL and routing pattern

All views use `apps/<app>/urls.py` with `path('', include(...))` in the root `novel_agent/urls.py`. Frontend HTML pages are served as static files from the `templates/` directory via individual `path()` entries in the main URL config. API endpoints are under `/api/`.

### Apps (Django apps in `apps/`)

| App | Purpose |
|-----|---------|
| `project` | Core ProjectList model, Character, Worldview, WorldviewChatHistory |
| `outline` | OutlineVersion, OutlineChatHistory, OutlineExpansion — chat-driven outline building with SSE streaming |
| `volume` | VolumeVersion, VolumeList — volume structure generation from outlines |
| `chapter` | ChapterVersion, ChapterList — chapter summaries, content generation, streaming |
| `worlds` | World — structured world-building with JSON fields and snapshots |
| `characters` | Character generation prompts only (models live in `project`) |
| `timeline` | TimelineEvent, TimelineChatHistory — chapter-range-based story timeline |
| `note` | Note — freeform "jot notes" with AI polish |
| `ai` | LLMService (central AI service), LLM wrapper (`llm.py`), all prompt templates |
| `user` | User LLM configs (LLMConfig, UserLLMConfig), TokenUsageLog, JWT auth views |

### LLM layer (`apps/ai/`)

- **`llm.py`**: Thin wrapper around LangChain's `ChatOpenAI`. `LLM` class handles config merging, streaming vs. non-streaming invocation, and retry logic. `LLMConfig` specifies model, temperature, max_tokens, timeout, etc.
- **`services.py`**: `LLMService` — the central AI service. All generation methods (outline chat, volumes, chapters, characters, world-building, titles, descriptions, note polish) live here. Uses `_call_with_retry` for all LLM calls. Parses LLM responses — some methods expect JSON, others use custom delimiters (e.g., `════CONTENT_START════` / `════ITEM_START════`).
- **`prompts.py`**: All prompt templates as module-level string constants. Very large — includes full system prompts for outline building, volume generation, chapter content, world-building, character generation, timeline planning, and note polishing.

### Streaming pattern

SSE responses use `StreamingHttpResponse` with `text/event-stream` content type. Data is yielded as `data: {json}\n\n` chunks. The LLM returns raw text chunks which are forwarded directly to the frontend. After the stream completes, the backend extracts structured content (using regex on delimiters like `════CONTENT_START════...════CONTENT_END════`) and persists to the database in a transaction.

### Data model conventions

- **Soft delete**: Most models use `is_deleted` boolean field instead of hard deletes.
- **Versioning**: Outline, Volume, and Chapter have version models (e.g., `OutlineVersion`, `VolumeVersion`, `ChapterVersion`) supporting multiple versions per parent, with `is_finalized`, `is_current`, and `is_deleted` flags. `version_number=0` means a "building/draft" version.
- **Chat history**: `OutlineChatHistory`, `WorldviewChatHistory`, `TimelineChatHistory` store role + content pairs linked to their parent model.

### Authentication

Custom JWT middleware (`novel_agent/middleware.py`) handles both API requests (401 on missing token) and page requests (redirect to `/login/`). API views use DRF's `JWTAuthentication` + `IsAuthenticated`. The custom `novel_agent/authentication.py` overrides DRF's JWTAuthentication to return `None` instead of raising on invalid tokens (so unauthenticated page requests fall through to the middleware redirect).

### Frontend

Django Templates with Bootstrap 5. All HTML pages live in `templates/`. JavaScript in the templates handles SSE consumption and dynamic UI updates. No separate frontend build step.

### Key environment variables (`.env`)

- `LLM_API_KEY`, `LLM_MODEL`, `LLM_BASE_URL` — LLM configuration
- `MYSQL_DB_*` — MySQL database connection
- `REDIS_DB_*` — Redis cache connection

### Logging

Uses `loguru` throughout (`from loguru import logger`). Not Django's standard logging.
