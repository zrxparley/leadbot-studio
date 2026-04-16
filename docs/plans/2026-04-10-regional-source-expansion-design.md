# Regional Source Expansion Design

Date: 2026-04-10

## Goal

Expand buyer-only procurement lead discovery beyond the current `UNGM + EasyTenders` mix, with a specific focus on:

- Southeast Asia
- Germany
- Australia
- Canada
- Middle East

The operating rule remains unchanged:

- procurement demand only
- fresh within the last 365 days
- public buyer identity required
- public email or phone strongly preferred

## Prioritization

### P0: Best immediate integration candidates

These are the best next sources because they either already expose public notice pages or expose a directory layer that includes public contacts.

1. `Indonesia INAPROC / LKPP`
Reason:
The LPSE directory exposes agency-level emails, phone numbers, and direct procurement portal URLs. That makes it a very practical bridge from "which buyer portal matters" to "where can we scrape fresh notices."

2. `Germany service.bund.de Ausschreibungen`
Reason:
It is an official publication layer that imports notices from many cooperating procurement platforms. This is ideal for Germany because it offers reach without requiring one connector per Land or municipal portal on day one.

3. `Australia AusTender`
Reason:
It is the national procurement system and should give the fastest path to diversified Australian buyer demand once browser or structured search extraction is added.

4. `Canada CanadaBuys`
Reason:
It is the official federal source, publishes new notices daily, and explicitly supports tender search across organizations and categories.

5. `Qatar Monaqasat`
Reason:
Public tender detail pages can expose ministry, publish date, and direct email/phone fields. That makes it unusually compatible with the current buyer-only standard.

### P1: Strong secondary sources

- `Singapore GeBIZ`
- `PhilGEPS`
- `Vietnam VNEPS`
- `Malaysia ePerolehan`
- `Germany e-Vergabe`
- `TED`
- `NSW eTendering`
- `Tenders VIC`
- `QTenders`
- `Dubai eSupply`
- `Saudi Etimad`
- `Oman Tender Board`
- `Bahrain Tender Board`

These are strategically important, but most will need browser automation, more multilingual parsing, or deeper tender detail handling.

### P2: Useful amplifiers, not first-wave integrations

- `Thailand e-GP`
- `Tenders WA`
- `MERX`

These can add volume, but they are not the fastest route to a stable buyer-only archive.

## Recommended implementation order

1. `Qatar Monaqasat`
Reason:
Public tender detail pages already look closest to the current EasyTenders pattern.

2. `Germany service.bund.de`
Reason:
Official and aggregated; high leverage for Germany.

3. `Canada CanadaBuys`
Reason:
Large opportunity volume and strong country diversification.

4. `Australia AusTender`
Reason:
National coverage and good strategic value.

5. `Indonesia INAPROC / LKPP`
Reason:
Very useful for Southeast Asia because it gives both directory intelligence and procurement routing.

6. `Singapore / Philippines / Vietnam / Malaysia`
Reason:
Add depth across Southeast Asia after the first diversified wave is stable.

7. `Dubai / Saudi / Oman / Bahrain`
Reason:
Add Middle East breadth once Qatar is stable.

## Data model impact

No schema change is required for this expansion phase.

The current lead model already supports:

- buyer organization
- demand summary
- posted date
- direct email
- direct phone
- source URL
- contact hint
- demand type

## Connector strategy

Two connector families are enough for the next stage:

1. `direct notice connector`
Use when a source exposes stable public notice detail pages with visible publish dates and contact fields.

Best fits:

- Monaqasat
- service.bund.de notice pages
- some CanadaBuys notice pages

2. `portal search + notice detail connector`
Use when the public entry point is a searchable portal and the detail page requires JS rendering or multi-step navigation.

Best fits:

- AusTender
- GeBIZ
- PhilGEPS
- VNEPS
- ePerolehan
- Dubai eSupply
- Etimad

## Verification rule

A source should only be promoted into the default daily run when all of the following are true:

1. It yields recent notices within the last 365 days.
2. It surfaces a real buyer organization.
3. It yields a public email or phone directly, or through a reliable public contact enrichment path.
4. It does not mostly produce supplier-side noise.

## Deliverable in repo

The current regional source registry is stored in:

- `app/data/regional_procurement_sources.json`

This file is intended to be the working backlog for the next connector wave.
