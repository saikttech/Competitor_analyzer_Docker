# 1. Останавливаем всё и удаляем старые образы и тома
docker compose down -v --rmi all

# 2. Собираем образы с абсолютного нуля (игнорируем любой кэш)
docker compose build --no-cache

# 3. Запускаем проект
docker compose up

# 4. Stop проект
docker compose down

Теперь вы можете:
Открыть браузер и перейти по адресу: http://localhost:8000/docs
Найти эндпоинт POST /analyze, нажать Try it out
Вставить тестовый JSON:
   {
     "niche": "аренда лофт",
     "geo": "Москва",
     "query": "лофт с караоке",
     "clear_db": false
   }

Добавить в раздел Headers (нажать "Edit" рядом с Headers):
Name: X-API-Key
Value: sk-test-123
Нажать Execute и получить ваш task_id!