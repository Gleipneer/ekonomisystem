# Known Limitations and Next Steps

## Titel
Aktuella begränsningar och nästa steg

**Senast verifierad:** 2026-04-28  
**Status:** Aktiv risklogg  
**Källa/grund:** kodinspektion i detta pass, befintliga docs, verifieringskommandon

## Aktuella begränsningar

- `app/main.py` är stor hotspot med många ansvar i en fil.
- `app/ai_services.py` är stor hotspot med både routing, prompting, schema och ingestlogik.
- `app/static/app.js` är stor frontend-hotspot.
- GitHub CI/checks var tidigare frånvarande och behöver hållas stabila efter införande.
- Semantiskt tveksamma LLM-intents kan förekomma även när schema validerar.
- Modellrouting finns som regelbaserad implementation; mer avancerad routingstrategi är inte verifierad som implementerad.
- Full bankkoppling till externa banker är inte verifierad som implementerad.
- Observability/metrics för produktion (standardiserad metrics pipeline) är inte verifierad som fullt etablerad.
- Extern advisory/deal-comparison är fortfarande begränsad/stub-betonad i nuvarande underlag.
- Full audit/undo/provenance över hela livscykeln är inte komplett.

## Nästa steg

- Bryt ut `main.py` i routers/moduler med oförändrat API-kontrakt.
- Isolera assistant- och ingest-kontrakt i separata service- och policylager.
- Stärk observability (strukturlogg, request-id, metrics, felklassning).
- Definiera och testa undo/audit-strategi för apply-flöden.
- Lägg till kontraktstester för GUI-state transitions och stale-source blockering.

## Osäkerheter/kvarvarande risker

- Data-In hashcanonicalization måste hållas strikt synkron mellan analyze och promote för att undvika falska mismatch.
