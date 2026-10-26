# Bill Splitter

Сервис на FastAPI для разделения общего счёта в компании. Можно создать счёт,
добавить участников и траты, а сервис посчитает, кто сколько потратил и кто
кому сколько должен перевести.

Пригодится, например, после совместного ужина или поездки, чтобы не считать
долги вручную.

За основу взят учебный пример app_final.py с занятий курса, тема и логика свои.

## Установка

Нужен Python 3.11 или новее.

```
git clone https://github.com/sasha-smirnov/bill-splitter.git
cd bill-splitter
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

```
./run.sh
```

Скрипт запускает uvicorn без --reload и подхватывает настройки из .env, если он есть.
Без скрипта можно так:

```
python -m uvicorn app_final:app --host 127.0.0.1 --port 8000
```

Для разработки удобнее с автоперезагрузкой: `python -m uvicorn app_final:app --reload`

Документация API открывается по адресу http://127.0.0.1:8000/docs

## Переменные окружения

Пример лежит в .env.example, можно скопировать: `cp .env.example .env`

- APP_NAME - название сервиса (по умолчанию Bill Splitter)
- CURRENCY - валюта (RUB)
- DEFAULT_TIP_PERCENT - чаевые в процентах, если не указаны в запросе (0)
- LOG_LEVEL - уровень логов (INFO)
- APP_HOST - адрес (127.0.0.1)
- APP_PORT - порт (8000)

Если задать переменную прямо в команде, она важнее .env: `APP_PORT=8001 ./run.sh`

## Маршруты

- GET / - проверка, что сервис отвечает
- GET /health - статус сервиса
- GET /version - версия
- GET /info - текущие настройки
- GET /bills - список счетов, можно фильтровать: /bills?participant=Аня
- POST /bills - создать счёт
- GET /bills/{id} - один счёт
- POST /bills/{id}/expenses - добавить трату
- DELETE /bills/{id} - удалить счёт
- GET /bills/{id}/split - кто кому должен, можно указать чаевые: ?tip=10

Данные хранятся в памяти, после перезапуска остаётся только демо-счёт с номером 1.

Пример:

```
curl -X POST http://127.0.0.1:8000/bills -H "Content-Type: application/json" -d '{"title": "Такси", "participants": ["Аня", "Борис"], "expenses": [{"description": "Такси", "payer": "Аня", "amount": 1800}]}'
curl http://127.0.0.1:8000/bills/2/split
```

## Тесты

```
pip install -r requirements-dev.txt
python -m pytest -v
```

Те же тесты запускаются в GitHub Actions при каждом push и pull request. Если они
прошли, собирается артефакт bill-splitter с файлами приложения.

## Проверка и диагностика

Проверить, что сервис работает:

```
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/version
```

Логи пишутся в терминал, где запущен сервис: старт, каждый запрос, создание счёта
и результат расчёта. Чтобы сохранить их в файл:

```
./run.sh 2>&1 | tee -a app.log
```

Найти предупреждения и ошибки: `grep -E "WARNING|ERROR" app.log`

Если что-то не работает:

- No module named 'fastapi' - не активировано окружение, нужно `source .venv/bin/activate`
- Permission denied при запуске run.sh - выполнить `chmod +x run.sh`
- Address already in use - порт занят, посмотреть кем: `lsof -i :8000`, или запустить на другом порту
- Настройка не применилась - перезапустить сервис и посмотреть /info
- Ответ 422 - неправильные входные данные, причина написана в поле detail
- Упал CI - открыть запуск во вкладке Actions или выполнить `gh run view --log-failed`
