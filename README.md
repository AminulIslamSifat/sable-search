# Sable Search Engine

Standalone multi-provider search API. Built to serve [Sable](https://github.com/sifat) but designed so **any tool, script, or app** can consume it via a clean REST interface.

## Quick Start

### Local (recommended)
```bash
cd sable-search-engine
uv run python server.py
```
Opens on `http://0.0.0.0:8080` by default. API docs at `/docs`.

### Docker (with SearXNG sidecar)
```bash
docker-compose up
```
Starts both SSE and a SearXNG instance. SSE auto-points at the sidecar.

### Render (one-click)
Deploy using `render.yaml`. Set your `SSE_SEARXNG_URL` env var to point at a SearXNG instance (or use a public one).

***

## API Reference

### `GET /search`
The main endpoint.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `q` | string | *required* | Search query |
| `count` | int | 10 | Results to return (1-50) |
| `provider` | string | auto | Force a specific provider |
| `time_filter` | string | null | `day`, `week`, `month`, `year` |
| `categories` | string | general | `general`, `news`, `images` |

**Response:**
```json
{
  "query": "rust async runtime",
  "provider_used": "searxng",
  "results_count": 10,
  "cached": false,
  "results": [
    {"title": "...", "url": "...", "snippet": "...", "score": 4.2}
  ],
  "meta": {"response_time_ms": 234, "fallback_used": false}
}
```

### `GET /health`
Returns status of all providers (configured, has keys, etc.)

### `GET /providers`
Lists available providers with configuration status.

### `GET /config`
Returns current runtime config (API keys redacted).

### `POST /config`
Update runtime config (JSON body). Does NOT persist to disk.

### `DELETE /cache`
Clear cache. Optional `?q=query` to clear specific query across all providers.

***

## Providers

| Provider | Needs Key | Needs URL | Notes |
|----------|-----------|-----------|-------|
| **searxng** | No | Yes | **Default.** Meta-search engine. JSON API + HTML fallback. |
| **duckduckgo** | No | No | HTML scraping. Chrome UA required. 4s throttle built-in. |
| **brave** | Yes | No | Brave Search API v1. Multi-key rotation on 429. |
| **google_pse** | Yes | No | Google Custom Search. Needs API key + CX ID. |
| **tavily** | Yes | No | Tavily search API. Multi-key rotation. |
| **serper** | Yes | No | Serper.dev API. Multi-key rotation. |

***

## Configuration

Edit `config.yaml` or use environment variables prefixed with `SSE_`.

### Environment Variables

| Env Var | Config Path | Example |
|---------|-------------|--------|
| `SSE_HOST` | server.host | `0.0.0.0` |
| `SSE_PORT` | server.port | `8080` |
| `SSE_DEFAULT_PROVIDER` | default_provider | `duckduckgo` |
| `SSE_SEARXNG_URL` | providers.searxng.url | `https://search.example.com` |
| `SSE_BRAVE_API_KEYS` | providers.brave.api_keys | `key1,key2` (comma-separated) |
| `SSE_TAVILY_API_KEYS` | providers.tavily.api_keys | `tvly-xxx` |
| `SSE_SERPER_API_KEYS` | providers.serper.api_keys | `key1,key2` |
| `SSE_GOOGLE_PSE_API_KEYS` | providers.google_pse.api_keys | `key1` |
| `SSE_GOOGLE_PSE_CX` | providers.google_pse.cx | `abc123` |
| `SSE_FALLBACK_CHAIN` | fallback_chain | `duckduckgo,brave` |
| `SSE_SAFESEARCH` | safesearch | `off`, `moderate`, `strict` |

### Fallback Chain
When the primary provider fails or returns empty results, SSE tries the next provider in the chain automatically. Configure via `config.yaml`:
```yaml
default_provider: searxng
fallback_chain:
  - duckduckgo
  - brave
```
Or via env: `SSE_FALLBACK_CHAIN=duckduckgo,brave`

***

## Using with Sable

Point Sable's search URL at this service:
```bash
export SEARXNG_INSTANCE="http://localhost:8080/search?q={query}&format=json"
```
Or in Sable's settings, set the SearXNG instance URL to `http://localhost:8080`.

***

## Architecture

```
Request → Query Parser → Cache Check → Provider Dispatcher → Fallback Chain → Ranker → Response
```

- **Query Parser**: Extracts `site:` filters, time hints, question detection, entities
- **Cache**: SQLite with LRU eviction. News TTL: 30min. Reference TTL: 24h.
- **Provider Dispatcher**: Tries primary → fallback chain. Skips unconfigured providers.
- **Ranker**: Scores by title match, snippet quality, domain authority (.edu/.gov boost), deduplicates by URL.

***

## License
MIT
