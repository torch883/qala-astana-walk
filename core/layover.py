"""«Астана за пересадку»: a city outing planned backwards from the departure, with a hard return deadline."""
from __future__ import annotations
import math
from datetime import datetime,timedelta
from core.geo import haversine,round_location
from core.schemas import LayoverPlan
from core.settings import CONFIG

def airport():return round_location(*CONFIG['presets']['Аэропорт'])

def transfer_min(a,b):
    # Conservative taxi estimate: straight line x detour at highway speed, traffic buffer and pickup overhead.
    c=CONFIG['layover']
    return math.ceil(haversine(*a,*b)*CONFIG['detour_factor']/c['transfer_m_per_min']*c['traffic_buffer'])+c['transfer_overhead_min']

def layover_minutes(intent,now):
    # A departure time is the real deadline, so it wins over a stated layover length.
    if not intent.departure_clock:return intent.layover_min
    hh,mm=map(int,intent.departure_clock.split(':'))
    departure=now.replace(hour=hh,minute=mm,second=0,microsecond=0)
    if departure<=now:departure+=timedelta(days=1)
    return int((departure-now).total_seconds()//60)

def windows(layover,now,transfer_floor=0,deadline=None):
    """Every anchor whose city window is long enough; each window is derived backwards from the departure."""
    c=CONFIG['layover'];departure=now+timedelta(minutes=layover);out=[]
    for name in c['anchors']:
        anchor=round_location(*CONFIG['presets'][name]);transfer=max(transfer_floor,transfer_min(airport(),anchor))
        city=layover-c['exit_min']-c['return_reserve_min']-2*transfer
        if city<c['min_city_min']:continue
        arrive=now+timedelta(minutes=c['exit_min']+transfer)
        leave=departure-timedelta(minutes=c['return_reserve_min']+transfer)
        if deadline is not None:
            leave=min(leave,deadline)
            city=min(city,int((leave-arrive).total_seconds()//60))
            if city<c['min_city_min']:continue
        # Earlier user deadlines preserve at least the configured airport reserve.
        actual_reserve=int((departure-(leave+timedelta(minutes=transfer))).total_seconds()//60)
        out.append(LayoverPlan(anchor=name,anchor_lat=anchor[0],anchor_lon=anchor[1],layover_min=layover,exit_min=c['exit_min'],transfer_min=transfer,reserve_min=actual_reserve,city_min=min(city,c['max_city_min']),arrive_city=arrive.isoformat(),leave_city_by=leave.isoformat(),back_at_airport_by=(leave+timedelta(minutes=transfer)).isoformat(),departure=departure.isoformat()))
    return out

def check_plan(plan,route=None):
    """Arithmetic guarantee: the outing ends by leave_city_by and the reserve before departure stays intact."""
    arrive,leave,back,dep=(datetime.fromisoformat(x) for x in [plan.arrive_city,plan.leave_city_by,plan.back_at_airport_by,plan.departure])
    if arrive+timedelta(minutes=plan.city_min)>leave:raise ValueError('layover_window')
    if back+timedelta(minutes=plan.reserve_min)!=dep or back-leave!=timedelta(minutes=plan.transfer_min):raise ValueError('layover_reserve')
    if route and route.total_min>plan.city_min:raise ValueError('layover_route')
    return True
