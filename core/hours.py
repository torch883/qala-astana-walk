from __future__ import annotations
import re
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from opening_hours import OpeningHours,ParserError
from core.schemas import OpenStatus
from core.settings import CONFIG

TZ=ZoneInfo(CONFIG['timezone'])

def local_time(now: datetime):
    return now.replace(tzinfo=TZ) if now.tzinfo is None else now.astimezone(TZ)

def evaluate(raw: str | None, now: datetime) -> OpenStatus:
    if not raw or not str(raw).strip():
        return OpenStatus(state='unknown',confidence='low',basis='missing_opening_hours')
    raw=str(raw).strip()
    # Holiday calendar for KZ is not verified; do not claim a confident answer.
    if re.search(r'\b(PH|SH)\b',raw):
        return OpenStatus(state='unknown',confidence='medium',basis='holiday_calendar_unverified: '+raw)
    try:
        oh=OpeningHours(raw,timezone=TZ)
        at=local_time(now)
        value=oh.state(at)
        if isinstance(value,tuple):value=value[0]
        state=str(value).lower().split('.')[-1]
        if state not in {'open','closed'}:
            return OpenStatus(state='unknown',confidence='medium',basis='conditional_hours: '+raw)
        nxt=oh.next_change(at)
        return OpenStatus(state=state,confidence='high',basis='OSM opening_hours: '+raw,next_change=nxt.isoformat() if nxt else None)
    except (ParserError,ValueError,TypeError,OverflowError):
        return OpenStatus(state='unknown',confidence='medium',basis='unparsed_opening_hours: '+raw)

def covers_visit(raw,now,travel_min,visit_min):
    current=evaluate(raw,now)
    if current.state=='closed': return False,current,'closed_now'
    arrival=local_time(now)+timedelta(minutes=travel_min)
    on_arrival=evaluate(raw,arrival)
    if on_arrival.state=='closed': return False,current,'closed_on_arrival'
    if on_arrival.state=='open' and on_arrival.next_change:
        change=datetime.fromisoformat(on_arrival.next_change)
        if change<arrival+timedelta(minutes=visit_min):
            return False,current,'closes_during_visit'
    return True,current,''
