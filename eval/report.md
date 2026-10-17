# Результаты eval

Дата: 2026-10-17T18:50:32.506292+00:00. Режим поиска: **e5+lexical**. Ответы: локальные шаблоны.

Пройдено **25/25**. Проверено рекомендаций: 30.

Выдуманные POI: **0.0%**; соответствие сценариям: **100.0%**; корректные метки источников: **100.0%**.

Задержка: p50 13.2 мс, p95 17.5 мс; максимум 26.6 мс. Инициализация: 1.16 с, отдельно от ответа.

Кейс | Результат | мс | Ответ | Замечание
--- | --- | ---: | --- | ---
mega_walk | PASS | 26.6 | recommendations | реальный OSM-снимок
coffee_socket | PASS | 17.2 | recommendations | реальный OSM-снимок
child | PASS | 17.5 | recommendations | реальный OSM-снимок
airport_flight | PASS | 0.5 | refusal | реальный OSM-снимок
unusual_night | PASS | 15.8 | recommendations | реальный OSM-снимок
missing_location | PASS | 0.3 | clarification | реальный OSM-снимок
outside_city | PASS | 0.3 | refusal | реальный OSM-снимок
empty_query | PASS | 13.2 | recommendations | реальный OSM-снимок
vague_query | PASS | 13.8 | recommendations | реальный OSM-снимок
english | PASS | 14.5 | recommendations | реальный OSM-снимок
kazakh | PASS | 15.9 | recommendations | реальный OSM-снимок
group_four | PASS | 14.4 | recommendations | реальный OSM-снимок
accessible | PASS | 13.8 | recommendations | реальный OSM-снимок
missing_hours | PASS | 0.8 | recommendations | контролируемая фикстура
all_closed | PASS | 0.4 | refusal | контролируемая фикстура
injection_poi | PASS | 0.7 | recommendations | контролируемая фикстура
harmful | PASS | 0.4 | refusal | реальный OSM-снимок
after_midnight | PASS | 14.3 | recommendations | реальный OSM-снимок
closes_on_arrival | PASS | 0.4 | refusal | контролируемая фикстура
required_socket | PASS | 0.4 | refusal | контролируемая фикстура
tiny_radius | PASS | 14.1 | refusal | реальный OSM-снимок
centre_flight | PASS | 0.4 | refusal | реальный OSM-снимок
night_park_unknown | PASS | 0.4 | refusal | контролируемая фикстура
invalid_coordinates | PASS | 0.3 | clarification | реальный OSM-снимок
route_three | PASS | 15.9 | recommendations | реальный OSM-снимок

## Границы выводов
Эти метрики проверяют инварианты кода и 25 заданных кейсов, а не достоверность OSM или оценку человека. «0% выдуманных POI» относится к ID в базе. Ошибки категорий, устаревшие часы и неточность пеших оценок этим показателем не измеряются. Язык проверяется по письменности и языку шаблонов; качество казахского требует проверки носителем.
API Gemini и LLM-обогащение не проверены без ключа. Retry и fallback проверяются модульным тестом с намеренно ошибочным провайдером. Фикстуры меняют поля реальных ID только в памяти и не выдаются за реальные часы.
Локации и запросы в answers.json — только публичные заранее заданные сценарии. Живые запросы не сохраняются.