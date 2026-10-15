# Ertangi tanlov uchun tezkor qo'llanma

> Bu fayl ertaga mavzu berilganda qanday ishlashni ko'rsatadi.
> Barcha backend tayyor — faqat mavzuga moslash kerak.

---

## Nima tayyor?

### Autentifikatsiya
- **Email + tasdiqlash kodi** — `POST /auth/email/send-code` → `POST /auth/email/verify`
- **JWT access + refresh token** — access 30 min, refresh 7 kun
- `POST /auth/refresh` — yangi tokenlar olish
- Google OAuth ham bor (ixtiyoriy)
- Demo login (development uchun)

### Universal CRUD
- `GET/POST/PATCH/DELETE /entities` — istalgan `type` bilan
- JSONB `data` maydoni — istalgan tuzilma, migratsiyasiz
- Filtr, qidiruv, sahifalash, saralash
- `GET /entities/stats?type=` — statistika

### AI Chat (Groq — 6 ta kalit rotatsiyasi)
- `POST /ai/chat` — oddiy chat, streaming (SSE)
- `assistant="knowledge"` — RAG rejimi (bilimlar bazasidan javob)
- `assistant="analytics"` — statistika tahlili
- `assistant="actions"` — function calling (read-only toollar)
- `POST /ai/insights?type=` — avtomatik tahlil

### RAG (bilimlar bazasi)
- PDF, DOCX, TXT yuklash → chunklarga bo'lish → embedding
- **Rasmlar** → Gemini bilan tahlil → matn → embedding
- `POST /knowledge/upload` — fayl yuklash
- `POST /knowledge/text` — matn qo'shish
- `POST /knowledge/search` — qidiruv

### Admin
- `GET /admin/overview` — umumiy statistika
- `GET /admin/users`, `PATCH /admin/users/{id}` — foydalanuvchilarni boshqarish

### Deploy
- Docker Compose (dev + prod)
- Caddy (avtomatik HTTPS)
- GitHub Actions CI/CD

---

## Ertaga mavzu berilganda — 5 qadam

### 1. Entity turini aniqlash
Masalan mavzu "Ekologiya" bo'lsa:
- `type = "eco_project"` yoki `"eco_report"`
- `data` ichidagi maydonlar: `{"category": "...", "location": "...", "impact_score": 85}`
- **Migratsiya KERAK EMAS** — `data` JSONB, erkin formatda

### 2. System promptlarni moslashtirish
`backend/app/services/prompts.py` faylini oching:
```python
SYSTEM_CHAT = (
    "Siz ekologiya bo'yicha mutaxassis assistentsiz. "
    "Atrof-muhit, tabiatni muhofaza qilish va barqaror rivojlanish "
    "haqida savollarga javob bering. O'zbek tilida javob bering."
)
```

### 3. Demo ma'lumotlar
```bash
docker compose exec api python -m scripts.seed \
    --type eco_project --count 40 \
    --topic "O'zbekistondagi ekologik loyihalar" --knowledge
```
Bu: 40 ta entity + 5 ta knowledge matn yaratadi (LLM orqali).

### 4. Bilimlar bazasiga ma'lumot qo'shish
- PDF, DOCX fayllarni `/knowledge/upload` orqali yuklang
- Rasmlarni ham yuklang — Gemini tahlil qiladi
- Qo'lda matn: `POST /knowledge/text {"title": "...", "content": "..."}`

### 5. Frontend ulash
Frontend `api.<DOMAIN>` ga ulanadi. Asosiy endpointlar:
- Auth: `/auth/email/send-code` → `/auth/email/verify`
- CRUD: `/entities?type=eco_project`
- AI: `/ai/chat` (streaming)
- Knowledge: `/knowledge/search`

---

## Fayl tuzilmasi (muhim fayllar)

```
backend-project/
├── .env                         ← SIRLAR (repoga tushmaydi!)
├── .env.example                 ← namuna
├── docker-compose.yml           ← `docker compose up --build`
├── docker-compose.prod.yml      ← production uchun
├── Caddyfile                    ← reverse proxy
├── TOMORROW_GUIDE.md            ← shu fayl
└── backend/
    └── app/
        ├── config.py            ← barcha sozlamalar
        ├── services/
        │   ├── prompts.py       ← AI system promptlar (MAVZUGA MOSLANG)
        │   ├── llm.py           ← Groq + key rotation
        │   ├── gemini.py        ← rasm tahlili
        │   ├── rag.py           ← chunking + vector qidiruv
        │   ├── embeddings.py    ← Gemini embedding API (5 kalit rotatsiyasi)
        │   ├── auth_service.py  ← JWT access/refresh
        │   ├── email_service.py ← email kod yuborish
        │   └── ai_tools.py     ← function calling toollar
        ├── routers/
        │   ├── auth.py          ← email login, refresh, google, demo
        │   ├── entities.py      ← universal CRUD
        │   ├── ai.py            ← chat, insights, sessions
        │   ├── knowledge.py     ← upload, search (pdf, rasm)
        │   └── admin.py         ← admin panel
        └── models/              ← SQLAlchemy modellar
```

---

## API kalit sozlamalar (.env)

| O'zgaruvchi | Tavsif |
|---|---|
| `LLM_API_KEYS` | Groq kalitlari, vergul bilan (6 ta bor) |
| `LLM_MODEL` | `llama-3.3-70b-versatile` (asosiy) |
| `GEMINI_API_KEYS` | Gemini kalitlari — embedding + rasm tahlili (5 ta) |
| `EMAIL_HOST_USER` | Gmail (kod yuborish uchun) |
| `SECRET_KEY` | JWT imzolash uchun |
| `ADMIN_EMAILS` | Admin bo'ladigan emaillar |

---

## Tezkor o'zgartirish chizig'i

1. **Yangi entity type** → faqat `POST /entities` da yangi `type` bering
2. **AI xulqi** → `services/prompts.py` ni o'zgartiring
3. **Yangi AI tool** → `services/ai_tools.py` ga funksiya qo'shing
4. **Yangi subdomen** → `Caddyfile` ga blok qo'shing
5. **Bilim qo'shish** → `/knowledge/upload` yoki `/knowledge/text`

---

## Serverga deploy

```bash
# 1. Serverda .env faylni joylashtiring
scp .env user@server:/opt/app/.env

# 2. docker-compose.prod.yml va Caddyfile ni ko'chiring
scp docker-compose.prod.yml Caddyfile user@server:/opt/app/

# 3. IMAGE o'zgaruvchisini to'g'rilang va ishga tushiring
ssh user@server "cd /opt/app && docker compose -f docker-compose.prod.yml up -d"

# 4. Health check
curl https://api.<DOMAIN>/health
```

GitHub Actions `main` ga push bo'lganda avtomatik deploy qiladi.
