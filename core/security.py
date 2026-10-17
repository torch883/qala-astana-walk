"""Untrusted OSM and user text never become system instructions."""
import re

INJECTION=re.compile(r'ignore.{0,40}instructions|system\s*prompt|игнориру\w*.{0,50}инструкц|раскрой.{0,30}ключ|<\s*/?\s*(system|script)|javascript:',re.I|re.S)

def safe_text(value,limit=500):
    text=str(value or '')
    if INJECTION.search(text): return '[untrusted text omitted]'
    return re.sub(r'[\x00-\x1f<>]',' ',text)[:limit]

def redact_query(text):
    # Coordinates and contact-like values are unnecessary for intent parsing.
    text=re.sub(r'[-+]?\d{1,3}\.\d{3,}', '[coordinate]',text)
    text=re.sub(r'\+?\d[\d\s()-]{8,}\d','[number]',text)
    return safe_text(text,1500)

# «Убить час/время» is the core use case, not a threat; only quantity words may sit in between.
KILL=r'убить(?!\s+(?:(?:\d+|пару|пол|один|одну|немного|свободн\w*|лишн\w*|оставш\w*|ещё|еще)\s+)?(?:час\w*|полчаса|врем\w*|минут\w*|вечер\w*|день|ден[её]к|утро|выходн\w*|ожидани\w*))'

def harmful(text):
    t=text.casefold()
    patterns=[r'купить.{0,25}наркот',r'взлом',r'ограб',KILL,r'самоуб',r'незакон',r'проникнуть(?!ся)',r'перелезть.{0,25}забор',r'поджечь',r'buy.{0,20}(drugs|cocaine)',r'break\s*in',r'rob\s+(a|the)',r'kill\s+(myself|someone)',r'заңсыз',r'есірткі',r'ұрлау']
    return any(re.search(p,t) for p in patterns)
