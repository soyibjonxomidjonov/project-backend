# Lokalda ishga tushirish (RUN.md)

Boshqa kompyuterga kodni yuklab (GitHub ZIP yoki `git clone`), papkaga kiring va **`.env`** faylini qo'ying:

```bash
cp .env.example .env     # keyin kalitlarni to'ldiring (LLM_API_KEY/S, GEMINI_API_KEY/S, SECRET_KEY, ...)
```

Pastdagi 3 usuldan birini tanlang. **1-usul (Docker) — eng oson va tavsiya etilgani.**

---

## 1-usul: Docker Compose (tavsiya) — DB + API birga

Faqat Docker Desktop (yoki Docker Engine + `docker compose`) kerak. Postgres+pgvector va migratsiya avtomatik.

```bash
docker compose up -d --build
```

- API: http://localhost:8000 · Docs: http://localhost:8000/docs · Health: http://localhost:8000/health
- Loglar: `docker compose logs -f api`
- To'xtatish: `docker compose down`  ·  Baza bilan birga: `docker compose down -v`

> `.env` dagi `DATABASE_URL=postgresql+asyncpg://app:app@db:5432/app` — `db` bu compose ichidagi konteyner nomi.
> Bu usulda uni **o'zgartirmang**.

---

## 2-usul: uvicorn (native Python, Dockersiz API)

Python 3.12 va ishlab turgan **Postgres + pgvector** kerak. Eng osoni — bazani Docker'da ko'tarib, API'ni native ishga tushirish.

```bash
# 1) Faqat bazani Docker'da ko'taring (port 5432 ochiq):
docker run -d --name pgv -p 5432:5432 \
  -e POSTGRES_USER=app -e POSTGRES_PASSWORD=app -e POSTGRES_DB=app \
  pgvector/pgvector:pg16

# 2) Virtual muhit + paketlar:
cd backend
python -m venv .venv
# Windows (PowerShell):  .venv\Scripts\Activate.ps1
# macOS/Linux:           source .venv/bin/activate
pip install -r requirements.txt

# 3) .env dagi DATABASE_URL ni localhost ga o'zgartiring:
#    DATABASE_URL=postgresql+asyncpg://app:app@localhost:5432/app

# 4) Migratsiya + ishga tushirish (backend/ ichida):
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- `--reload` = kod o'zgarsa avtomatik qayta yuklaydi (development).
- Health: http://localhost:8000/health

---

## 3-usul: `fastapi dev` (FastAPI CLI)

2-usuldagi bazani (va `.env` DATABASE_URL=localhost) talab qiladi. CLI uchun qo'shimcha paket kerak:

```bash
cd backend
pip install -r requirements.txt
pip install "fastapi[standard]"      # `fastapi` buyrug'i shundan keladi

alembic upgrade head
fastapi dev app/main.py              # development (auto-reload)
# yoki production uslubida:
# fastapi run app/main.py --host 0.0.0.0 --port 8000
```

---

## Frontend / CORS

Lokal frontend `http://localhost:3000`, `http://localhost:5173` (va istalgan `localhost`/`127.0.0.1` port)
**har doim** CORS'da ruxsat etilgan — `.env` ga tegish shart emas. Prod subdomenlar `https://<sub>.scholarmap.uz`
avtomatik; boshqa originlarni `.env` dagi `EXTRA_CORS_ORIGINS` ga vergul bilan qo'shing.

## Tez-tez muammolar

- `env file .env not found` → `.env` faylini yaratmagansiz (`cp .env.example .env`).
- `/health` da `"db":"error"` → baza ulanmagan: Docker usulida `docker compose ps` (db healthy?), native usulda `DATABASE_URL` localhost ekanini va `pgv` konteyner ishlab turganini tekshiring.
- Port 8000 band → boshqa dastur ishlatyapti; uni to'xtating yoki portni o'zgartiring.
