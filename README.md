---

## Development

### Setup Backend
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run Tests
```bash
pytest tests/ -v
```

### Start Server
```bash
uvicorn app.main:app --reload
```

### Start Frontend
```bash
cd frontend
python3 -m http.server 5500
```

Visit `http://localhost:5500`

---

## Roadmap (v2)

- [ ] Support for more PII types (names, addresses, dates)
- [ ] PDF/Word export
- [ ] User authentication & accounts
- [ ] Increased file size limits
- [ ] Named Entity Recognition (NER)

---
