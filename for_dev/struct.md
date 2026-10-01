```
news_classifier/
├── config.yaml               # Конфигурация фидов, моделей, перевода и порогов
├── requirements.txt          # Зависимости проекта
├── data/
│   ├── branches.json         # Определения и ключевые слова отраслей
│   └── seen_news.db          # База дедупликации (SQLite)
├── src/
│   ├── models.py             # Датаклассы (NewsItem, BranchHit, ImpactHit, ClassifiedNews)
│   ├── translate.py          # Автоматический перевод EN -> RU с кешированием и failover
│   ├── pipeline.py           # Конвейер объединения Ingestion -> Translation -> Stage 1 -> Stage 2
│   ├── ingest/               # Модули сбора новостей
│   │   ├── base.py           # Базовый абстрактный класс + определение языка
│   │   ├── foreign_rss.py    # CNBC & BBC коннектор с User-Agent
│   │   ├── bloomberg_rss.py  # Bloomberg RSS коннектор
│   │   └── interfax_rss.py   # Интерфакс коннектор
│   ├── classify/             # Классификаторы
│   │   ├── branch_classifier.py  # Stage 1: Multilingual Zero-Shot NLI + Fallback
│   │   └── impact_classifier.py  # Stage 2: FinBERT / RuSentiment + Fallback
│   ├── storage/
│   │   └── dedup.py          # SQLite хранилище дедупликации
│   └── alerts/
│       ├── formatter.py      # Красивый форматированный вывод алертов (время, перевод)
│       └── telegram_notifier.py # Telegram Bot API диспетчер с поддержкой HTML и перевода
├── scripts/
│   ├── watch.py              # Real-Time демон мониторинга
│   └── run_demo.py           # Одноразовый тестовый запуск
└── tests/
    ├── test_pipeline.py      # Тесты пайплайна
    ├── test_dedup.py         # Тесты хранилища дедупликации
    ├── test_translation_and_time.py # Тесты времени публикации и перевода
    ├── test_branch_filtering.py     # Тесты выбора тем и пресетов (forex/crypto/etc.)
    └── test_freshness.py            # Тесты отсечения старых новостей и бейджей свежести
```