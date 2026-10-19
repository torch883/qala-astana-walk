# Результаты eval

Дата: 2026-10-19T11:33:32.071050+00:00. Режим поиска: **e5+lexical**. Ответы: локальные шаблоны.

Пройдено **33/33**. Проверено рекомендаций: 45.

Выдуманные POI: **0.0%**; соответствие сценариям: **100.0%**; корректные метки источников: **100.0%**.

Задержка: p50 16.4 мс, p95 444.1 мс; максимум 444.5 мс. Инициализация: 1.33 с, отдельно от ответа.

Кейс | Результат | мс | Ответ | Замечание
--- | --- | ---: | --- | ---
mega_walk | PASS | 22.8 | recommendations | реальный OSM-снимок
coffee_socket | PASS | 18.5 | recommendations | реальный OSM-снимок
child | PASS | 17.2 | recommendations | реальный OSM-снимок
airport_flight | PASS | 0.6 | refusal | реальный OSM-снимок
unusual_night | PASS | 17.0 | recommendations | реальный OSM-снимок
missing_location | PASS | 0.3 | clarification | реальный OSM-снимок
outside_city | PASS | 0.4 | refusal | реальный OSM-снимок
empty_query | PASS | 14.2 | recommendations | реальный OSM-снимок
vague_query | PASS | 16.4 | recommendations | реальный OSM-снимок
english | PASS | 15.3 | recommendations | реальный OSM-снимок
kazakh | PASS | 17.2 | recommendations | реальный OSM-снимок
group_four | PASS | 57.0 | recommendations | реальный OSM-снимок
accessible | PASS | 74.2 | recommendations | реальный OSM-снимок
missing_hours | PASS | 4.3 | recommendations | контролируемая фикстура
all_closed | PASS | 2.1 | refusal | контролируемая фикстура
injection_poi | PASS | 3.9 | recommendations | контролируемая фикстура
harmful | PASS | 1.8 | refusal | реальный OSM-снимок
after_midnight | PASS | 98.1 | recommendations | реальный OSM-снимок
closes_on_arrival | PASS | 2.7 | refusal | контролируемая фикстура
required_socket | PASS | 2.3 | refusal | контролируемая фикстура
tiny_radius | PASS | 84.5 | refusal | реальный OSM-снимок
centre_flight | PASS | 1.2 | refusal | реальный OSM-снимок
night_park_unknown | PASS | 1.9 | refusal | контролируемая фикстура
invalid_coordinates | PASS | 1.3 | clarification | реальный OSM-снимок
route_three | PASS | 97.2 | recommendations | реальный OSM-снимок
layover_long | PASS | 444.1 | recommendations | реальный OSM-снимок
frost_walk | PASS | 104.8 | recommendations | реальный OSM-снимок
layover_short | PASS | 2.9 | refusal | реальный OSM-снимок
layover_departure_clock | PASS | 444.5 | recommendations | реальный OSM-снимок
layover_english | PASS | 418.5 | recommendations | реальный OSM-снимок
layover_no_time | PASS | 2.2 | clarification | реальный OSM-снимок
frost_park | PASS | 72.5 | refusal | реальный OSM-снимок
rain_walk | PASS | 112.8 | recommendations | реальный OSM-снимок

## Границы выводов
Эти метрики проверяют инварианты кода и 33 заданных кейсов, а не достоверность OSM или оценку человека. «0% выдуманных POI» относится к ID в базе. Ошибки категорий, устаревшие часы и неточность пеших оценок этим показателем не измеряются. Язык проверяется по письменности и языку шаблонов; качество казахского требует проверки носителем.
API Gemini и LLM-обогащение не проверены без ключа. Retry и fallback проверяются модульным тестом с намеренно ошибочным провайдером. Фикстуры меняют поля реальных ID только в памяти и не выдаются за реальные часы.
Локации и запросы в answers.json — только публичные заранее заданные сценарии. Живые запросы не сохраняются.