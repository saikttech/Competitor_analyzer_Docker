
---

# 🚀 RAG Competitor Analyzer (Production-Ready)

Автоматизированный **ETL + RAG пайплайн** для глубокого анализа конкурентов. Система самостоятельно находит компании в интернете, парсит полные тексты сайтов, очищает данные, разбивает их на смысловые фрагменты, векторизует с помощью нейросетей и генерирует структурированный аналитический отчет на основе пользовательского запроса.

Проект эволюционировал из прототипа на Google Colab/SQLite в **полноценную микросервисную архитектуру**, готовую к развертыванию в продакшене.

---

## 🏗 Архитектура

```mermaid
graph TD
    Client[Клиент / Swagger UI] -->|HTTP POST /analyze| API[FastAPI Server]
    API -->|1. Ставит задачу| Redis[(Redis Queue)]
    API -->|2. Возвращает task_id| Client
    
    Redis -->|3. Забирает задачу| Worker[Celery Worker]
    
    Worker -->|4. Парсинг| DDG[(DuckDuckGo Search)]
    Worker -->|5. Парсинг текста| Web[Сайты конкурентов]
    Worker -->|6. Сохранение чанков| DB[(PostgreSQL + pgvector)]
    Worker -->|7. Векторизация| OpenAI[OpenAI API / Proxy]
    Worker -->|8. Hybrid Search| DB
    Worker -->|9. Генерация отчета| OpenAI
    Worker -->|10. Сохранение| Storage[Локальная папка / S3]
    
    Client -->|11. GET /analyze/{task_id}| API
    API -->|12. Статус и ссылка на отчет| Client
```

---

## ✨ Ключевые особенности

- 🔄 **Асинхронная обработка:** Тяжелые задачи (парсинг, эмбеддинг, LLM) выполняются в фоне через **Celery + Redis**, предотвращая таймауты API.
- 🗄️ **Продвинутая база данных:** Использование **PostgreSQL + pgvector** для нативного хранения векторов и гибридного поиска (Косинусное сходство + BM25 полнотекстовый поиск).
- 🧠 **Умный RAG-пайплайн:** Очистка SEO-спама, интеллектуальный чанкинг по границам предложений и гибридный поиск для максимальной релевантности.
- 🛡️ **Production-Ready защита:** Rate Limiting, аутентификация по API-ключам, таймауты HTTP-запросов и защита воркеров от OOM (Out of Memory).
- 📦 **Гибкое хранение:** Отчеты сохраняются локально в смонтированную папку `./reports` с возможностью бесшовного переключения на S3-совместимые хранилища (MinIO, Yandex Cloud, AWS).
- 🐳 **Полная контейнеризация:** Развертывание одной командой через Docker Compose.

---

## 🛠 Стек технологий

| Категория | Технологии |
|-----------|------------|
| **Backend API** | FastAPI, Uvicorn, Pydantic |
| **Очередь задач** | Celery, Redis |
| **База данных** | PostgreSQL 15, `pgvector`, `pg_trgm`, SQLAlchemy |
| **Парсинг** | `duckduckgo-search`, `httpx`, `BeautifulSoup4` |
| **AI / LLM** | OpenAI API (`gpt-3.5-turbo`, `text-embedding-3-small`) |
| **Инфраструктура** | Docker, Docker Compose |
| **Хранилище** | Локальная ФС (с фоллбэком на S3 через `boto3`) |

---

## 🚀 Быстрый старт

