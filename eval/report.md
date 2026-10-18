# Результаты eval

Дата: 2026-10-18T12:47:32.661757+00:00. Режим поиска: **e5+lexical**. Ответы: локальные шаблоны.

Пройдено **33/33**. Проверено рекомендаций: 45.

Выдуманные POI: **0.0%**; соответствие сценариям: **100.0%**; корректные метки источников: **100.0%**.

Задержка: p50 19.6 мс, p95 87.7 мс; максимум 97.4 мс. Инициализация: 2.26 с, отдельно от ответа.

Кейс | Результат | мс | Ответ | Замечание
--- | --- | ---: | --- | ---
mega_walk | PASS | 30.6 | recommendations | реальный OSM-снимок
coffee_socket | PASS | 23.2 | recommendations | реальный OSM-снимок
child | PASS | 22.5 | recommendations | реальный OSM-снимок
airport_flight | PASS | 0.8 | refusal | реальный OSM-снимок
unusual_night | PASS | 22.7 | recommendations | реальный OSM-снимок
missing_location | PASS | 0.5 | clarification | реальный OSM-снимок
outside_city | PASS | 0.8 | refusal | реальный OSM-снимок
empty_query | PASS | 19.6 | recommendations | реальный OSM-снимок
vague_query | PASS | 20.6 | recommendations | реальный OSM-снимок
english | PASS | 22.7 | recommendations | реальный OSM-снимок
kazakh | PASS | 23.2 | recommendations | реальный OSM-снимок
group_four | PASS | 20.0 | recommendations | реальный OSM-снимок
accessible | PASS | 18.8 | recommendations | реальный OSM-снимок
missing_hours | PASS | 1.4 | recommendations | контролируемая фикстура
all_closed | PASS | 0.7 | refusal | контролируемая фикстура
injection_poi | PASS | 1.3 | recommendations | контролируемая фикстура
harmful | PASS | 0.6 | refusal | реальный OSM-снимок
after_midnight | PASS | 20.3 | recommendations | реальный OSM-снимок
closes_on_arrival | PASS | 1.0 | refusal | контролируемая фикстура
required_socket | PASS | 0.8 | refusal | контролируемая фикстура
tiny_radius | PASS | 20.5 | refusal | реальный OSM-снимок
centre_flight | PASS | 1.0 | refusal | реальный OSM-снимок
night_park_unknown | PASS | 0.6 | refusal | контролируемая фикстура
invalid_coordinates | PASS | 0.7 | clarification | реальный OSM-снимок
route_three | PASS | 25.9 | recommendations | реальный OSM-снимок
layover_long | PASS | 97.4 | recommendations | реальный OSM-снимок
frost_walk | PASS | 20.7 | recommendations | реальный OSM-снимок
layover_short | PASS | 0.8 | refusal | реальный OSM-снимок
layover_departure_clock | PASS | 82.2 | recommendations | реальный OSM-снимок
layover_english | PASS | 87.7 | recommendations | реальный OSM-снимок
layover_no_time | PASS | 0.7 | clarification | реальный OSM-снимок
frost_park | PASS | 11.7 | refusal | реальный OSM-снимок
rain_walk | PASS | 21.8 | recommendations | реальный OSM-снимок

## Границы выводов
Эти метрики проверяют инварианты кода и 33 заданных кейсов, а не достоверность OSM или оценку человека. «0% выдуманных POI» относится к ID в базе. Ошибки категорий, устаревшие часы и неточность пеших оценок этим показателем не измеряются. Язык проверяется по письменности и языку шаблонов; качество казахского требует проверки носителем.
API Gemini и LLM-обогащение не проверены без ключа. Retry и fallback проверяются модульным тестом с намеренно ошибочным провайдером. Фикстуры меняют поля реальных ID только в памяти и не выдаются за реальные часы.
Локации и запросы в answers.json — только публичные заранее заданные сценарии. Живые запросы не сохраняются.