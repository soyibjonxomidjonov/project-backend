# Universal AI Backend

Ertangi tanlovda istalgan mavzu berilganda, 2 soat ichida ishlaydigan sayt chiqarish uchun
tayyor, deploy qilingan, test qilingan backend.

## Lokalda ishga tushirish (zip yoki git clone)

Faqat Docker Desktop (yoki Docker Engine + `docker compose`) kerak.

```bash
# 1. Kodni oling: GitHub -> "Code" -> "Download ZIP" (yoki git clone), keyin papkaga kiring
# 2. .env faylini yarating (shart — repoda yo'q)
cp .env.example .env
# 3. Kerakli kalitlarni .env ga yozing (LLM_API_KEY/S, GEMINI_API_KEY/S, SECRET_KEY, ...)

# 4. Ishga tushirish (DB + API birga ko'tariladi, migratsiya avtomatik)
docker compose up -d --build
```

- API: http://localhost:8000 · Docs: http://localhost:8000/docs · Health: http://localhost:8000/health
- Postgres (pgvector) lokal konteyner ichida ishlaydi — hech qanday tashqi bazaga ulanmaydi.
- To'xtatish: `docker compose down` · Bazani ham o'chirish: `docker compose down -v`

### Frontend / CORS
Lokal frontend `http://localhost:3000` va `http://localhost:5173` (hamda istalgan `localhost`/`127.0.0.1` port)
CORS'da **har doim ruxsat etilgan** — `.env` ga tegmasdan ishlaydi. Prod frontend uchun `https://<sub>.scholarmap.uz`
avtomatik, qo'shimcha originlarni `EXTRA_CORS_ORIGINS` orqali bering.

## Ertangi "mavzu berildi" jarayoni

### 1. Yangi type qo'shish
Migratsiya kerak emas. `entities` jadvalidagi `type` maydoniga yangi qiymat bering:
```
POST /entities {"type": "product", "title": "...", "data": {...}}
```

### 2. System promptlarni moslashtirish
`backend/app/services/prompts.py` faylida mavzuga mos promptlar yozing.

### 3. Demo ma'lumotlar generatsiya qilish
```bash
docker compose exec api python -m scripts.seed \
    --type product --count 40 --topic "Elektron mahsulotlar" --knowledge
```

### 4. Yangi subdomen qo'shish
`Caddyfile` ga yangi blok qo'shing:
```
myapp.domen.uz {
    root * /srv/sites/myapp
    file_server
    try_files {path} /index.html
}
```
Keyin: `docker compose -f docker-compose.prod.yml restart caddy`

## API endpointlar

| Yo'l | Tavsif |
|---|---|
| `GET /health` | Salomatlik tekshiruvi |
| `GET /auth/google/login?redirect=` | Google OAuth boshlash |
| `POST /auth/demo-login` | Demo kirish (development) |
| `GET /auth/me` | Joriy foydalanuvchi |
| `GET /entities?type=&q=&page=` | Yozuvlar ro'yxati |
| `POST /entities` | Yangi yozuv |
| `PATCH /entities/{id}` | Tahrirlash |
| `DELETE /entities/{id}` | O'chirish |
| `GET /entities/stats?type=` | Statistika |
| `POST /ai/chat` | AI chat (streaming qo'llab-quvvatlanadi) |
| `POST /ai/insights?type=` | AI tahlil |
| `POST /knowledge/upload` | Hujjat yuklash (PDF, DOCX, TXT) |
| `POST /knowledge/text` | Matn qo'shish |
| `POST /knowledge/search` | Bilimlar bazasidan qidirish |
| `GET /admin/overview` | Admin statistika |
| `GET /admin/users` | Foydalanuvchilar ro'yxati |

## Deploy (CD)
`main` branchga push qilinganda GitHub Actions (`.github/workflows/deploy.yml`) avtomatik deploy qiladi:
1. SSH orqali EC2 serverga ulanadi
2. `git fetch` + `git reset --hard origin/main`
3. `docker compose up -d --build --force-recreate` (image serverda yig'iladi)
4. Migratsiya (`alembic upgrade head`) api konteyner CMD'ida avtomatik bajariladi

Server `.env` (sirlardan iborat) serverda qo'lda turadi — CD uni ko'chirmaydi.

## Rollback
```bash
# Serverda oldingi commitga qaytarish:
git reset --hard <oldingi-sha> && docker compose up -d --build --force-recreate
```
