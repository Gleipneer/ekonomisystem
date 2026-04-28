# Drift och operations

Start, stopp, felsökning och övervakning av systemet.
Last verified: 2026-04-10.

## Start och stopp

### Med systemd (rekommenderat för server)

```bash
sudo systemctl start economic-system    # Starta
sudo systemctl stop economic-system     # Stoppa
sudo systemctl restart economic-system  # Starta om
sudo systemctl status economic-system   # Status
journalctl -u economic-system -f        # Loggar (live)
journalctl -u economic-system --since "1 hour ago"  # Senaste timmen
```

### Manuellt (utveckling)

```bash
./scripts/start_app.sh                  # Starta (förgrund)
# Ctrl+C för att stoppa
```

### Docker

```bash
docker-compose up -d --build            # Starta
docker-compose stop                     # Stoppa
docker-compose restart                  # Starta om
docker-compose logs -f                  # Loggar
```

## Health check

```bash
curl -s http://localhost:8000/healthz
# Förväntat: {"status":"ok"}
```

Automatisk health check:
```bash
./scripts/healthcheck.sh
```

## Hur man vet att systemet lever

| Signal | Kommando | Förväntat |
|---|---|---|
| Health endpoint | `curl localhost:8000/healthz` | `{"status":"ok"}` |
| Frontend | Öppna `http://localhost:8000/` | SPA laddas |
| API docs | Öppna `http://localhost:8000/docs` | Swagger UI |
| Hushållslista | `curl localhost:8000/households` | JSON-lista |
| AI utan nyckel | `curl -X POST localhost:8000/households/1/assistant/respond -H 'Content-Type: application/json' -d '{"prompt":"test"}'` | HTTP 503 |

## Loggar

- **systemd**: `journalctl -u economic-system`
- **Docker**: `docker-compose logs`
- **Manuellt**: stdout från uvicorn-processen
- **Runtime-logg**: `logs/runtime-*.log` (om genererad av start-script)

## Vanliga fel

### `503` på AI-routes
- **Orsak**: `OPENAI_API_KEY` saknas i `.env`
- **Åtgärd**: Lägg till giltig nyckel i `.env`, starta om

### `502` på AI-routes
- **Orsak**: OpenAI API-fel (timeout, rate limit, ogiltig nyckel)
- **Åtgärd**: Kontrollera nyckel, nätverksaccess, OpenAI status

### Port upptagen
- **Orsak**: Annan process använder port 8000
- **Åtgärd**: `start_app.sh` hittar automatiskt nästa lediga port. Eller: `APP_PORT=8001 ./scripts/start_app.sh`

### Tabeller saknas
- **Orsak**: Migrationer inte körda
- **Åtgärd**: `source venv/bin/activate && alembic upgrade head`

### Dokumentuppladdning misslyckas
- **Orsak**: `uploaded_files/` saknas eller har fel rättigheter
- **Åtgärd**: `mkdir -p uploaded_files && chmod 755 uploaded_files`

### OCR fungerar inte
- **Orsak**: Tesseract inte installerat
- **Åtgärd**: `sudo apt install tesseract-ocr tesseract-ocr-swe`

## Recovery

### Databas korrupt
```bash
# Stoppa appen
sudo systemctl stop economic-system

# Återställ från backup
cp backups/database.db.YYYYMMDD database.db

# Kör migrationer om nödvändigt
source venv/bin/activate && alembic upgrade head

# Starta
sudo systemctl start economic-system
```

### Full omstart från rent läge
```bash
sudo systemctl stop economic-system
rm database.db  # VARNING: all data försvinner
source venv/bin/activate
alembic upgrade head
sudo systemctl start economic-system
```

## Backup (minimum)

| Vad | Var | Frekvens |
|---|---|---|
| Databas | `database.db` | Dagligen |
| Uppladdade filer | `uploaded_files/` | Dagligen |
| Konfiguration | `.env` | Vid ändring |
