# Agregator HCL — Căutare tematică Sector 3

Instrument de căutare în hotărârile Consiliului Local Sector 3 (sursa: hcl.usr.ro).

## Comenzi

```bash
# Descarcă și indexează HCL-urile (prima rulare: ~15 min pentru 2024-2026)
python ingest.py

# Pornește interfața de căutare
streamlit run app.py
```

## Update date noi

```bash
python ingest.py          # adaugă docs noi, sare peste cele existente
git add hcl.db
git commit -m "data: update HCL"
git push
```

## Structură

| Fișier | Rol |
|--------|-----|
| `db.py` | Schema SQLite + FTS5, funcții de căutare |
| `fetcher.py` | Descărcare date de pe hcl.usr.ro |
| `ingest.py` | Script de ingestie (descărcare + indexare) |
| `app.py` | Interfața Streamlit |
| `topics.yaml` | Topicuri predefinite cu alias-uri |
| `schema.sql` | Schema bazei de date |
