#!/usr/bin/env python3
"""Pannello meteo per Kindle 4 (600x800, scala di grigi).
Data, meteo, vento, mare e maree, orari di pesca (solunari).
Gira su GitHub Actions ogni 30 minuti e pubblica dashboard.png.
Uso: python3 genera.py [--demo] [--out dashboard.png]
"""
import io, json, math, os, sys, datetime as dt, urllib.request
from zoneinfo import ZoneInfo
import base64
import ephem
from PIL import Image, ImageDraw, ImageFont

# ---------------- CONFIGURAZIONE ----------------
LUOGO = "CERVIA"
LAT, LON = 44.2614, 12.3553          # meteo (centro di Cervia)
MARE_LAT, MARE_LON = 44.27, 12.40    # punto in mare davanti a Cervia
TZ = ZoneInfo("Europe/Rome")
W, H = 600, 800
# ------------------------------------------------

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
def F(size, bold=False, serif=False, italic=False):
    name = "DejaVuSerif" if serif else "DejaVuSans"
    if bold and italic: name += "-BoldOblique" if not serif else "-BoldItalic"
    elif bold: name += "-Bold"
    elif italic: name += "-Oblique" if not serif else "-Italic"
    for d in (os.path.join(BASE, "fonts"), FONT_DIR):
        p = os.path.join(d, name + ".ttf")
        if os.path.exists(p): return ImageFont.truetype(p, size)
    return ImageFont.load_default()

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]
MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio",
        "agosto", "settembre", "ottobre", "novembre", "dicembre"]

WMO = {0: ("Sereno", "sun"), 1: ("Poco nuvoloso", "cloud-sun"), 2: ("Parz. nuvoloso", "cloud-sun"),
       3: ("Coperto", "cloud"), 45: ("Nebbia", "cloud-fog"), 48: ("Nebbia", "cloud-fog"),
       51: ("Pioviggine", "cloud-drizzle"), 53: ("Pioviggine", "cloud-drizzle"), 55: ("Pioviggine", "cloud-drizzle"),
       56: ("Pioggia gelata", "cloud-drizzle"), 57: ("Pioggia gelata", "cloud-drizzle"),
       61: ("Pioggia debole", "cloud-rain"), 63: ("Pioggia", "cloud-rain"), 65: ("Pioggia forte", "cloud-rain-wind"),
       66: ("Pioggia gelata", "cloud-rain"), 67: ("Pioggia gelata", "cloud-rain"),
       71: ("Neve debole", "cloud-snow"), 73: ("Neve", "cloud-snow"), 75: ("Neve forte", "cloud-snow"),
       77: ("Nevischio", "cloud-snow"), 80: ("Rovesci", "cloud-rain"), 81: ("Rovesci", "cloud-rain"),
       82: ("Rovesci forti", "cloud-rain-wind"), 85: ("Rovesci di neve", "cloud-snow"),
       86: ("Rovesci di neve", "cloud-snow"), 95: ("Temporale", "cloud-lightning"),
       96: ("Temporale", "cloud-lightning"), 99: ("Temporale", "cloud-lightning")}

