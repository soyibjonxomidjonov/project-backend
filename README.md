# Universal AI Backend

Ertangi tanlovda istalgan mavzu berilganda, 2 soat ichida ishlaydigan sayt chiqarish uchun
tayyor, deploy qilingan, test qilingan backend.

## Tezkor boshlash (development)

```bash
# .env faylini yaratish
cp .env.example .env
# Kerakli kalitlarni .env ga yozish

# Ishga tushirish
docker compose up --build
```

API: http://localhost:8000
Docs: http://localhost:8000/docs

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

## Rollback
```bash
IMAGE_TAG=<oldingi sha> docker compose -f docker-compose.prod.yml up -d
```

## Deploy
`main` branchga push qilinganda GitHub Actions avtomatik deploy qiladi:
1. Testlar ishga tushadi
2. Docker image yig'iladi va GHCR ga yuklanadi
3. SSH orqali serverda yangilanadi
4. Health check tekshiriladi
