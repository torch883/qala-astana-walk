"""Publish only metrics produced by an actual evaluation run."""
import json
from core.settings import ROOT,CONFIG
from eval.run_eval import scenarios

def main():
    report=json.loads((ROOT/'eval/results.json').read_text(encoding='utf-8'))
    rows={r['id']:r for r in report['cases']};m=report['metrics']
    lines=['# Тестовые сценарии и ограничения','',f'Последний прогон: {m["run_at"]}. Результат: **{m["passed"]}/{m["cases"]}**. Поиск: {m["retrieval_backend"]}.',f'\nВыдуманные ID: {m["hallucination_rate_pct"]}%; соответствие сценариям: {m["constraint_satisfaction_pct"]}%; корректные метки источников: {m["source_label_correct_pct"]}%. p95: {m["p95_ms"]} мс.','\nПолные входы и проверки: `tests/scenarios.yaml`. Ответы: `eval/answers.json`. Восстановление: `python -m eval.run_eval`.','\nКейс | Запрос | Локация | Время Астаны | Ожидание | Результат','--- | --- | --- | --- | --- | ---']
    for c in scenarios():
        loc=c.get('preset') or str(c.get('location'))
        if c.get('preset'):loc+=' '+str(CONFIG['presets'][c['preset']])
        lines.append(f'{c["id"]} | {c["query"] or "пустой"} | {loc} | {c["now"][:16].replace("T"," ")} | {c["expected"]} | '+('PASS' if rows[c['id']]['passed'] else 'FAIL: '+', '.join(rows[c['id']]['errors'])))
    lines+=['\n## Что именно проверяется','Существование ID и источника, совпадение вычисленных расстояния и времени, лимит пути, бюджет с возвращением, часы на весь визит, 1–3 карточки, категория, язык шаблонов, обязательные поля, отсутствие выдуманного места и правильная маркировка идей. Доступность требует wheelchair=yes. Ночью нужны open/high; непроверенное освещение открытых пространств блокирует выдачу.','\n## Контролируемые фикстуры','Кейсы missing_hours, all_closed, injection_poi, closes_on_arrival, required_socket и night_park_unknown используют реальные ID с изменениями только в памяти. Это проверка логики при заданных условиях, не утверждение о реальном месте. Остальные кейсы используют неизменённый снимок OSM. Погода в eval всегда задаётся явным сценарием (frost, blizzard, rain), без сети.','\n## Известные ограничения',f'Проверки {m["cases"]} кейсов не доказывают полноту распознавания естественного языка. Фильтр вредных запросов основан на словарях. Проверка языка определяет письменность и локализацию шаблонов; она не оценивает литературное качество. Нулевой hallucination rate означает отсутствие новых ID, а не достоверность часов и свойств OSM. Нужны пользовательское исследование, полевой аудит, реальные маршруты и проверка казахского носителем.','Gemini и LLM-обогащение без ключа не проверены в сети. Unit-тест намеренно возвращает несуществующий ID и проверяет два вызова провайдера и безопасный fallback.','Для аэропорта ожидается отказ, поскольку резерв 120 минут и дорога не оставляют времени на прогулку. Ближайшая альтернатива не выдаётся как готовая рекомендация и не ослабляет правила безопасности.']
    (ROOT/'docs/test_scenarios.md').write_text('\n'.join(lines),encoding='utf-8')
    text=(ROOT/'docs/presentation.md').read_text(encoding='utf-8')
    marker='- Результаты, задержки и ошибки — в `eval/report.md`.'
    replacement=f'- Последний прогон: **{m["passed"]}/{m["cases"]}**, выдуманные ID **{m["hallucination_rate_pct"]}%**, p95 **{m["p95_ms"]} мс**. Подробности — `eval/report.md`.'
    text=text.replace(marker,replacement)
    (ROOT/'docs/presentation.md').write_text(text,encoding='utf-8')
    print('Scenario document and slide metrics updated from actual eval')

if __name__=='__main__':main()