VENTI = ["Tramontana", "Grecale", "Levante", "Scirocco", "Ostro", "Libeccio", "Ponente", "Maestrale"]
SIGLE = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
def vento_nome(deg):
    i = int((deg % 360 + 22.5) // 45) % 8
    return VENTI[i], SIGLE[i]
def beaufort(kmh):
    lim = [1, 6, 12, 20, 29, 39, 50, 62, 75, 89, 103, 118]
    return next((i for i, l in enumerate(lim) if kmh < l), 12)
def mare_douglas(m):
    for lim, nome in [(0.1, "calmo"), (0.5, "poco mosso"), (1.25, "mosso"), (2.5, "molto mosso"),
                      (4, "agitato"), (6, "molto agitato"), (9, "grosso")]:
        if m < lim: return nome
    return "molto grosso"

# ---------------- DATI ----------------
def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "kindle-meteo/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def dati_meteo():
    return get_json(
        "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
        "&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,"
        "precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,sunrise,sunset"
        "&timezone=Europe%%2FRome&forecast_days=4" % (LAT, LON))

def dati_mare():
    return get_json(
        "https://marine-api.open-meteo.com/v1/marine?latitude=%s&longitude=%s"
        "&hourly=sea_level_height_msl&daily=wave_height_max"
        "&current=wave_height,sea_surface_temperature"
        "&timezone=Europe%%2FRome&forecast_days=2" % (MARE_LAT, MARE_LON))

def dati_demo(oggi):
    """Dati di esempio, solo per l'anteprima."""
    days = [(oggi + dt.timedelta(d)).isoformat() for d in range(4)]
    meteo = {"daily": {"time": days, "weather_code": [2, 61, 3, 0], "temperature_2m_max": [17.4, 15.1, 16.0, 18.2],
             "temperature_2m_min": [9.8, 10.4, 8.7, 7.9], "precipitation_probability_max": [10, 80, 35, 5],
             "precipitation_sum": [0, 6.4, 0.8, 0], "wind_speed_10m_max": [14, 27, 18, 9],
             "wind_gusts_10m_max": [25, 48, 30, 17], "wind_direction_10m_dominant": [100, 140, 40, 270],
             "sunrise": [days[0] + "T06:51"], "sunset": [days[0] + "T17:02"]}}
    times, lv = [], []
    for h in range(48):
        t = dt.datetime.combine(oggi, dt.time()) + dt.timedelta(hours=h)
        times.append(t.strftime("%Y-%m-%dT%H:%M"))
        lv.append(0.22 * math.cos(2 * math.pi * (h - 3.2) / 12.42) + 0.08 * math.cos(2 * math.pi * (h - 9) / 24.0))
    mare = {"hourly": {"time": times, "sea_level_height_msl": lv},
            "daily": {"time": days[:2], "wave_height_max": [0.4, 1.1]},
            "current": {"wave_height": 0.3, "sea_surface_temperature": 18.6}}
    return meteo, mare

# ---------------- CALCOLI ----------------
def maree(mare, giorno):
    """Alte e basse maree del giorno, con interpolazione parabolica sui dati orari."""
    t = [dt.datetime.fromisoformat(x) for x in mare["hourly"]["time"]]
    v = mare["hourly"]["sea_level_height_msl"]
    out = []
    for i in range(1, len(v) - 1):
        if v[i] is None or v[i - 1] is None or v[i + 1] is None: continue
        a, b, c = v[i - 1], v[i], v[i + 1]
        tipo = "alta" if b > a and b >= c else "bassa" if b < a and b <= c else None
        if not tipo: continue
        den = a - 2 * b + c
        off = 0.5 * (a - c) / den if den else 0
        quando = t[i] + dt.timedelta(hours=off)
        livello = b - 0.25 * (a - c) * off
        out.append((quando, tipo, livello))
    # scarta oscillazioni sotto i 5 cm (rumore del modello)
    cambiato = True
    while cambiato:
        cambiato = False
        for i in range(len(out) - 1):
            if abs(out[i][2] - out[i + 1][2]) < 0.05:
                del out[i:i + 2]; cambiato = True; break
    return [x for x in out if x[0].date() == giorno]

def _local(d): return ephem.localtime(d).replace(tzinfo=None) if False else ephem.Date(d).datetime().replace(tzinfo=dt.timezone.utc).astimezone(TZ)

def solunari(giorno):
    """Periodi solunari: maggiori (luna al meridiano e all'antimeridiano, ±1h),
    minori (alba e tramonto della luna, ±30 min). Fase lunare e giudizio della giornata."""
    obs = ephem.Observer(); obs.lat, obs.lon = str(LAT), str(LON); obs.elevation = 2
    obs.pressure = 0; obs.horizon = "-0:34"
    inizio = dt.datetime.combine(giorno, dt.time(), TZ).astimezone(dt.timezone.utc)
    fine = inizio + dt.timedelta(days=1)
    luna = ephem.Moon()
    eventi = []
    for nome, fn in [("transito", obs.next_transit), ("antitransito", obs.next_antitransit),
                     ("sorge", obs.next_rising), ("tramonta", obs.next_setting)]:
        obs.date = ephem.Date(inizio - dt.timedelta(hours=2))
        while True:
            try: d = fn(luna)
            except (ephem.AlwaysUpError, ephem.NeverUpError): break
            t = _local(d)
            if t.astimezone(dt.timezone.utc) >= fine + dt.timedelta(hours=2): break
            if t.date() == giorno: eventi.append((nome, t))
            obs.date = ephem.Date(d + ephem.minute)
    maggiori = sorted([(t - dt.timedelta(hours=1), t + dt.timedelta(hours=1)) for n, t in eventi if n in ("transito", "antitransito")])
    minori = sorted([(t - dt.timedelta(minutes=30), t + dt.timedelta(minutes=30)) for n, t in eventi if n in ("sorge", "tramonta")])
    # fase lunare
    mezzodi = dt.datetime.combine(giorno, dt.time(12), TZ).astimezone(dt.timezone.utc)
    luna.compute(ephem.Date(mezzodi))
    illum = luna.moon_phase
    pn = ephem.previous_new_moon(ephem.Date(mezzodi)); nn = ephem.next_new_moon(ephem.Date(mezzodi))
    eta = (ephem.Date(mezzodi) - pn) / (nn - pn)  # 0..1
    if eta < 0.03 or eta > 0.97: fase = "Luna nuova"
    elif eta < 0.22: fase = "Luna crescente"
    elif eta < 0.28: fase = "Primo quarto"
    elif eta < 0.47: fase = "Gibbosa crescente"
    elif eta < 0.53: fase = "Luna piena"
    elif eta < 0.72: fase = "Gibbosa calante"
    elif eta < 0.78: fase = "Ultimo quarto"
    else: fase = "Luna calante"
    vic = min(abs(eta - 0), abs(eta - 0.5), abs(eta - 1))  # vicinanza a nuova/piena
    stelle = 4 if vic < 0.05 else 3 if vic < 0.12 else 2 if vic < 0.2 else 1
    return maggiori, minori, fase, illum, eta, stelle

# ---------------- DISEGNO ----------------
NERO, GRIGIO, CHIARO = 0, 90, 200

ICONE = {"sun-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAADdUlEQVR42u1YvW7UQBD+7FziQECkAHRSIrmhS5GKOq6oaZICGmoaKOjPj5BHSEFFAZSIhn0EP0AkAkqUKKE4iVN+7g4Phfd/x2ZzQUIocePV+PPs7Mx8s7MLXOPn5XYMKqXzGNgS1cy/geQ+kiJC2waRiNDGGxxICmD572m7gf072AM2ebS017yS44PVEJW8e3zHS9lfTL5lOpFTlbKp0j8EFKzvJ/IGUSWHOZH6NvATeUA00jOp+RPSPxuH3JLvsTiUowXOb8o4erKqTePcq8g+UYIXgYfWyRgHyzQqHW1DyzjYprkrzYiMH4xnjNOtCURAf22InJRKBCwuAOwinGHPFX0J7UBGRENXZJum/DaWy7UeAZz5MOUg99kNJDm30jClMy1UmZ37Xms81wiTD0Rv5Y8jxo6VHQDAKyKiJgveFx11nIi4Wh76NPQ0ryxU57H+jVpQ1aUsIfWMurTdZkYM7JHRW/55neFaE0e1FZ2LxdZJ51vGHqwPAJOt5za7+T2S6gJYYQjkrWBfua89XpqsecgMuxlQJMmI3MYg9Zzzs/GGqcohbBFApancuhXcM/zNiagNlhv+Zh7jbdXLpgROZQ1pgU3lsO6AFcAP5UHhFqgegE1g8rGBaZ+KooGpb82q6qKJlbDCuwcZ3cLkYtXEqrRq9rDZVmR0U02RENZQ6BxIZf71dE0zpV3l9jyQSkDPy3dblBiHJGxcejPu9XygpwY2VQIKMaRUpDLaU7NlqPjqOSZAilrwNdvU96PoYPWAb1vARNhzmdkPrG9WX7BnUbZqJ/3IqoeiJS2Hxu2ptzF7sHkrSuJqBFwyBm10bCFzpsAQ0bStOBCAuw2b7bD7sFoXyT6A884yOFJlsLpqUc2JiMabzyjocRwOZJY99VxrwZ+0jD1Ybdlz1EGgdbNnlRGbcxAql6enzIiBmal2O9mdxbUEF3Kt3xHTYXS0K3HNT2QrFdmYRbZ5A65Trbi2J4SNMFtD22cbWt1lpNbZIIRh+3Kt++UOAozI+TU1xfTMg42t4iphT5lMpFJ+cPPttd+S7XBpqdiXfN4POWhaHGXaQlHbxjnahDGtb85vpe9y6xi5bqic+76MPMae4pC5DxmLU3cJ9HCN2wC31jyHnLDFUUtvbjD+a5gI6B+vja2HxaxXiJEXknNhyp58/XSNL3d/A7atRSLgNP6TAAAAAElFTkSuQmCC", "sun-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABVklEQVR42q2UMU7DMBSGP7tpg9SlEwMLnVhzBHIE9nIIbtAcoQMHYKiYuYF9hBygQxZQRySQiEqax+DnpLSRQAgP8fOfxPn8/vcCvx2T1ZFw+a6B1XmW/CR042+CWcfFRQ5A2gJZDbgSgKkUAcxKpUIFttAASKUOW2RSgoVPxkG44SkErj2YLXAXP7tTYSNwfg9+qzfMmonIKnIBsBTZh2gUDuDAGN8/MBURpYpIIopnFenlNuIBIC046ddGasgk714xbGHDoVBBrYJxbZ7gQZgZ1+akIj6VHIyUqYi3CcyT3r35qQ0NVE2IXxuoMK7NUynASmlcGzIwEq8X5RDmcIYfRB8+HEt5XsQcHifoJIWB9APgAYZsGDRqug9WLqMRWXS/1k27up8EwebK6E0xXFIJ29AvG2bDZfm9cBPYPcZ+WVz1tNfN/zZQ59qwMNL5bex/+1f4Ap8jnoWhkQhBAAAAAElFTkSuQmCC", "cloud-sun-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAAD6ElEQVR42u1YvW4TQRD+9mLjgJFwAREoSKagoAsNFQVb8QQJBTS0ICQo6ONHQIgHoKCigLyB7xHyABSWSBSgOilG+H8o7vZu5+fsK5AoYBufx9/OzM5+83MG/uH1/E0TVEKTJrAurYy9SnIVzjfQ9oAobaDNdlhJPND7c9r+w/4e7JpJnlLayj/cj9ObGuU+3rssKLs0+NYpiZwEyiZBfwYE2HVJ5AdEx8Vjnyj8diiJfEg0Li0F+47KzVVALhafs/SseLpgxS04Rw9vlq5Z4Q3JPg+CpypCe1Q5h8g1GjBtWeQcYtf4STtEVRyqyFRBjwykKv1LRwqjNIDKYg/gC7SFERcNtR/oEFHGRbFrIW6z4rjRSoFfEhYCxNcXJelbJ9WU7pTCAx82Lg1CF0L3mehDsXFs+LH7HgDwkogoZ8Gn+hq8S0REq01FekhEOtLGQXJ167M+ENYdr4XdCg+318JK1y81g7lBs4r0dB0sVYfZoK29Lm57RLODx2QkEFtXaOWLG0vXdvATAG646b5u+JBA2eaK3CFqNBjIhK8JiAdcA9hIwNY45zdrm8c0qIdRQ1jKC1QralD3jyKq+Bx2AMyP4nT+TPTdx5VhFPLRcxTRNKZKlrcVdrv9PPFOOMwRsWtLQn76alsWxEvWF5i6PtEY2OK57QKqFOWwTpAlIitlurPwvq4Ed+JfF7p5cKviCIlonHB5qvTKqwXmBYwZuhtf7QAAvvHal69FMBpfVgsoxoP5E/fMA9gKnTMDcPoImKdRiVx5oD0sO21X5/MVCiPCbnnTCZHVwYumMCx76KHK08OKLP3yDG1v5G6gXmJU8YhEy3W9Nr/TNqLG+UqkVDyUVXMU/6LavI89GNUV0hU7z9j0rQdEsAHLXd70xkz3cr+m5MlMnHqje7OzdYkM9/JcOJL07w6sS/CQiS3UOWwtWAF1+akp0UbJmDeOdZldSr4oq7papny+DbCWMJry+TYK1EJSXnXARJWKkRwibN/Oy/dUu5IXa7Xj8dwD28q3idWLVsqoUjlNVWuTJ9XEr4d1REQSLKzWORdDdZLTRB1X0XJhJshAaiOzX6eGUegROpNGyawaJqxnudfiRlPBhppmlKprroO1G8Ayi3U9TtYkp+vAgAltC+s9zvOYJMBEzaVmJJ1R5EWZQpIPOtaoLowilS01D2RqMFpQes/oIl2SE6flblH5TiLJSzmCuqjzl6XV7QOYbht/ROmVqXQ+rhlWBezcgh3Vvl2Rnm505PiaGLX3TO/8ZsBmOgPfQ8UN6MomtdqyCv5Pqe4rLG24MOXNM7Hf2ma7TPwWtjZg510l/fHin/1z9zd545+FZnZ/AQAAAABJRU5ErkJggg==", "cloud-sun-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABhUlEQVR42p2UMU4zQQyFvxkCK0iTggaQCDcIN2CPQEVDQ00DBT05AkLiBhENDTfYPcJ2NBTbIFGm+H8REthHMfaGTQPCzXje2J7nN9bAb23jZgUY/jMn2jro/QS09jcgTHyzmwOQNcBoBhQVAH2NE7Go2oAa4tgcINMslRipgggL1hNwzGNyiubbGoFLv3ZuwLNgdwLlqx2ECZlUOS8ArqXP5K2lpYQQymVAkGSszCQ5PaPwcupFrHEotKLMSHlXsWfybsSaSo/YKF4AMQhFkwOhkCoIqjOpBPqSPiGo7kt1hCuSgh3aqpcpmRLvoCoVHeqdPTVQWNqRKiiUs8M3aYdaiqEZ0FfVvramQNR/3wdqoGFr1o7DNImapUtij9JUPsOeOk+X68MjAJi6Vq7Y0wOhI+H85CBJGD+c0CseYdouGFiEATJAHHQHV2yvApsmZeohMo6pyPryTdNgmEY9avbvSuCcsXfnZr3MPbcxQIcGvPmJ57QycyGpndMecLvIgfvf/gpfTD+64C4Lg1AAAAAASUVORK5CYII=", "cloud-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAAC3klEQVR42u1XPW4TQRT+ZrIkFkbCSIAigUgKeh+BPQAFBVwiTY4QH4WGAgcJSjrvEbakoHARgSNRLFIirR17H8XMzs7fm3VBFe3XJB5/fv/z3htgwIAB9xDijOhz3sv6SkTUvOuhnRMRETVpeS9Io458eWBU/m3/y55854VNyWDNSxO/rTNe3AlZqFmdC5tGnLNHDouW/vdS/Tl2T4/30slplToB8zPNL6O0MRERbXJAqJTdRGlvumSKBRHRLkqz3TtkjZOOgHPOuLETq0POuCkRNd3HCyLaRmgX7s/H7q8cD0rP1FnUg8aXXkY9qP2qqoLUPwWwsg9XAEYBbQLgo324AfAg5mjTd6Ic3YaB9NMlwqCPiajwbJMA/ri0Wlts0zLfA6ABcBqhFZ61hTr2gtlE6rSZzz95bm2ZVnFtKZ0AAU0X3/NlR8uVZw7a373K7Tsa3PKD9sJe2UkomYtrnFPNoQryZ1JUapoIw2bR8DpF604e7kcTM+NUk2rFS9MBG675mA6buQYb3F4C4j0AHBppW6Y52l1nzNPU5Cl7aWJhbmyKhhPtg7TrIcRK31iZHp7rAhCt0jo98fJeaVgCaGkZT6stWgIbdWP7aFQAE0AmotFWVKZzukPS1VorFQlapau3R2kFZIAEpaVtAdF6midp0NL+Aw2W0knfNiaBIkmj/Wi2tNEetCpZScKi9dVJ2wf4iJgWc+RPHn/J2gFSxfmUpWWtbY2evCyNAKkCyEdETQ0JYJZydWI6+beudXLSAOBxbE20hkvVLZZcfxBKhARw17XOWDLbNDXdNAkwUrbHViluh5gyK5ZeYeNrnj8Jd/GlMdZ7wxU00FnFFtpwJJWR9TgcCzTrSl0ZRl8ubdazDzkAkvzqbmHLPT5c3FjvhRV/o36mHgwd4o8xH7X9SMEvTucP9jlmQ8fctF0RL5HbR45S0Mso7S338HRwxT1jHay5R7GD6xwDBgy4b/gHyR2+w3cSS10AAAAASUVORK5CYII=", "cloud-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABMElEQVR42tWTMVICMRSGvzxQnKGhoJJxOIJHIN7ARgsrewu8ARzBht5GGxtvwB7BI2xhSUHBjDDu8lskm816A7bJ/N8kf17e+xdO63t46+q5dMj1QJK+MrCQpDqKHtgawLmi2TCUJKlMJ2bS6l6qEpC+YSI12nT04NZaJosdwDSZTEMJg8CBmTyAS66LuruifVivdUfYumu8dADMsQlgA+clmGMbQAVcgZEDW2J94iuPAI8YDdDTR8EYhqGu2Loay3t5KFwX8Ox8F5R4q3Kwxxu0plSMrMqBwGCUg5EpB4CJ8X/Qz/XWWJ610oFRmM/A1ih5SeCCIg0q9tU3o2ySkoYdr6zpgy8mq9C1S36zwMTUGPxkdb3SA7Xv1U0bS0lKBcyjPnpwIdq3ALx/ntL/+Aff8ZVF/gq77AAAAABJRU5ErkJggg==", "cloud-fog-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAADJ0lEQVR42u1YO27bQBB9S9miEBZxEQSBHUAu06lJL1Y5gd0kTW4Q30A6QAodIY0DpPMNpCP4AAGiwkBcqjBiWaY4Kbgkd3ZnlgTSOd7Chqmn+b83SwPP56kdw/44w+NV51eOiYguu1AnREREN3HUkOxZRGGzGlbmEVRGzbnpYyxqLiXnrFXYxIXtg48HtrC/WZnNqjMBIqI7//Ok+vWeP30hOzW/vE7LXm2elzk+xnIdt2WtelaIsX0GgN3b9udAHDoiIrK1N0siopUW2h0bqLUW2pzZ3gqwKW/QROwXsOReUidSPwP3sZxD6juZiDlkfrODB0gAvALw0314D2AkJpr7OZVSovvwiwEsrObYLXcdHhFtwtxXXgoGgJf+I4BTDzYC4OlQCeDIc/pSiHdG9HB+7se7l2pEVC54a7by1DOZmAq8rHn70KaQAz5DmgfDhduE64C+Nf+3bhOC4UoancitUwMggLUV+uZ8MZf6zEUskaYBS88rBiJs2sCuG1ipqYpD81QkZcKDO1C0uHydA8eLVijTUKaa86VVjSwCG9aqk0QX1G5u+Qlksvy0k1J0WsMfu5k7YDSvIVGnGNftisOyasySWI2t6hx1xlYzNkERx60sseXWe7zrcoqNDV2eN1c6CmvNRGCFZRbFnRaAqWPLuyKsrOXd1qiftaaAyow4sNN+1g56wDa9YYddl88KlvSwVgCYq4CDOtkBCarq7qW9trM4GaoJKcUl6zi1PF3FUj1q1H8qqm8w5GsA6p24XS5ZLIdKuRI7xyO9rnX9dxHiH7YwWumseePsoKnO6JmzNcaq/BpyWJyq2pW6orqDJjjvAGydCJQR4RfAsdIswy985kw2NhCujxN+y7+xsD0XI1OGZEm3wMOI7YWhIKcFgFswWNDVU34nCPaxPRvANHxBlHor3HfBAOACX9HtFMMfgmTzsw7fjCA0fyPC7n3YlT4N2hueU9QP/H34+/M/Fv6nc8JmRN1QS+3tnolpwjWzHAjTi2DXGMgwj/gm7wWDYg3/CmOZZnfah8zaVnuh4TBPL3cKjC4Y7FaJDYcuox8/PQ/5Uz5/ASMqnwW/a7WmAAAAAElFTkSuQmCC", "cloud-fog-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABVklEQVR42rWTMU7DQBBFnycJCRgJS4CEQpHcgCMQbpAG0eYGHCE5Qo6QGiGRG8RH4AgpEBWFC5AsFPtTrNdeB0oyzWieZmf+7szCoaz38j0N42gjlZMAXEvSWwA2klQ2cV+SpNcajBz4dJHBDN1ZynHdQ1rCkeT7dFQAzJVWIHanR9rWNRcA5qtyK+e187IK5+demnLnb/Q0dV0zB86qG5qvHju1FlGBHDgB63rFAqIFBpXCEmAG/foOl/ePyiFW83imAgsft1xYG7Bi0gYfTGxHMIB8P0Mk7QyBiSTMSfYBJi7agHQQjJ3MSC0EGOtoUYMumbGlWZYBqZEHbcakYMEibEqAjR8qHRVEMHwfLgH00M+/TpudktJYW/dA1fWSHSu/MpKkrRVg1UQAsvLcASqpazKIAHpTAD3/74dx655Xqw1cAXDUgLFTPKnBL3M/pPyz6EHsBw76o0Bo8tkgAAAAAElFTkSuQmCC", "cloud-drizzle-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAADo0lEQVR42u1YvW7TUBT+7CR1RZCagaKqRUpGtizsuY/QAYTExBu0bxA/AEPEzMBAB5gYmYgfIeyV2iFSkeiQoaJp6vgw3Ht9r++vB6bCHZLW/nz+z3eOA/w/D+0kjX9e4v5r9JFDIqKzGOqIiIhoGUbtkDizIGwqYRULoPpUn2UbYUFxGWnn0gsb67CtdbsjAnvVCHNSRB0gIrox76f860Xz6iO30uTCyLRbq/DzjOFNyNehCivPWem07S0AbJ6pz46z6IiISMQ+mRMRFT7TbhoFdekzLW/IXjtgk2aCxs58AfOmlkyz1PRAv+z2ITOVjJ0+9M1kWxeQAngC4Fy/eAtg1+koM32qXI5u7QctmB3NoR5uaR4RrWzfC8OFBIDh/j2AkQHbBWDwUAVgYCjdc9g7Jbp79cq0d+uKEVE1a6Zm7a76Bk1MHH0p+/ZOucAAs0PqCzszPQkLq31l/6/1JFjFldY8wYTSBIAFUxH6qD3IXHlukljqqgbMDa3oOGGTGraoYZWPVbQ2z5xNmTaN63q4uHrKgMOZIsrMpqn6nCjW6AdgO5J10uCA2uSiP4G+m35UpZRRafgtJnMERrmEBJViKNMVhvV5maWhGAvWGURtkx2bogzjCtHY7tQbfRdTipUw3V1vOnWUQloSgJWisyistAQSaRuLWcilsbg0aietDqCnRjTYqJ20bgvYqjWsF1s+OYxHL/mieXz4yVGgOf9DmyLzyuCOjqSdsVbtqex2Dkt5ZEYAcKzZ2AOOIRqAmhNQJ7o9Oe5UIRUhVweAgOVAyrjrTLvLgzmqYZcAvDuxGi59PncTndKHkk05c6Wijnf9WZLx3wQav6dgVPi75kCbQROirbKtp9s21YI5JCprWDJfKlhCWhdnPA38wYy2KguZTqob7m0BAnCAlMdqBeA5gLWEUY5zALmkKQasVdSvNepkAPZoxf0pABDJBbDQ35wAJN8Z920B4GgpZznzvYYs9JG/RZTwu2JfisBKAD/jsHonSGM8XuVxGBW4RQulp3jnZ3gV0J3P8Ehb6UvO5nUrWGjmVa1ek+2lzzh859xnANA79r9VauvedOt/q3QQl+2pk7hsGNO6tesfFk5+s6S5iQtoV28PGHYyiyxrRAA6VAbDK4jrMTqoicsPGwG5BWtufjd1ZyVNJtKlXeEDT+sAoNNNYXBO3W37ihjx/oc3INdNXnjoqS9c8W8pzbmss79HXKlr4bd/lKFfF9/+4V9B/wDYWKoOjsXb6wAAAABJRU5ErkJggg==", "cloud-drizzle-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABfklEQVR42rWTPXLUQBBG3/QKZFCAqgwBEKxPgI+w4gZOyB2Qc4TVETiCYxIInUlH0BEUEBIocBUqGOkjmJF2tFW4SFDS1a96ur/+Efyv78nXXzep7xpprhLwVpK+J6CRpPnk55IkdSvYB/AQPINb9N5anq01pM/wVFrq7DQBHNVGUITXe/VrzhrAlqwcFKz8ImsK9rhI0xjstb7chKpDAC9ih7ZkL4Jac0QwAs/BskWxAFdjEBXOALeQrz28+vBJIxQ6Dc80Yelw59q2gDuqLfhBZZ5kAeN5hCi3EQITZRpTngNMvISPAK+XiXl2M0DTYuqM1sgcQFXiwPjm6owKHCUZg9FzOpYLWmOkBFwFcEULpq5QVfROPU3Mns9cjzRdXPMb3D0Hz7sqX9cJBw8U6rcD8txtI2xijRg8MF+uTVP0ZEnLE67iWCeXChAu1QDW5uBsL4+BvEtpLvYPMWkG8Hvm6oLaJdvg4KOwkGMIrT1aZfB/A7tof17e/+tf/gcUFqMPTgEYMQAAAABJRU5ErkJggg==", "cloud-rain-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAADWklEQVR42u2YPW/TQBjH/768VXhoBkCoICUjWxb2+CN0oEJi4huQb1B/AIaImaEDXSoGRrb4I5SJBakVqlQkOmSo2jR1/DDcne+58/lsxIBU6qFt7J/vntf/PQ1wf921K7I+vMTt58ZXdoiIDpuop0RERGdhqk/qmgexfY0VSYCKqbzO2iwWXG5A7DqtxSYc21Qed1Rgz60wR1mjA0REl+5zIX+9sO8+8G8anTiZ9u+q/DxM8Drk68iEVeYs99r2BgDWz8zPjrfoiIhIxT5aEBFldaZdWgV1Wmdaaq298mBTO0ETb76Ahb3LgFnqesBv+30YuJtMvD7EbrIrNyAAPATwnd+8BrDldTRxfSp8jm6qL1awajRHPNzaPCJaVn3PHBciAI77twDGDrYFwNGhAsDQ2XTbY+8+0c3enmvvxhcjomJup2blr3pLJqaevtR9e2NcSAC3Q8ob/TlPwnGlfXX/r3gSKsUlSp1I1KYRgApmInTAXkx8ebZFTPiqAQtnV3S82LTEjkusqFMV1uYDb1MK27hujRYXjxNgZ26EclCVqfJ6a1QjDmB9rToieECtU9WfQOyXH1MpeeNquFIncwNGqUaCm2Kk0xXGYllmIhRjpTrDRtt0xwrkYS5Tje1PvdN3TZtiqUz31xuXjlytFgWwXHUWhTfNgUjbljRZKFdLmlejdquVAaypEYaN263WbYEtW2O9puFTYjJ60RHzeOejp0BT+Qc7RRaFox0dLTsTVu1Cd7vEhIzMGAB2mY09YBeqAcg+AbnQbevjzhRSFnJ1CCgsBUQiXU/YUxnMcYmdAqidic3hEstzN+KSPtJqKpVLqDreqs+Sjv860Pg9g1FW3zVP2Bk0JdoY23rctn0WzBFRXmLR4sxgEcku7gLAT36i9hPW3X2lNgLSh5xZI0w9PQew0hilbJQa8kabA7gotfcAMy8WJSpJEvuxl/HsDK2pOC0x+hTQy6xR8LtqXmrAchmtFmopZwLRpONF2oxRhmu02HSGd22wb0dpG2z9Cmjn6T12j/1LjPhwvrT/OxDWOES8kZd/hx2oplTKOKvBzvHBGDpbZ47mlCs8ujAf3n+tDciFrQt3PfWZHf8/Ws07rCctsDg437KxxzPwV7+UoV8nX/7jb0F/AybbXu2WyK+JAAAAAElFTkSuQmCC", "cloud-rain-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABZUlEQVR42rWTPU7EMBCFP8+a3xREAiQQBRT0HIFwAxoqGgp6jkCOwBGoaaCk2xxhj7AFoqJIgUQEWT8KJ9kkEoiGNKP5PJ55fnbgv76Vx8/zfu6mUsh64ECSXnpgKklhma9JkjTrwGEE7zEzuEJnVrDRzZDuYFVq50y0ALhV0YAk7j7UvOuZA1jblVPFqLqVtYjxtpWmKsYTPZzHqWUEW80Jre2eRLXmaEAFbIL5VrEAl2PQKAwAV7DWnWH34kYVJFqaZ1pgfXNDbkPAPdkQvJFZTe8CqnGFSIcVAhNpvyYdA0zswDXAfutYzSQATAtMM6MwvAPIUhwYTy73ZOBI8ZTGnOVjWacwKlLAZQBHFGCaJcqSudOcacATCgcc7wGTLODh8jWB1AOeDwxeu56et6FBNfdD8BXykafbjDwtx4D/BDUFiDLKB74CQO56t8FpHdeaHmXc+OuUsv4JTJr4sf3817/8G16Rk1sbPdzuAAAAAElFTkSuQmCC", "cloud-rain-wind-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAAEUklEQVR42u1YO44bRxB90/wtPMEyWBiGZIAKnTFxvn2EDaTEkW6gI3COsEdQokDZ3oBzBB7AgBkIsMMJCIvaHU45qK7umu6eGcaWBovlbvOxu+pV1atqAj+e/9tT9P55i5enyY+8IiL6NIV6TURE9GUctST3PI7CdgLr7AiqJP98uWaz0e1WpJ7jIGyrYZfk7Zkj9u8ezUU96QAR0Sl+3/DL7/3Vn/KHFn9Fkc6f6vz8ZPHHmK+bQCvHrM3a9h4Ann8Nv2fZpCMiIsd9sSciqodMO/US6jhkWtXb+5yB3fcDtM3GC9j3T1kpS2MP9HLeh1V8yDbrQxkHO1mAAXAH4E+9+BXATdZRG/vU5Ry9pB9MYCmbG023mEdETep7HblQAIjcfwHwJoLdAIh0qAOwjg69zdi7I/r27l1s7yXHEVH32A/NOZ/1PZm4z9Sl1O234IIF4grxC8tHHYRDUr5S/2cdhCS5jNcJ6w4tACSwwNBH9UGbi3NfxEwuG7CPTsUsC7v3sIOHdUOqosp8lS1K0zduPqDF3c8WePUYhHKVypR/PgTVKEdgS1EdM9qgnitXn0CZl5+QKe3kbvjXdeYJGFUCGT0UGwnXOKzkNDNjHDvVWU/aJhVr0I7jalfY+dBHdTd1KBpnej7ftHS0brdiBNa6yqLxQ1ugENvslIW8m53eTcNeq7AV+youyYP/06ponlztdKKMjS+ng5K9S4AZoPaxX2jFfdA8mcAzMJfEZ+8LG8EW/M+d7p5WD58Mc5FdD82mMByOahA2F7GbednZq65UOqHyeRZ6lm7Kt46vUjKkkyZbcHp5OynUieE8XgjsScFe3KvLtwowltlFDSwemF1OtTe+SWycD87qD512J4SydD6w1QUrmrjDr8bl8Q3vz1F+z+sibI7/Z+cQW3sDrOGbyiLAqOZl7nFz+UEN4BfVg+6Z6T3REdgQnYDSsbtTXWND1PJEdZAydy27IIYbAPhHKgON1IULwtKpjQH70Hqr2UJ2B78BOKtB4eDZ5aMdu/0BcENW2DUsj/x20R/4ird+0JgRUSXuzDLjIw8aKyLiPSuGXdAX/AcJAvlkmbt5Kar+Ro527szEA7WbBRohbB6mgo9po60lCFtuVYWvl17F1UCl2aUaXzPTrxXCdq7Hb5PZsZTcpVqSBVh+zjSxmN3kZgTlIup+xSawVsMGbmTM7q1mN9uIiY5C2G3ceYymrZGj14i6Sg/2BFjgHAQkfztK2M03dV9d+3hK94dyToTqagavuy0HwUqy5HbzApJl16ikbOXo+WgQjiITZdLXjWoqjUjoXcxugHkXc0HoDRi1GuMHhhijBWSb3IFMbw43Ph0HYOSDUAPNYBCwDwKCMr2MhWAdfTqa4XFoRTZcknanwblk7eOfGZqMnsCwdko7MTcl6ThWXdlRKhoDroTV0zAMp2Mm/lO7ETeoK2DX7IYK52u+29ukd8vstzGfv/tvQf8DUT16J/WiSiEAAAAASUVORK5CYII=", "cloud-rain-wind-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABvElEQVR42rWTP3LTQBSHv31e44AL70zCDAOFU9D7CCw3SEPvG3CE6Ag5QmoaUtJJR9ABKFRkGAoXKjKMhqz1o1hJlqlo2Obt++bt+7/wv87y6++bue5KqY8z8E6SHmeglKT+pK8kSaonsM3gKWsGe/TRKl5OMaQ7eCGNcRY6AtyqGsA6v96qmXwWADZ65YOyVBrTOmZ5O6amLsudvtzkqG0Gm6FCG72vc7bmGEAHvALzY8YCXIHBkGEPsIfVVMPrT5/VwVqn5pmO2Ly5fWHngHviOTgQLTEbQPe3hQjZwkWAgABTDesGsCNOjYkA798AS8u5cAXBA35wXyYoO2ArTLVRGcQEBOHAeHCFI9kjQXha2Kg2NZtEmdioMDrCkiY4Ysc1lfFM66mucSTuVHn6ynmqKEe7iD3AW3ai7FaqV3rC4AehJybPg+eQGxRlHDxV4n4Yb7dQvRN2BANc7Dxt6OkvB0B7QRUF7bhU9Va5wGxxQRvkYpqApwhyHGabm+NMFkHE5AePBoTekTzF9GTXLdSsNO063396muf+BH7tPVV/OR/hRvH8F25P/8lOGzc/6266LgBIV9/+/Zf/ASUJ0hsEQ/UCAAAAAElFTkSuQmCC", "cloud-snow-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAADf0lEQVR42u1YPW7UQBT+7P1xxCJlC4hQgrRbIlFsQ79zhBRESFTcYLlB9gAUe4Q0Keg4AfERcgAkUkSC0sWKbDa2H4Vn7Dczz2PTUECmSJTx5/c73/fGAR7Xv7Yi64+3ePjS+coxEdFlF+qEiIjoNowak16bIOzcwEoVQE2oXrd9jAXNJcTWTStswWGF93igC/vDKnOUdiZARLR1n8fVrzf27hPZafTd6bTsVed5qfA+lOusKWvVs1yM7QMA7F82PwfioSMiIl376IqIKG0LbWsdqJu20NaW7Z0AW9oNWoj9Aq5sLwmL1M2Ab8s5JK6ThZjDxG22t4EYwDMA3/jmHYADMVHl5lRKiRb+ix7Mr+aMl9uER0SZn3vqpBABcNJ/ADB3YAcAHB0qAUwdp4dCvOdE92dnbryFVCOicmO3ZiefeksmlgIvDW/vmxQU4DKk3hhveBOuPfoa/u94E7zDFdc6obTTCIAHayp0wV5UUp9tEYul04ArxysGImxZw65rWNmmKozmiUjK2A5u2KLF5ZECjjeNUCa+TNVr1ajGJAAbG9WJgwNqv9b8BCay/DQnJe+0hl96MnfAaG0gQaeYmXaFYZPqmMWhGmvVmXbGZhgbIw/jUk1sufUO77qcItOhy+eNS0eurUUBWK6ZRWGnORCZ2FRXhJU11W2N+lmrC9hyRhhs3s/asAcs6w0bdV0+K1jcw1oOYN0KGJpkBySoKp9LRdvMsslQnZBSHLLMqeZpGkp1Wqt/PZ35kBqdusNlpnNIeCbnRT3ksoayGYAF43VsdK1Srlif4wMApyzEEXBqYtf13+uEFOvGUB+bUQOjtGqd8uoAvGAzaElUVFclxZRoa+7gbC+XYRExFieVdvFxc1gln3BR3VfZpoyzOZABeAVgxy4K1wCWTPkH1ZC1L4AzUgAO+cwnUvoCmPIvJwDRV1aSk1szy1tIvNpYI79F/AbsQWIuBT5ZnrK9HMBPGTZ3CHTRKrYpu+oWkK0ppjyU4q4FZq2P+IRupxh/Ros1i7L7d4GZ1ymeACbBMcHu+9sOREXn54rTWRIfgc7SV6VAZ78gEp3lTxoua22aJzBLcGoRf2pPgRh/vPo5legsHyGPzvL0d+ksN92jc2itNn3yHYj32yCdA7C5NA9jafqoHjAlXSR69jSW7nVZD1jWz/5foLN/n6Gj14//Ifwf1m9VN5xMWX0zOQAAAABJRU5ErkJggg==", "cloud-snow-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABbklEQVR42rWSPVLcQBBG37QFMlawWwUODMH6BHAEhhuQkBOQc4TVEfYIxE5MSLY6go6gwKEDBQQqW9JHMNLsaHM66Zo3Pf3z9cBn2cnvf/fp2e2l0SfgSpL+JGAvSePhnEuSVEewCeA9nAwe0Z1VnMUa0g5OpbnOFw0AW1UTKMLrjZqYswSwOSu3Cl793NYQ/HZuTV3wN/p1H6q2AaymCW3OXoRuzTGBDvgGls0dC3AlBlOHI8Aj5HGG7w/P6qDQQTzTgKXijqUtAS/4JfiLt55kAd1xhFgvIwQm1mnM+hhg4mIJqL4ma6c1KksBxqsr3RvAtSejhZXqfATY16xUQq6mkAenhht54z9tzLFTBeyr+cm05kvcG6c7rn0e1wmbd6BQEwVaZ0DPS4y47QEbiBFtD4zncWiKhiyZcMB5tmXyUwHCTzWADA8uUSqNyAB6AVTukPWJvObHQspNFzUN9jM7AonqwZr+6CKv+UT7AHS3nGKAPN0CAAAAAElFTkSuQmCC", "cloud-lightning-150": "iVBORw0KGgoAAAANSUhEUgAAAJYAAACWAgMAAABBb5lxAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAAD0ElEQVR42u1YO1IbQRB9M3yErUAEFOXCgbiBEufaIxBAYh+CI7AHcMARCCAh4gbSEQgduMoKqDIBAYHKCCNtO9iZVXdPz65i25PY7L6dnv69fiPg//rblhN/nOLtrvOTIyKimy7URyIiood21C6FddkKu4iwqmhB9alZD5ts1rpdj9iaZWEjDlslr7dCYH+KMLtppwNERHP93tf/fJJP39tG3Q+Vadtq8POmwOc2X4frsB4SEdEyH9tXXgFm0RERUYi9mxARlbmjzUVBzXJHK8XeCwM2lgkamfkCJtJKj51Ue8DPTEQ0NT1Y6XKZmXmftz6AB3AA4Dt/+AJgz3S00D5VlqOr9MMElkZzaKTLE9Fz6vtUueAAKPffABwr2B4AxUMVgH1ldGCc94Lo9exMn3dlxYioupSpWdhVL2hibPRl7NvXtQsFkHRIfLB7yZNwn7Rv7P8FT0JSXL7hiSIYdQAS2DpCV+zDwsqzJDFvNu9EWcWWCRs3sPsGVuVYhbV5z2xKLw+3neHi6rAAji4B+GIadlvmiPt83bH9FthuZB3fOqB+l6E/gb5NP+tKWXbuhl8B0gGjMg7wVqOxYzt2wyOAIsC287C3uhW7dqsibNmOK9e7OfXqhP1/Gs6UVkift+cwBCKttzEn3kFIeVq9or3ryvAgYxLvicZ2MSCFUlcu/ZQ0bE/ThDNhB0b0PDBVzHhs9/+FYuiJqHof46X5TU6iGuaBZ1kiHsCTcbZnYIc92QHwrMVnDfMqHneZ7inlMJW8WZ9tIUtnv67FuLZjTNTMmsgW6jd1JpjYqck8CBUCTLmrOh77QICVgC+4o7MEFlv2ng+6Qg65uSEURqrma/98mDzvWFeRSt2MqZrCHvxhnHsANF1PE4863nF9YDOIKa4tkoOOaxSm31SCHTGPmBocynj0uBxl2nIs4zESqbto5KRsBCdl5rAZxDLx51Lw9eJw8uLrLyTlo6PgUY/fU2qhXCkZXYXEN+8mpKVtP7wasZnsmYr362kCrp/KplSvlDhd8fvRfVQ2K377wLd6BBTQ274I2GuJR5Pwv+qmLrmumAWjiQw4hTpbj8hQT/JWVtYBWdmjZ8C1zCR7CfU8CyO6zl6Mb29vYym6k/bJnapIb5J7wqoGTLFqDpZjVSN26N5NsWpuTVqFSY5VM0ZzU8ZwdNZtdGDqYCseFbqNKlZtSfyiezfNqhmYMx31myU+gR1Y1wdT2m+Y+OVm8Zij82xm4lOYMxrBgG1v1gg9+9cLb0vdLtiyZs0uGMHUyz61+LTJz3ujTSoc2L3+t38F/QOxEmNMmtKjAAAAAABJRU5ErkJggg==", "cloud-lightning-64": "iVBORw0KGgoAAAANSUhEUgAAAEAAAABAAgMAAADXB5lNAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAABjUlEQVR42rWTMXLUQBBFn9q7XmMFLFUuiioCcQLLN9jhBptA7CP4BrtHgBsQEDmBG0gncPkIG5jMwQYbCErSJ2jNSHJEwiRT/afn95/+PfC/1vLHn+00ziqpDxPgvSQ9TYBKkvoxXkmS9JiAwoGTRwa36KPVvEo1pC9wLoVE0QHsVA9A7rcLHRLnHsAiKxv5rjbK6nzfRWlqfC91v/WqRwdeDy+0yJ67WssYgAa4BFswCBKQ1Vh6Yw9wgxEzePv5jgvINTbP1E2uAP3e5gDfCHPgmWAtznEdgIawiIdf39yAWMeMLKxdnIn10GwA1hG44Bi1cAVwxc9kZOvt8eNHozaA7ehtqX1q5Eq1ceAWjNapa6PhHSx5BvhADSbtyd3Iqvd5OVEojDaXatjo/jvnlduZq6WSegq5JZkaJIlS7jvlKZOksNFgcxZixiHJ3Ukd+e/JcH9K45EsGcfSU1z7CCw4zK8UCnMgjt74I7p5nMXRi6QZL4BlKmKx6nHOsXpZ9SzZcjbM5K+Hf/7lfwH5vr9tl0KrrQAAAABJRU5ErkJggg==", "wind-36": "iVBORw0KGgoAAAANSUhEUgAAACQAAAAkAgMAAACcbnALAAAADFBMVEX///+qqqpVVVUAAAABM1s0AAAAqUlEQVR42pWQsQ3CMBBFn42DUChIk4YmQqKhygoegQ6K7EJGYAQXFEgskRFSQ5MR3CAhhHIUtqko4Kon/f9P9w9+n+kpUT0CaKBQbSTf2ahmVc82YNXPR2tyB6VfqyO1iEh7EK8BpKWZqdzBs9lc72n75KEjGUzuAChfISsiQ1JxKqqy+3ZvUMc9xKz9UAfmdgHKVXIvhtCDLHVj6RMVDNFWSaqpz3/87g0kwji0gIk/BAAAAABJRU5ErkJggg=="}  # icone PNG in base64, inserite da build_genera.py

def icona(nome, size):
    img = Image.open(io.BytesIO(base64.b64decode(ICONE["%s-%d" % (nome, size)]))).convert("L")
    return img

def testo_a_capo(draw, txt, font, larghezza):
    parole, righe, cur = txt.split(), [], ""
    for p in parole:
        prova = (cur + " " + p).strip()
        if draw.textlength(prova, font=font) <= larghezza: cur = prova
        else: righe.append(cur); cur = p
    if cur: righe.append(cur)
    return righe

def luna_disegno(draw, cx, cy, r, eta):
    """Disegna la fase lunare (eta 0=nuova, 0.5=piena)."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=255, outline=NERO, width=2)
    k = math.cos(2 * math.pi * eta)  # 1 nuova, -1 piena
    crescente = eta < 0.5
    for y in range(-r + 1, r):
        x = math.sqrt(r * r - y * y)
        term = x * k
        if crescente: x0, x1 = -x, term       # parte scura a sinistra
        else: x0, x1 = -term, x               # parte scura a destra
        if x1 > x0: draw.line([(cx + x0, cy + y), (cx + x1, cy + y)], fill=NERO)

def hm(t): return t.strftime("%H:%M")

def genera(meteo, mare, oggi, adesso):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    M = 20
    B = lambda s: F(s, True)

    # --- intestazione (0-104) ---
    d.text((M, 10), GIORNI[oggi.weekday()].upper(), font=B(28), fill=NERO)
    d.text((M, 44), "%d %s %d" % (oggi.day, MESI[oggi.month - 1], oggi.year), font=F(44, True, serif=True), fill=NERO)
    d.text((W - M, 16), LUOGO, font=B(28), fill=NERO, anchor="ra")
    d.rectangle([M, 102, W - M, 106], fill=NERO)

    # --- oggi (112-300) ---
    dd = meteo["daily"]
    y0 = 116
    desc, ic = WMO.get(dd["weather_code"][0], ("—", "cloud"))
    img.paste(icona(ic, 150), (M - 8, y0))
    tmax, tmin = dd["temperature_2m_max"][0], dd["temperature_2m_min"][0]
    d.text((168, y0 - 4), "%d°" % round(tmax), font=B(84), fill=NERO)
    d.text((170, y0 + 92), "min %d°" % round(tmin), font=B(28), fill=NERO)
    d.text((M, y0 + 142), desc, font=B(28), fill=NERO)
    pp = dd["precipitation_probability_max"][0] or 0; ps = dd["precipitation_sum"][0] or 0
    d.text((M, y0 + 178), "Pioggia %d%%" % pp + ("  ·  %.1f mm" % ps if ps >= 0.2 else ""), font=B(24), fill=NERO)
    vx = 390
    nome, sig = vento_nome(dd["wind_direction_10m_dominant"][0])
    vel, raff = dd["wind_speed_10m_max"][0], dd["wind_gusts_10m_max"][0]
    img.paste(icona("wind", 36), (vx, y0 + 2))
    d.text((vx + 44, y0 + 6), "VENTO", font=B(22), fill=NERO)
    d.text((vx, y0 + 46), nome, font=B(32), fill=NERO)
    d.text((vx, y0 + 88), "%s · %d km/h" % (sig, round(vel)), font=B(26), fill=NERO)
    d.text((vx, y0 + 124), "raffiche %d" % round(raff), font=F(24), fill=NERO)
    d.text((vx, y0 + 154), "forza %d" % beaufort(vel), font=F(24), fill=NERO)
    d.rectangle([M, 324, W - M, 325], fill=NERO)

    # --- prossimi 3 giorni (328-500) ---
    y1 = 334
    colw = (W - 2 * M) / 3
    for i in range(1, 4):
        g = dt.date.fromisoformat(dd["time"][i])
        x = M + (i - 1) * colw; cx = x + colw / 2
        d.text((cx, y1), GIORNI[g.weekday()][:3].upper() + " %d" % g.day, font=B(24), fill=NERO, anchor="ma")
        _, ic_i = WMO.get(dd["weather_code"][i], ("—", "cloud"))
        img.paste(icona(ic_i, 64), (int(cx - 32), y1 + 32))
        d.text((cx, y1 + 100), "%d° / %d°" % (round(dd["temperature_2m_max"][i]), round(dd["temperature_2m_min"][i])), font=B(28), fill=NERO, anchor="ma")
        _, s_i = vento_nome(dd["wind_direction_10m_dominant"][i])
        d.text((cx, y1 + 136), "%s %d km/h" % (s_i, round(dd["wind_speed_10m_max"][i])), font=F(21), fill=NERO, anchor="ma")
        d.text((cx, y1 + 162), "pioggia %d%%" % (dd["precipitation_probability_max"][i] or 0), font=F(21), fill=NERO, anchor="ma")
        if i < 3: d.rectangle([x + colw - 1, y1 + 4, x + colw, y1 + 186], fill=NERO)
    d.rectangle([M, 524, W - M, 528], fill=NERO)

    # --- mare, maree, luna (534-660) ---
    y2 = 536
    d.text((M, y2), "MARE", font=B(22), fill=NERO)
    if mare:
        onde = (mare.get("current") or {}).get("wave_height")
        if onde is None: onde = mare["daily"]["wave_height_max"][0]
        d.text((M, y2 + 28), mare_douglas(onde or 0).capitalize(), font=B(28), fill=NERO)
        d.text((M, y2 + 64), "onde %.1f m" % (onde or 0), font=B(22), fill=NERO)
        sst = (mare.get("current") or {}).get("sea_surface_temperature")
        if sst is not None: d.text((M, y2 + 92), "acqua %d°" % round(sst), font=B(22), fill=NERO)
        dom = mare["daily"]["wave_height_max"][1] if len(mare["daily"]["wave_height_max"]) > 1 else None
        if dom is not None: d.text((M, y2 + 120), "domani %s" % mare_douglas(dom), font=F(20), fill=NERO)
    mx = 226
    d.text((mx, y2), "MAREE", font=B(22), fill=NERO)
    mm = maree(mare, oggi) if mare else []
    for j, (t, tipo, liv) in enumerate(mm[:4]):
        yy = y2 + 30 + j * 30
        d.text((mx, yy), "▲ alta" if tipo == "alta" else "▼ bassa", font=B(22), fill=NERO)
        d.text((mx + 100, yy), hm(t), font=B(22), fill=NERO)
        d.text((mx + 180, yy), "%+d cm" % round(liv * 100), font=F(20), fill=NERO)
    if not mm: d.text((mx, y2 + 30), "dati non disponibili", font=F(20), fill=NERO)
    maggiori, minori, fase, illum, eta, stelle = solunari(oggi)
    lx = W - M - 48
    luna_disegno(d, lx, y2 + 40, 36, eta)
    parole = fase.split(" ", 1)
    d.text((lx, y2 + 80), parole[0], font=B(18), fill=NERO, anchor="ma")
    if len(parole) > 1: d.text((lx, y2 + 100), parole[1], font=B(18), fill=NERO, anchor="ma")
    d.text((lx, y2 + 121), "%d%%" % round(illum * 100), font=F(18), fill=NERO, anchor="ma")
    d.rectangle([M, 682, W - M, 683], fill=NERO)

    # --- pesca (696-776) ---
    y3 = 690
    d.text((M, y3), "PESCA · ORARI SOLUNARI", font=B(20), fill=NERO)
    d.text((W - M, y3), "giornata " + ["", "scarsa", "discreta", "buona", "ottima"][stelle], font=B(20), fill=NERO, anchor="ra")
    fascia = lambda a: "   ".join("%s–%s" % (hm(x), hm(y)) for x, y in a) or "—"
    d.text((M, y3 + 28), "Maggiori", font=B(23), fill=NERO)
    d.text((M + 128, y3 + 28), fascia(maggiori), font=B(23), fill=NERO)
    d.text((M, y3 + 54), "Minori", font=F(23), fill=NERO)
    d.text((M + 128, y3 + 54), fascia(minori), font=F(23), fill=NERO)
    alba = dt.datetime.fromisoformat(dd["sunrise"][0]); tram = dt.datetime.fromisoformat(dd["sunset"][0])
    # 776-800 lasciati liberi per la batteria scritta dal Kindle
    d.text((M, 774), "alba %s · tramonto %s · agg. %s" % (hm(alba), hm(tram), hm(adesso)), font=F(18), fill=NERO)
    return img


def main():
    demo = "--demo" in sys.argv
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "dashboard.png"
    adesso = dt.datetime.now(TZ)
    oggi = adesso.date()
    if demo: meteo, mare = dati_demo(oggi)
    else: meteo, mare = dati_meteo(), dati_mare()
    img = genera(meteo, mare, oggi, adesso)
    img.save(out, optimize=True)
    print("Creato", out)

if __name__ == "__main__":
    main()
