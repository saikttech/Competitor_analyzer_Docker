# Запуск задачи
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"niche": "аренда лофт", "geo": "Москва", "query": "лофт с караоке"}'

# Проверка статуса (вставьте task_id)
curl http://localhost:8000/analyze/<task_id>