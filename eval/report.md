# Результаты eval

Дата: 2026-10-17T19:16:09.245403+00:00. Режим поиска: **e5+lexical**. Ответы: локальные шаблоны.

Пройдено **33/33**. Проверено рекомендаций: 45.

Выдуманные POI: **0.0%**; соответствие сценариям: **100.0%**; корректные метки источников: **100.0%**.

Задержка: p50 14.3 мс, p95 61.6 мс; максимум 73.9 мс. Инициализация: 1.65 с, отдельно от ответа.

Кейс | Результат | мс | Ответ | Замечание
--- | --- | ---: | --- | ---
mega_walk | PASS | 36.6 | recommendations | реальный OSM-снимок
coffee_socket | PASS | 19.7 | recommendations | реальный OSM-снимок
child | PASS | 18.2 | recommendations | реальный OSM-снимок
airport_flight | PASS | 0.6 | refusal | реальный OSM-снимок
unusual_night | PASS | 16.8 | recommendations | реальный OSM-снимок
missing_location | PASS | 0.3 | clarification | реальный OSM-снимок
outside_city | PASS | 0.3 | refusal | реальный OSM-снимок
empty_query | PASS | 14.3 | recommendations | реальный OSM-снимок
vague_query | PASS | 15.0 | recommendations | реальный OSM-снимок
english | PASS | 15.7 | recommendations | реальный OSM-снимок
kazakh | PASS | 17.0 | recommendations | реальный OSM-снимок
group_four | PASS | 15.7 | recommendations | реальный OSM-снимок
accessible | PASS | 15.2 | recommendations | реальный OSM-снимок
missing_hours | PASS | 0.9 | recommendations | контролируемая фикстура
all_closed | PASS | 0.5 | refusal | контролируемая фикстура
injection_poi | PASS | 0.8 | recommendations | контролируемая фикстура
harmful | PASS | 0.4 | refusal | реальный OSM-снимок
after_midnight | PASS | 15.7 | recommendations | реальный OSM-снимок
closes_on_arrival | PASS | 0.5 | refusal | контролируемая фикстура
required_socket | PASS | 0.5 | refusal | контролируемая фикстура
tiny_radius | PASS | 14.8 | refusal | реальный OSM-снимок
centre_flight | PASS | 0.5 | refusal | реальный OSM-снимок
night_park_unknown | PASS | 0.4 | refusal | контролируемая фикстура
invalid_coordinates | PASS | 0.3 | clarification | реальный OSM-снимок
route_three | PASS | 18.1 | recommendations | реальный OSM-снимок
layover_long | PASS | 73.9 | recommendations | реальный OSM-снимок
frost_walk | PASS | 16.4 | recommendations | реальный OSM-снимок
layover_short | PASS | 0.6 | refusal | реальный OSM-снимок
layover_departure_clock | PASS | 61.6 | recommendations | реальный OSM-снимок
layover_english | PASS | 60.4 | recommendations | реальный OSM-снимок
layover_no_time | PASS | 0.4 | clarification | реальный OSM-снимок
frost_park | PASS | 8.5 | refusal | реальный OSM-снимок
rain_walk | PASS | 13.6 | recommendations | реальный OSM-снимок

## Границы выводов
Эти метрики проверяют инварианты кода и 33 заданных кейсов, а не достоверность OSM или оценку человека. «0% выдуманных POI» относится к ID в базе. Ошибки категорий, устаревшие часы и неточность пеших оценок этим показателем не измеряются. Язык проверяется по письменности и языку шаблонов; качество казахского требует проверки носителем.
API Gemini и LLM-обогащение не проверены без ключа. Retry и fallback проверяются модульным тестом с намеренно ошибочным провайдером. Фикстуры меняют поля реальных ID только в памяти и не выдаются за реальные часы.
Локации и запросы в answers.json — только публичные заранее заданные сценарии. Живые запросы не сохраняются.