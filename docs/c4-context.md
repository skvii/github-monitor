# C4-model, level 1: System Context

> Het C4-model beschrijft software in vier zoomniveaus: **Context → Containers → Components → Code**.
> **Level 1 (System Context)** is het meest uitgezoomde niveau. Het laat zien **wie** het systeem gebruikt en met **welke externe systemen** het praat. Technische details (welke database, welke framework) horen hier nog **niet** bij.

```mermaid
flowchart TB
    user["<b>Eindgebruiker</b><br/><i>[Persoon]</i><br/><br/>Wil weten hoeveel activiteit er<br/>op GitHub is en hoe vaak er<br/>pull requests zijn in een repo"]

    system["<b>GitHub Monitor</b><br/><i>[Software System]</i><br/><br/>Verzamelt Watch-, PullRequest- en<br/>Issues-events en berekent daar<br/>statistieken over"]

    github["<b>GitHub API</b><br/><i>[Extern Software System]</i><br/><br/>Levert de publieke events<br/>van heel GitHub"]

    user -- "Vraagt statistieken en grafiek op<br/><i>[REST / JSON, PNG]</i>" --> system
    system -- "Haalt elke ~60 sec de nieuwste events op<br/><i>[REST / JSON, HTTPS]</i>" --> github

    classDef person fill:#08427b,stroke:#052e56,color:#fff
    classDef internal fill:#1168bd,stroke:#0b4884,color:#fff
    classDef external fill:#999999,stroke:#6b6b6b,color:#fff
    class user person
    class system internal
    class github external
```

## Toelichting

| Element | Type | Rol |
|---|---|---|
| **Eindgebruiker** | Persoon | Vraagt via de REST API statistieken op: events per type binnen een offset, gemiddelde tijd tussen PR's, en een grafiek |
| **GitHub Monitor** | Ons systeem | Verzamelt de events, slaat ze op en berekent de statistieken |
| **GitHub API** | Extern systeem | Bron van de publieke events (`GET /events`) |

**Kleurgebruik volgens de C4-conventie:** donkerblauw = persoon, blauw = het systeem dat we bouwen, grijs = een extern systeem dat we niet beheren.

## Eén niveau dieper (level 2, ter illustratie)

Niet gevraagd, maar handig voor de presentatie: zo ziet het systeem er van binnen uit.

```mermaid
flowchart LR
    user["Eindgebruiker"]
    github["GitHub API<br/><i>[extern]</i>"]

    subgraph monitor["GitHub Monitor (één Python-proces)"]
        collector["<b>Collector</b><br/><i>[asyncio-taak, httpx]</i><br/>ETL: extract → transform → load<br/>bronnen: /events + gekozen repo's"]
        db[("<b>Database</b><br/><i>[SQLite]</i><br/>tabel events")]
        api["<b>REST API</b><br/><i>[FastAPI]</i><br/>statistieken + grafiek"]
    end

    collector -- "GET /events (ETag)" --> github
    collector -- "INSERT OR IGNORE" --> db
    api -- "SELECT" --> db
    user -- "GET /stats/..." --> api
```