### 1. Требования
- Установленный [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- API-ключ OpenAI (или прокси-сервера, например, proxyapi.ru)

### 2. Установка и запуск
```bash
# Клонируйте репозиторий
git clone https://github.com/your-username/rag-competitor-analyzer.git
cd rag-competitor-analyzer

# Создайте файл .env на основе примера (или скопируйте из документации ниже)
cp .env.example .env 
# Отредактируйте .env, вставив ваш OPENAI_API_KEY

# Запустите всю экосистему (сборка и запуск займут 2-3 минуты)
docker compose up --build
```

После успешного запуска сервисы будут доступны по адресам:
- **FastAPI (Swagger UI):** http://localhost:8000/docs
- **PostgreSQL:** `localhost:5432`
- **Redis:** `localhost:6379`

---

## ⚙️ Конфигурация (`.env`)

Создайте файл `.env` в корне проекта и заполните его:

```env
# --- AI Настройки ---
OPENAI_API_KEY=sk-your-real-key-here
OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1  # Или https://api.openai.com/v1

# --- База данных и Очередь ---
DATABASE_URL=postgresql://postgres:postgres@db:5432/competitors_db
REDIS_URL=redis://redis:6379/0

# --- Хранилище отчетов (Опционально) ---
# Если закомментировано, отчеты сохраняются в локальную папку ./reports
# S3_ENDPOINT_URL=http://minio:9000
# S3_ACCESS_KEY=minioadmin
# S3_SECRET_KEY=minioadmin
# S3_BUCKET_NAME=reports
# S3_REGION=us-east-1
```

---

## 📡 Использование API

### Способ 1: Через Swagger UI (Рекомендуется)
1. Откройте http://localhost:8000/docs
2. Нажмите кнопку **Authorize** 🔒 в правом верхнем углу.
3. Введите API-ключ: `sk-test-123` и нажмите Authorize.
4. Разверните эндпоинт `POST /analyze`, нажмите **Try it out**.
5. Вставьте JSON:
   ```json
   {
     "niche": "аренда лофт",
     "geo": "Москва",
     "query": "лофт с караоке и проектором",
     "clear_db": false
   }
   ```
6. Нажмите **Execute**. Вы получите `task_id`.
7. Используйте эндпоинт `GET /analyze/{task_id}`, вставив полученный `task_id`, чтобы проверить статус и получить ссылку на готовый отчет.

### Способ 2: Через cURL
```bash
# 1. Запуск задачи
curl -X POST "http://localhost:8000/analyze" \
     -H "Content-Type: application/json" \
     -H "X-API-Key: sk-test-123" \
     -d '{"niche": "аренда лофт", "geo": "Москва", "query": "лофт с караоке", "clear_db": false}'

# 2. Проверка статуса (замените YOUR_TASK_ID)
curl -X GET "http://localhost:8000/analyze/YOUR_TASK_ID" \
     -H "X-API-Key: sk-test-123"
```

---

## 📁 Структура проекта

```text
├── docker-compose.yml      # Оркестрация контейнеров (API, Worker, DB, Redis)
├── Dockerfile              # Сборка Python-образа
├── .env                    # Переменные окружения (не коммитить в Git!)
├── requirements.txt        # Python-зависимости
├── config.py               # Чтение .env и инициализация S3-клиента
├── models.py               # SQLAlchemy ORM модели (PostgreSQL + pgvector)
├── pipeline.py             # 🧠 Ядро: ETL (Парсинг, Чанкинг) + RAG (Поиск, LLM)
├── celery_app.py           # Конфигурация Celery (очереди, лимиты памяти)
├── tasks.py                # Celery-воркер (обертка над pipeline.py)
├── main.py                 # FastAPI приложение (REST API, Rate Limiting)
└── reports/                # Локальная папка для сгенерированных .md отчетов
```

---

## 🔮 Roadmap (Планы по улучшению)

- [ ] Интеграция **Cross-Encoder Reranker** для повышения точности топ-выдачи.
- [ ] Поддержка парсинга через **Playwright** для сайтов с тяжелым JavaScript.
- [ ] Добавление **Telegram-бота** для удобного запуска анализа из мессенджера.
- [ ] Интеграция **Langfuse** для мониторинга стоимости и качества LLM-запросов.
- [ ] Настройка **CI/CD** пайплайна (GitHub Actions) для автоматического тестирования и деплоя.

---

## 🤝 Вклад в проект

Pull Request'ы приветствуются! Для серьезных изменений, пожалуйста, сначала откройте Issue, чтобы обсудить, что вы хотите изменить.

---

## 📄 Лицензия

Этот проект распространяется под лицензией MIT. См. файл `LICENSE` для подробностей.

---

