# GitHub Monitor

Technische opdracht voor Lely (Data Engineer).

Deze applicatie **streamt GitHub-events** (`WatchEvent`, `PullRequestEvent`, `IssuesEvent`) via een **ETL-pipeline** naar een SQLite-database en maakt **statistieken op ieder moment beschikbaar via een REST API**.

```
GitHub API ──(extract)──▶ transform ──(load)──▶ SQLite ◀──(query)── REST API ◀── gebruiker
```

- Diagram (C4 level 1): [docs/c4-context.md](docs/c4-context.md)

## Snel starten

**Vereist:** [uv](https://docs.astral.sh/uv/getting-started/installation/). uv installeert zelf de juiste Python-versie (3.12).

```bash
uv sync                    # installeer dependencies
uv run github-monitor      # start de API + collector op http://127.0.0.1:8000
```

Open **http://127.0.0.1:8000/docs** voor de interactieve API-documentatie (Swagger). Na ongeveer een minuut staan de eerste events in de database.

**Aanbevolen:** zet een GitHub-token en kies een of meer repo's om extra te volgen. Zonder repo's is de PR-statistiek bijna altijd leeg, omdat een repo zelden twee keer in de GitHub-brede stroom voorkomt. Zonder token staat GitHub 60 requests per uur toe, met token 5000. Elke extra repo kost een request per minuut, dus met repo's is een token nodig. Een fine-grained token zonder extra rechten is genoeg.

```bash
# bash
export GITHUB_TOKEN=github_pat_...
export GITHUB_REPOS=home-assistant/core

# PowerShell
$env:GITHUB_TOKEN = "github_pat_..."
$env:GITHUB_REPOS = "home-assistant/core"
```

| Variabele | Standaard | Betekenis |
|---|---|---|
| `GITHUB_TOKEN` | *(leeg)* | Optioneel GitHub-token |
| `GITHUB_REPOS` | *(leeg)* | Repo's die naast heel GitHub extra gepolld worden, kommagescheiden |
| `DB_PATH` | `data/events.db` | Locatie van de SQLite-database |
| `COLLECTOR_ENABLED` | `true` | `false` = alleen de API, zonder events op te halen |

## Endpoints

| Endpoint | Wat | Voorbeeld |
|---|---|---|
| `GET /stats/events?offset=10` | Aantal events per type, aangemaakt in de laatste `offset` minuten | zie hieronder |
| `GET /stats/pull-requests/average-time?repo=owner/repo` | Gemiddelde tijd (seconden) tussen pull request-events voor één repo. Optioneel `&action=opened` (of een andere PR-action) | zie hieronder |
| `GET /stats/events/chart?offset=60` | **Bonus:** grafiek (PNG) van events per minuut per type | open in de browser |

```bash
curl "http://127.0.0.1:8000/stats/events?offset=10"
```
```json
{"offset_minutes": 10, "since": "2026-11-13T11:21:34Z",
 "counts": {"WatchEvent": 1, "PullRequestEvent": 2, "IssuesEvent": 1}, "total": 4}
```

```bash
curl "http://127.0.0.1:8000/stats/pull-requests/average-time?repo=home-assistant/core"
```
```json
{"repo": "home-assistant/core", "action": "all", "pull_request_events": 32, "avg_seconds": 88.4}
```

```bash
curl "http://127.0.0.1:8000/stats/pull-requests/average-time?repo=home-assistant/core&action=opened"
```
```json
{"repo": "home-assistant/core", "action": "opened", "pull_request_events": 4, "avg_seconds": 777.3}
```

Foute invoer (bv. `offset=0`, `offset=abc` of een ontbrekende offset) geeft een **422** met uitleg.

## Tests en kwaliteit

```bash
uv run pytest              # unit- en API-tests (offline: GitHub wordt nagebootst)
uv run ruff check .        # linting
uv run ruff format .       # formatting
```

## Projectstructuur

```
src/github_monitor/
├── etl.py         # De ETL-pipeline: extract (GitHub) → transform (filter + plat) → load (SQLite)
├── collector.py   # Draait de ETL steeds opnieuw, met het interval dat GitHub aangeeft
├── db.py          # SQLite-verbinding en tabel
├── stats.py       # De statistieken (SQL-queries)
├── chart.py       # De grafiek (matplotlib → PNG)
├── api.py         # REST API (FastAPI); start de collector op de achtergrond
├── config.py      # Instellingen via omgevingsvariabelen
└── __main__.py    # Startpunt: uv run github-monitor
tests/             # pytest
docs/              # C4-diagram
```

## Aannames

1. **"Streamen" = pollen.** GitHub biedt geen echte stream voor publieke events. De collector roept `GET /events` aan met het interval dat GitHub opgeeft (`X-Poll-Interval`, ~60 sec) en gebruikt een `ETag`, zodat een antwoord zonder nieuwe events (304) niet meetelt voor de rate limit.
2. **We zien een steekproef, niet alles.** Per poll levert GitHub de 100 meest recente publieke events van heel GitHub. Daarvan is maar een klein deel Watch/PR/Issues (in een test 4 van de 100). Op de rest van GitHub gebeurt in die minuut veel meer.
3. **Twee soorten bronnen.** Altijd heel GitHub (`/events`), plus optioneel de repo's uit `GITHUB_REPOS` (`/repos/{owner}/{repo}/events`). Zonder die repo's is de PR-statistiek bijna altijd `null`: in een live test waren 27 PR-events verspreid over 27 verschillende repo's. Alles komt in één tabel en wordt ontdubbeld op het event-`id`. **Gevolg:** in de offset-statistiek zijn events van de gekozen repo's iets oververtegenwoordigd. De eerste poll van een repo geeft ook direct de laatste 100 events van die repo, dus historie van voor de start.
4. **De offset telt op het moment waarop het event op GitHub is aangemaakt** (`created_at`), niet op het moment waarop wij het opsloegen. Zo staat het in de opdracht ("aangemaakt").
5. **GitHub levert events met vertraging aan.** GitHub noemt 30 sec tot enkele uren. In een test kwamen events ~5 minuten na `created_at` binnen. Voor korte offsets kan het aantal daardoor **te laag** uitvallen.
6. **De offset is verplicht**, in hele minuten, minimaal 1. De opdracht zegt "voor een bepaalde offset". Een absolute startdatum is niet gevraagd en niet gebouwd.
7. **"Tijd tussen pull requests" = tijd tussen alle `PullRequestEvent`s** van een repo, ongeacht de action (`opened`, `closed`, …), omdat de opdracht geen specifieke soort noemt. Het getal meet dus **PR-activiteit**. Met de optionele parameter `action` (bv. `opened`) tel je alleen die soort; bij `home-assistant/core` is dat 88 sec (alles) tegenover ~13 min (alleen nieuwe PR's), omdat veel events labels van bots zijn. Berekening: (laatste − eerste) / (aantal − 1). Bij minder dan 2 events: `avg_seconds: null`.
8. **Alleen events uit de GitHub Events API.** Statistieken gaan over wat de collector heeft opgehaald via de events-endpoints. Voor de gekozen repo's is dat ook de recente historie die GitHub bij de eerste poll teruggeeft. Er wordt geen andere bron gebruikt (zoals `/repos/{repo}/pulls`). Voor repo's die niet in `GITHUB_REPOS` staan, is de PR-statistiek meestal `null` of gebaseerd op weinig events.
9. **Alle tijden zijn UTC.**
10. **Eén proces, één worker.** De collector draait als achtergrondtaak in de API. Met meerdere workers zou hij meerdere keren draaien. In productie zou ik collector en API als aparte containers draaien.

## Wat ik met meer tijd zou doen

- Collector en API splitsen in twee containers (Docker Compose).
- Optionele absolute filters `since`/`until`.
- Bij grote volumes: events als Parquet naar een lakehouse schrijven en analyseren met DuckDB of Databricks (OLTP → OLAP).
- CI-pipeline met tests, ruff en een type checker.
