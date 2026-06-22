# 🚀 Ai NorX - منصة الوكلاء الأذكياء العربية

<div align="center">

![Status](https://img.shields.io/badge/status-MVP%20Development-orange)
![License](https://img.shields.io/badge/license-Proprietary-red)
![Stack](https://img.shields.io/badge/stack-Next.js%20%2B%20FastAPI-blue)

**منصة سحابية عربية للوكلاء الأذكياء على غرار Manus AI و Z.ai و Kimi**

</div>

---

## 📋 نظرة عامة

Ai NorX هي منصة سحابية متكاملة للوكلاء الأذكياء، مصممة خصيصاً للمستخدم العربي. تجمع أفضل الميزات من المشاريع مفتوحة المصدر (Onyx, Nanobot, LibreChat) مع بنية سحابية حديثة وآمنة.

### ✨ الميزات الرئيسية

- 🤖 **وكلاء أذكياء قابلون للتخصيص** - أنشئ وكلاء بـ system prompts مخصصة
- 💬 **محادثات متعددة** - بعدد لا محدود من المحادثات
- 🌐 **متعدد المستأجرين** - كل مستخدم له مساحة عمل خاصة معزولة
- 🔐 **مصادقة آمنة** - عبر Clerk مع دعم OAuth و 2FA
- 🎨 **عربي أولاً** - واجهة RTL كاملة مع خطوط عربية
- 🆓 **مجاني** - يستخدم مزودي LLM مجانيين (NVIDIA NIM, OpenCode.ai)
- ⚡ **بث مباشر** - استجابات فورية عبر WebSocket

## 🛠️ المكدس التقني

### Frontend
- **Next.js 16** + React 19 + TypeScript
- **Tailwind CSS 4** + shadcn/ui + Radix UI
- **Clerk** للمصادقة
- **TanStack Query** لإدارة الحالة
- **WebSocket** للبث المباشر

### Backend
- **Python 3.12** + FastAPI + Uvicorn
- **SQLAlchemy 2.0** (async) + PostgreSQL
- **Alembic** للـ migrations
- **Pydantic 2** للتحقق
- **httpx** للـ HTTP async

### Infrastructure
- **Neon** - PostgreSQL serverless
- **Upstash** - Redis serverless
- **Cloudflare R2** - تخزين الملفات
- **Vercel** - استضافة الواجهة
- **Railway** - استضافة الـ backend
- **GitHub Actions** - CI/CD

## 🚀 البدء السريع

### المتطلبات
- Python 3.11+
- Node.js 20+
- npm أو yarn

### التطوير المحلي

```bash
# استنساخ المستودع
git clone https://github.com/jbreel77888/Ai-NorX.git
cd Ai-NorX

# إعداد متغيرات البيئة
cp .env.example .env.secrets
# عدّل القيم في .env.secrets

# تشغيل Backend
cd backend
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# في terminal آخر، تشغيل Frontend
cd frontend
npm install
npm run dev
```

ثم افتح http://localhost:3000 في المتصفح.

## 📁 بنية المشروع

```
Ai-NorX/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/v1/         # API endpoints
│   │   ├── core/           # Auth, Tenant, RBAC, Config
│   │   ├── agents/         # Agent engine
│   │   ├── llm/            # LLM Gateway
│   │   ├── chat/           # Chat engine
│   │   ├── db/             # Database models
│   │   └── main.py         # FastAPI app
│   ├── alembic/            # DB migrations
│   └── pyproject.toml
├── frontend/               # Next.js 16 frontend
│   ├── src/
│   │   ├── app/            # Next.js App Router
│   │   ├── components/     # React components
│   │   └── lib/            # Utilities
│   └── package.json
├── .github/workflows/      # CI/CD
└── docker-compose.yml      # Dev environment
```

## 🔐 الأمان

- **عزل المستأجرين** عبر contextvars + SQLAlchemy filters
- **مصادقة JWT** عبر Clerk
- **تشفير البيانات** في القاعدة والنقل
- **CORS** مُحكم
- **Rate limiting** (قريباً)

## 📜 الترخيص

جميع الحقوق محفوظة © 2026 Ai NorX. هذا المشروع خاص وليس مفتوح المصدر.

## 📞 التواصل

- **البريد:** jbrel77189@gmail.com
- **GitHub:** [jbreel77888/Ai-NorX](https://github.com/jbreel77888/Ai-NorX)

---

<div align="center">
  <sub>Built with ❤️ for the Arabic-speaking community</sub>
</div>
