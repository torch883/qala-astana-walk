# Результаты eval

Дата: 2026-10-17T16:59:38.831850+00:00. Режим поиска: **e5+lexical**. Ответы: локальные шаблоны.

Пройдено **25/25**. Проверено рекомендаций: 29.

Выдуманные POI: **0.0%**; соответствие сценариям: **100.0%**; корректные метки источников: **100.0%**.

Задержка: p50 94.6 мс, p95 146.0 мс; максимум 187.4 мс. Инициализация: 8.1 с, отдельно от ответа.

Кейс | Результат | мс | Ответ | Замечание
--- | --- | ---: | --- | ---
mega_walk | PASS | 146.0 | recommendations | реальный OSM-снимок
coffee_socket | PASS | 125.0 | recommendations | реальный OSM-снимок
child | PASS | 128.8 | recommendations | реальный OSM-снимок
airport_flight | PASS | 1.1 | refusal | реальный OSM-снимок
unusual_night | PASS | 135.7 | recommendations | реальный OSM-снимок
missing_location | PASS | 0.8 | clarification | реальный OSM-снимок
outside_city | PASS | 1.0 | refusal | реальный OSM-снимок
empty_query | PASS | 94.6 | recommendations | реальный OSM-снимок
vague_query | PASS | 110.1 | recommendations | реальный OSM-снимок
english | PASS | 105.1 | recommendations | реальный OSM-снимок
kazakh | PASS | 123.8 | recommendations | реальный OSM-снимок
group_four | PASS | 107.3 | recommendations | реальный OSM-снимок
accessible | PASS | 98.9 | recommendations | реальный OSM-снимок
missing_hours | PASS | 5.2 | recommendations | контролируемая фикстура
all_closed | PASS | 1.8 | refusal | контролируемая фикстура
injection_poi | PASS | 4.6 | recommendations | контролируемая фикстура
harmful | PASS | 0.5 | refusal | реальный OSM-снимок
after_midnight | PASS | 101.9 | recommendations | реальный OSM-снимок
closes_on_arrival | PASS | 2.8 | refusal | контролируемая фикстура
required_socket | PASS | 1.8 | refusal | контролируемая фикстура
tiny_radius | PASS | 131.6 | refusal | реальный OSM-снимок
centre_flight | PASS | 1.4 | refusal | реальный OSM-снимок
night_park_unknown | PASS | 2.6 | refusal | контролируемая фикстура
invalid_coordinates | PASS | 0.3 | clarification | реальный OSM-снимок
route_three | PASS | 187.4 | recommendations | реальный OSM-снимок

## Границы выводов
Эти метрики проверяют инварианты кода и 25 заданных кейсов, а не достоверность OSM или оценку человека. «0% выдуманных POI» относится к ID в базе. Ошибки категорий, устаревшие часы и неточность пеших оценок этим показателем не измеряются. Язык проверяется по письменности и языку шаблонов; качество казахского требует проверки носителем.
API Gemini и LLM-обогащение не проверены без ключа. Retry и fallback проверяются модульным тестом с намеренно ошибочным провайдером. Фикстуры меняют поля реальных ID только в памяти и не выдаются за реальные часы.
Локации и запросы в answers.json — только публичные заранее заданные сценарии. Живые запросы не сохраняются.