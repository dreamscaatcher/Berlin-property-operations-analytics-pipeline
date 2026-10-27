#!/usr/bin/env python3
"""
Berlin Property Operations Analytics -- SYNTHETIC DATA GENERATOR (33k-unit scale variant)
=========================================================================================
Copy of data_generation/generate_data.py scaled to 33,000 units across 680 properties
(roughly the size of a large Berlin Hausverwaltung). Same SEED, same draw logic, same
storylines; the planted DQ issues are scaled by 33,000 / 2,428. NOT real Optima figures.

Every record produced by this script is FICTITIOUS. No real properties,
tenants, contractors or company data are used. Distributions are rough,
plausible assumptions for a German residential/commercial portfolio.

Seeded (SEED below) -> fully reproducible. Writes CSVs to ../data/raw/.
Run:  python3 data_generation/generate_data.py
"""
import os, json
from datetime import date, datetime, timedelta
import numpy as np
import pandas as pd

SEED = 20261017
rng = np.random.default_rng(SEED)
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "raw")
os.makedirs(OUT, exist_ok=True)

START = date(2024, 1, 1)
SNAP = date(2026, 9, 30)  # data snapshot / "today" in the sample
WARMUP = [date(2023, m, 1) for m in range(1, 13)]
MONTHS = [date(y, m, 1) for y in (2024, 2025, 2026) for m in range(1, 13) if date(y, m, 1) <= SNAP]

def month_end(d):
    n = d.replace(day=28) + timedelta(days=4)
    return n - timedelta(days=n.day)

def third_working_day(d):
    # §556b BGB: rent due by the 3rd working day (public holidays ignored here)
    c, x = 0, d
    while True:
        if x.weekday() < 5:
            c += 1
            if c == 3:
                return x
        x += timedelta(days=1)

def rdate(a, b):
    return a + timedelta(days=int(rng.integers(0, (b - a).days + 1)))

# ---------------------------------------------------------------- properties
#            city,      district,                  n, rent_mult, demand(>1 = slower re-letting)
LOCS_BASE = [("Berlin", "Mitte", 4, 1.20, 1.00),
        ("Berlin", "Friedrichshain-Kreuzberg", 5, 1.18, 1.00),
        ("Berlin", "Pankow", 5, 1.08, 1.00),
        ("Berlin", "Charlottenburg-Wilmersdorf", 4, 1.15, 1.00),
        ("Berlin", "Neukölln", 4, 1.00, 1.00),
        ("Berlin", "Tempelhof-Schöneberg", 3, 1.05, 1.00),
        ("Berlin", "Steglitz-Zehlendorf", 3, 1.02, 1.00),
        ("Berlin", "Lichtenberg", 3, 0.92, 1.05),
        ("Berlin", "Treptow-Köpenick", 3, 0.93, 1.05),
        ("Berlin", "Spandau", 2, 0.85, 1.15),
        ("Berlin", "Marzahn-Hellersdorf", 2, 0.80, 1.20),
        ("Berlin", "Reinickendorf", 2, 0.85, 1.15),
        ("Potsdam", "Potsdam", 3, 1.00, 1.10),
        ("Hamburg", "Hamburg", 2, 1.15, 1.00),
        ("Leipzig", "Leipzig", 3, 0.68, 1.60),
        ("Dresden", "Dresden", 2, 0.66, 1.60)]
# ---- 33k scale: 50 -> 680 properties (x13.6), same district mix; exactly 33,000 units
N_PROPS, N_UNITS = 680, 33000
SCALE = N_UNITS / 2428          # used to scale the planted DQ issues
_raw = [n * N_PROPS / 50 for _, _, n, _, _ in LOCS_BASE]
_ns = [int(x) for x in _raw]
for i in sorted(range(len(_raw)), key=lambda i: -(_raw[i] - _ns[i]))[:N_PROPS - sum(_ns)]:
    _ns[i] += 1
LOCS = [(c, d, k, m, dm) for (c, d, _, m, dm), k in zip(LOCS_BASE, _ns)]
CENTRAL = {"Mitte", "Friedrichshain-Kreuzberg", "Pankow", "Charlottenburg-Wilmersdorf", "Hamburg"}
TYPES = ["Altbau residential", "Neubau residential", "WEG condominium", "Commercial/retail", "Office"]
TCODE = dict(zip(TYPES, ["ALT", "NEU", "WEG", "RET", "OFF"]))
RESIDENTIAL = {"ALT", "NEU", "WEG"}
def type_weights(city, district):
    if district == "Marzahn-Hellersdorf":
        return [0, .8, 0, .2, 0]
    if district in CENTRAL:
        return [.40, .12, .18, .10, .20]
    if city == "Berlin":
        return [.25, .40, .20, .08, .07]
    return [.45, .25, .15, .05, .10]

BASE_RENT = {"ALT": 11.0, "NEU": 13.5, "WEG": 12.5, "RET": 22.0, "OFF": 24.0}  # EUR/m2/month Kaltmiete
GROWTH = {"ALT": .03, "NEU": .03, "WEG": .03, "RET": .0, "OFF": .01}         # market growth p.a.
UNITS_RANGE = {"ALT": (30, 100), "NEU": (40, 110), "WEG": (15, 60), "RET": (4, 20), "OFF": (6, 30)}
OCC_START = {"ALT": .97, "NEU": .97, "WEG": .97, "RET": .90, "OFF": .87}
P_MOVE = {"ALT": .0065, "NEU": .0075, "WEG": .006, "RET": .008, "OFF": .010}  # monthly move-out probability
TICKET_RATE = {"ALT": .13, "NEU": .09, "WEG": .10, "RET": .15, "OFF": .12}     # tickets / unit / month (base)

words = ["Linden", "Kastanien", "Ahorn", "Eichen", "Birken", "Ulmen", "Lerchen", "Sonnen", "Rosen", "Flieder",
         "Tannen", "Buchen", "Erlen", "Weiden", "Pappel", "Eschen", "Holunder", "Mohn", "Lavendel", "Kiefern",
         "Akazien", "Platanen", "Schwalben", "Kranich"]
suffixes = ["hof", "haus", "carré", "höfe"]
names = [w + s + ("" if k == 1 else f" {k}") for k in range(1, 9) for w in words for s in suffixes]  # 768 unique names
rng.shuffle(names)

props = []
pid = 0
for city, district, n, mult, demand in LOCS:
    for _ in range(n):
        pid += 1
        t = TYPES[rng.choice(5, p=type_weights(city, district))]
        c = TCODE[t]
        yb = {"ALT": (1885, 1935), "NEU": (1965, 2022), "WEG": (1900, 2018), "RET": (1960, 2016), "OFF": (1970, 2021)}[c]
        props.append(dict(
            property_id=f"P{pid:03d}", property_name=names[pid - 1], city=city, district=district,
            property_type=t, property_type_code=c, year_built=int(rng.integers(*yb)),
            n_units_planned=int(rng.integers(*UNITS_RANGE[c])),
            has_lift=bool(rng.random() < {"ALT": .3, "NEU": .85, "WEG": .5, "RET": .5, "OFF": 1}[c]),
            has_garden=bool(rng.random() < .55),
            heating_source=str(rng.choice(["Fernwärme", "Erdgas", "Wärmepumpe"], p=[.5, .4, .1] if c != "NEU" else [.55, .25, .2])),
            management_since=str(date(int(rng.integers(2008, 2023)), int(rng.integers(1, 13)), 1)),
            rent_mult=mult, demand=demand))
# scale the planned unit counts so the portfolio has exactly N_UNITS units (deterministic, no extra draws)
_tot = sum(p["n_units_planned"] for p in props)
for p in props:
    p["n_units_planned"] = max(UNITS_RANGE[p["property_type_code"]][0], int(round(p["n_units_planned"] * N_UNITS / _tot)))
_diff = N_UNITS - sum(p["n_units_planned"] for p in props)
_i = 0
while _diff != 0:
    p = props[_i % len(props)]; lo, hi = UNITS_RANGE[p["property_type_code"]]
    if _diff > 0 and p["n_units_planned"] < hi:
        p["n_units_planned"] += 1; _diff -= 1
    elif _diff < 0 and p["n_units_planned"] > lo:
        p["n_units_planned"] -= 1; _diff += 1
    _i += 1
P = pd.DataFrame(props)

# ---------------------------------------------------------------- units
units = []
uid = 0
for p in props:
    c = p["property_type_code"]
    for i in range(p["n_units_planned"]):
        uid += 1
        if c in RESIDENTIAL:
            area = float(np.clip(rng.lognormal(np.log(66), .3), 25, 180)); utype = "Wohnung"
            floors = 6 if c == "ALT" else 9
            nk = rng.normal(2.75, .2)
        elif c == "RET":
            area = float(rng.uniform(45, 450)); utype = "Laden/Gewerbe"; floors = 1; nk = rng.normal(2.8, .25)
        else:
            area = float(rng.uniform(90, 900)); utype = "Büro"; floors = 8; nk = rng.normal(2.8, .25)
        units.append(dict(unit_id=f"U{uid:05d}", property_id=p["property_id"], unit_no=f"{i + 1:03d}",
                          unit_type=utype, floor=int(rng.integers(0, floors)),
                          rooms=int(np.clip(round(area / 27), 1, 6)) if utype == "Wohnung" else None,
                          area_m2=round(area, 1), has_balcony=bool(utype == "Wohnung" and rng.random() < .55),
                          _nk_rate=round(float(nk), 2), _c=c, _mult=p["rent_mult"], _demand=p["demand"],
                          _district=p["district"]))
U = pd.DataFrame(units)

def market_m2(c, mult, d):
    yrs = (d - START).days / 365.25
    return BASE_RENT[c] * mult * (1 + GROWTH[c]) ** yrs

# ---------------------------------------------------------------- tenancies, rent roll, payments, vacancies
tenants, rent_rows, pay_rows, vac_rows = [], [], [], []
tid = rrid = payid = vid = 0
CHANNELS_LET = ["Immobilienportal", "Eigene Website", "Interessentenliste", "Makler", "Empfehlung"]

def new_tenant(u, lease_start, rent_m2):
    global tid
    tid += 1
    c = u["_c"]
    prof = rng.choice(["reliable", "occasional", "at_risk"], p=[.78, .17, .05])
    t = dict(tenant_id=f"T{tid:06d}", tenant_label=f"Mieter T{tid:06d}", unit_id=u["unit_id"],
             tenant_type="Privat" if c in RESIDENTIAL else "Gewerbe",
             lease_start=lease_start, lease_end=None,
             payment_method=str(rng.choice(["Dauerauftrag", "SEPA-Lastschrift", "Überweisung"], p=[.45, .35, .20])),
             _profile=prof, _rent_m2=rent_m2,
             _raise_month=(MONTHS[int(rng.integers(3, len(MONTHS)))] if (c in RESIDENTIAL and rng.random() < .25) else None))
    tenants.append(t)
    return t

def add_payment(rr, pdate, amount, method):
    global payid
    if pdate > SNAP or amount <= 0:
        return
    payid += 1
    pay_rows.append(dict(payment_id=f"PM{payid:07d}", rent_roll_id=rr, payment_date=pdate,
                         amount=round(amount, 2), payment_method=method,
                         bank_ref=f"BR{pdate.strftime('%Y%m')}{payid:07d}"))

def pay_line(t, c, m, rr, due_date, total):
    prof = t["_profile"]
    pl, pp, pn = {"reliable": (.02, .003, .001), "occasional": (.12, .04, .012), "at_risk": (.20, .15, .08)}[prof]
    recover = .6
    if c == "RET" and m >= date(2025, 7, 1):  # pattern: retail arrears creep from mid-2025
        k = (m.year - 2025) * 12 + m.month - 6
        pp += min(.010 * k, .15) * (.5 if prof == "reliable" else 1.5)
        pn += min(.006 * k, .08) * (.5 if prof == "reliable" else 1.5)
        recover = .4
    if m.month == 1:  # post-Christmas late payments
        pl += .02
    r = rng.random()
    meth = t["payment_method"]
    ontime = due_date if meth == "SEPA-Lastschrift" else due_date - timedelta(days=int(rng.integers(0, 5)))
    if r < pn:
        if rng.random() < recover * .8:
            add_payment(rr, due_date + timedelta(days=int(rng.integers(30, 200))), total, meth)
    elif r < pn + pp:
        f = rng.uniform(.3, .9)
        add_payment(rr, ontime, total * f, meth)
        if rng.random() < recover:
            add_payment(rr, due_date + timedelta(days=int(rng.integers(30, 150))), total * (1 - f), meth)
    elif r < pn + pp + pl:
        add_payment(rr, due_date + timedelta(days=int(rng.integers(5, 45))), total, meth)
    else:
        add_payment(rr, ontime, total, meth)

for _, u in U.iterrows():
    c = u["_c"]; area = u["area_m2"]
    cur = None; vacant_until = None; cur_vac = None
    if rng.random() < OCC_START[c]:
        back = min(rng.exponential(8 if c in RESIDENTIAL else 5), 28)
        ls = START - timedelta(days=int(back * 365.25) + 1)
        rent_m2 = max(market_m2(c, u["_mult"], ls) * (1 + .025) ** back, BASE_RENT[c] * u["_mult"] * .55) * rng.normal(1, .07)
        cur = new_tenant(u, ls, rent_m2)
        # 2023 warm-up: rent lines + payments for the sitting tenant only, so that the
        # reporting window starts with realistic opening receivables (no move-outs simulated in 2023)
        for m in WARMUP:
            if ls <= m + timedelta(days=14):
                kalt = round(area * rent_m2, 2); nk = round(area * u["_nk_rate"], 2)
                rrid += 1
                due = third_working_day(m)
                rent_rows.append(dict(rent_roll_id=rrid, period_month=m, due_date=due, unit_id=u["unit_id"],
                                      tenant_id=cur["tenant_id"], kaltmiete_due=kalt, nk_prepayment_due=nk,
                                      total_due=round(kalt + nk, 2)))
                pay_line(cur, c, m, rrid, due, kalt + nk)
    else:
        # vacant at start: previous tenant moved out in late 2023
        mo = rdate(date(2023, 8, 31), date(2023, 12, 31))
        back = min(rng.exponential(7), 25)
        ls = mo - timedelta(days=int(back * 365.25) + 1)
        prev = new_tenant(u, ls, market_m2(c, u["_mult"], ls) * rng.normal(1, .07))
        prev["lease_end"] = mo
        cur_vac = dict(unit_id=u["unit_id"], old_tenant_id=prev["tenant_id"], move_out_date=mo, old_rent_m2=prev["_rent_m2"])
        vacant_until = mo
    pending = None  # (relet_date, vac dict)

    def start_vacancy(move_out, old):
        global vid
        if c in RESIDENTIAL:
            med = 32 * u["_demand"] ** 2.2
            renov = c == "ALT" and rng.random() < .25 or c != "ALT" and rng.random() < .08
            days = rng.lognormal(np.log(med), .55) + (rng.integers(60, 150) if renov else 0)
        else:
            renov = rng.random() < .2
            days = rng.lognormal(np.log(130 if c == "RET" else 150), .7) + (rng.integers(30, 90) if renov else 0)
        days = max(int(days), 7)
        relet = move_out + timedelta(days=days)
        vid += 1
        v = dict(vacancy_id=f"V{vid:05d}", unit_id=u["unit_id"], property_id=u["property_id"],
                 old_tenant_id=old["tenant_id"], new_tenant_id=None, move_out_date=move_out, relet_date=None,
                 days_vacant=None, old_rent_m2=round(old["_rent_m2"], 2), new_rent_m2=None,
                 renovation_before_relet=bool(renov), marketing_channel=None, applications_received=None)
        vac_rows.append(v)
        return relet, v, renov

    if cur_vac is not None:
        old = tenants[-1]  # the previous tenant was appended just above (same object as the list scan in the original)
        pending = start_vacancy(cur_vac["move_out_date"], old)

    for m in MONTHS:
        # re-letting
        if cur is None and pending is not None and pending[0] <= month_end(m):
            relet, v, renov = pending
            if relet <= SNAP:
                nm = market_m2(c, u["_mult"], relet) * rng.normal(1, .06) * (1.08 if renov else 1)
                cur = new_tenant(u, relet, nm)
                v.update(new_tenant_id=cur["tenant_id"], relet_date=relet, days_vacant=(relet - v["move_out_date"]).days,
                         new_rent_m2=round(nm, 2),
                         marketing_channel=str(rng.choice(CHANNELS_LET, p=[.55, .15, .15, .08, .07] if c in RESIDENTIAL else [.35, .1, .05, .4, .1])),
                         applications_received=int(max(1, rng.lognormal(np.log(80 / u["_demand"] ** 3 if c in RESIDENTIAL else 4), .6))))
                pending = None
        if cur is None or cur["lease_start"] > m + timedelta(days=14):
            continue
        # rent line (Sollstellung)
        rent_m2 = cur["_rent_m2"]
        if c in ("RET", "OFF"):  # Indexmiete: +2.5% each January after lease start
            rent_m2 *= 1.025 ** sum(1 for y in (2024, 2025, 2026) if date(y, 1, 1) <= m and cur["lease_start"] < date(y, 1, 1))
        if cur["_raise_month"] is not None and m >= cur["_raise_month"]:
            rent_m2 *= 1.07  # Mieterhöhung (within Kappungsgrenze)
        nk_rate = u["_nk_rate"] * (1.04 if m >= date(2025, 1, 1) else 1.0)  # prepayment adjustment after 2023 statements
        kalt = round(area * rent_m2, 2); nk = round(area * nk_rate, 2)
        rrid += 1
        due = third_working_day(m)
        rent_rows.append(dict(rent_roll_id=rrid, period_month=m, due_date=due, unit_id=u["unit_id"],
                              tenant_id=cur["tenant_id"], kaltmiete_due=kalt, nk_prepayment_due=nk,
                              total_due=round(kalt + nk, 2)))
        pay_line(cur, c, m, rrid, due, kalt + nk)
        # move-out at month end?
        months_in = (m.year - cur["lease_start"].year) * 12 + m.month - cur["lease_start"].month
        if months_in >= 6 and m < date(2026, 9, 1) and rng.random() < P_MOVE[c]:
            mo = month_end(m)
            cur["lease_end"] = mo
            pending = start_vacancy(mo, cur)
            cur = None

T = pd.DataFrame(tenants)
RR = pd.DataFrame(rent_rows)
PAY = pd.DataFrame(pay_rows)
V = pd.DataFrame(vac_rows)
print(f"properties={len(P)} units={len(U)} tenants={len(T)} rent_lines={len(RR)} payments={len(PAY)} vacancies={len(V)}")

# ---------------------------------------------------------------- contractors & maintenance tickets
CONTRACTORS = [("C01", "Kontraktor 01 – Heizung/Sanitär", "HLS"), ("C02", "Kontraktor 02 – Heizung/Sanitär", "HLS"),
               ("C03", "Kontraktor 03 – Heizung/Sanitär", "HLS"), ("C04", "Kontraktor 04 – Sanitär", "HLS"),
               ("C05", "Kontraktor 05 – Elektro", "Elektro"), ("C06", "Kontraktor 06 – Elektro", "Elektro"),
               ("C07", "Kontraktor 07 – Aufzugsservice", "Aufzug"), ("C08", "Kontraktor 08 – Aufzugsservice", "Aufzug"),
               ("C09", "Kontraktor 09 – Tischler/Schlüsseldienst", "Tischler"), ("C10", "Kontraktor 10 – Fenster/Türen", "Tischler"),
               ("C11", "Kontraktor 11 – Dach/Fassade", "Bau"), ("C12", "Kontraktor 12 – Bautenschutz", "Bau"),
               ("C13", "Kontraktor 13 – Garten/Außenanlagen", "Außen"), ("C14", "Kontraktor 14 – Hausmeisterdienst", "Hausmeister")]
CTR = pd.DataFrame(CONTRACTORS, columns=["contractor_id", "contractor_name", "trade"])
CTR["is_synthetic"] = True
CAT = {  # category: (base weight, contractor pool, median cost EUR)
    "Heizung": (.14, ["C01", "C02", "C03"], 380), "Sanitär": (.22, ["C01", "C02", "C03", "C04"], 290),
    "Elektro": (.12, ["C05", "C06"], 210), "Aufzug": (.05, ["C07", "C08"], 650),
    "Fenster/Türen": (.10, ["C09", "C10"], 330), "Schimmel/Feuchtigkeit": (.06, ["C12"], 900),
    "Schließanlage": (.07, ["C09"], 160), "Dach/Fassade": (.04, ["C11", "C12"], 1800),
    "Außenanlagen": (.05, ["C13"], 420), "Sonstiges": (.15, ["C14"], 150)}
HEAT_SEASON = {1: 3.0, 2: 2.8, 3: 2.0, 4: 1.0, 5: .4, 6: .3, 7: .3, 8: .3, 9: .7, 10: 1.6, 11: 2.3, 12: 3.0}
PRIO_BY_CAT = {"Heizung": [.12, .45, .38, .05], "Sanitär": [.08, .30, .52, .10], "Aufzug": [.10, .55, .32, .03],
               "Elektro": [.05, .25, .55, .15], "Schimmel/Feuchtigkeit": [0, .25, .60, .15]}
PRIOS = ["P1 Notfall", "P2 Hoch", "P3 Normal", "P4 Niedrig"]
SLA = {"P1 Notfall": (2, 24), "P2 Hoch": (24, 72), "P3 Normal": (72, 336), "P4 Niedrig": (120, 720)}
PRI = pd.DataFrame([dict(priority=p, sla_response_hours=SLA[p][0], sla_resolution_hours=SLA[p][1]) for p in PRIOS])
CFACT = {c: rng.uniform(.75, 1.1) for c, _, _ in CONTRACTORS}
def contractor_factor(cid, d):
    if cid == "C03":  # pattern: one HLS contractor degrades from Q4 2025 (capacity problem)
        k = max(0, (d.year - 2025) * 12 + d.month - 9)
        return 1.1 + min(k, 10) * .12
    return CFACT[cid]
weather = {m: rng.normal(1, .08) for m in MONTHS}
units_by_prop = U.groupby("property_id")["unit_id"].apply(list).to_dict()
tickets = []
mtid = 0
for p in props:
    c = p["property_type_code"]; ulist = units_by_prop[p["property_id"]]
    for m in MONTHS:
        w = {k: v[0] for k, v in CAT.items()}
        if not p["has_lift"]:
            w["Aufzug"] = 0
        w["Heizung"] *= HEAT_SEASON[m.month] * weather[m]
        w["Schimmel/Feuchtigkeit"] *= 1.6 if m.month in (11, 12, 1, 2, 3) else .8
        tot = sum(w.values())
        cats, probs = list(w), np.array(list(w.values())) / tot
        lam = len(ulist) * TICKET_RATE[c] * tot + .6 + len(ulist) * .01
        n = rng.poisson(lam)
        portal_share = .40 + .22 * MONTHS.index(m) / (len(MONTHS) - 1)
        for _ in range(n):
            mtid += 1
            cat = cats[rng.choice(len(cats), p=probs)]
            common = rng.random() < .15
            prio = PRIOS[rng.choice(4, p=PRIO_BY_CAT.get(cat, [.02, .15, .58, .25]))]
            day = int(rng.integers(1, month_end(m).day + 1))
            created = datetime(m.year, m.month, day, int(rng.integers(0, 24)), int(rng.integers(0, 60)))
            if created.date() > SNAP:
                continue
            ch = "Notfall-Hotline" if prio == "P1 Notfall" and rng.random() < .6 else \
                str(rng.choice(["Mieterportal", "Telefon", "E-Mail", "Hausmeister"],
                               p=[portal_share, (1 - portal_share) * .45, (1 - portal_share) * .35, (1 - portal_share) * .20]))
            cid = str(rng.choice(CAT[cat][1]))
            f = contractor_factor(cid, created.date())
            load = 1.3 if cat in ("Heizung", "Sanitär") and m.month in (12, 1, 2) else 1.0
            resp_h = rng.lognormal(np.log(SLA[prio][0] * .4 * f * load), .6)
            res_h = resp_h + rng.lognormal(np.log(SLA[prio][1] * .4 * f * load), .7)
            assigned = (created + timedelta(hours=float(resp_h))).replace(microsecond=0)
            resolved = (created + timedelta(hours=float(res_h))).replace(microsecond=0)
            status = "Erledigt"; cost = round(float(rng.lognormal(np.log(CAT[cat][2]), .7) * (1.35 if prio == "P1 Notfall" else 1)), 2)
            r = rng.random()
            if r < .02:
                status, resolved, cost = "Storniert", None, 0.0
            elif r < .032:
                status, resolved, cost = "Wartet auf Material/Freigabe", None, None
            if resolved is not None and resolved.date() > SNAP:
                status, resolved, cost = "In Bearbeitung", None, None
            if assigned.date() > SNAP:
                status, assigned, cid = "Neu", None, None
            tickets.append(dict(ticket_id=f"MT{mtid:06d}", property_id=p["property_id"],
                                unit_id=None if common else str(rng.choice(ulist)), is_common_area=bool(common),
                                category=cat, priority=prio, channel=ch, contractor_id=cid,
                                created_at=created, assigned_at=assigned, resolved_at=resolved, status=status,
                                cost_eur=cost))
MT = pd.DataFrame(tickets)
print(f"tickets={len(MT)}")

# ---------------------------------------------------------------- service-charge statements (Nebenkostenabrechnung)
COST_TYPES = {  # EUR / m2 / month by year; allocation key
    "Heizung/Warmwasser": ({2023: 1.65, 2024: 1.20, 2025: 1.10}, "Verbrauch (HeizkostenV)"),
    "Wasser/Abwasser": ({2023: .37, 2024: .38, 2025: .40}, "Verbrauch"),
    "Müllabfuhr": ({2023: .17, 2024: .18, 2025: .19}, "Wohnfläche"),
    "Gebäudereinigung": ({2023: .19, 2024: .20, 2025: .21}, "Wohnfläche"),
    "Versicherung": ({2023: .22, 2024: .24, 2025: .26}, "Wohnfläche"),
    "Grundsteuer": ({2023: .22, 2024: .22, 2025: .22}, "Wohnfläche"),
    "Hausmeister": ({2023: .24, 2024: .25, 2025: .26}, "Wohnfläche"),
    "Allgemeinstrom": ({2023: .07, 2024: .06, 2025: .06}, "Wohnfläche"),
    "Aufzug": ({2023: .15, 2024: .15, 2025: .16}, "Wohnfläche"),
    "Gartenpflege": ({2023: .10, 2024: .10, 2025: .11}, "Wohnfläche")}
pfac = {}
for p in props:
    c = p["property_type_code"]
    heat = {"ALT": 1.15, "NEU": .85, "WEG": 1.0, "RET": 1.0, "OFF": .95}[c] * rng.normal(1, .08)
    gst25 = rng.uniform(.7, 1.6)  # Grundsteuer reform effective 2025: property-specific change (assumed)
    pfac[p["property_id"]] = dict(heat=heat, gst25=gst25, gen=rng.normal(1, .07), lift=p["has_lift"], garden=p["has_garden"])
# months billed per (unit, tenant, year) and prepayments from rent roll
RR["year"] = pd.to_datetime(RR["period_month"]).dt.year
agg = RR.groupby(["unit_id", "tenant_id", "year"]).agg(months=("rent_roll_id", "count"), prepaid=("nk_prepayment_due", "sum")).reset_index()
# 2023 (before data window): tenants whose lease covered (part of) 2023, assume 12 months / partial
rows23 = []
uinfo = U.set_index("unit_id")
UREC = uinfo[["property_id", "area_m2", "_nk_rate"]].to_dict("index")
for t in tenants:
    ls, le = t["lease_start"], t["lease_end"]
    if ls >= date(2024, 1, 1) or (le is not None and le < date(2023, 1, 1)):
        continue
    s = max(ls, date(2023, 1, 1)); e = min(le or date(2023, 12, 31), date(2023, 12, 31))
    mths = max(1, round((e - s).days / 30.4))
    rows23.append(dict(unit_id=t["unit_id"], tenant_id=t["tenant_id"], year=2023, months=min(mths, 12),
                       prepaid=round(UREC[t["unit_id"]]["area_m2"] * UREC[t["unit_id"]]["_nk_rate"] * min(mths, 12), 2)))
agg = pd.concat([pd.DataFrame(rows23), agg[agg.year.between(2024, 2025)]], ignore_index=True)
late_props = {2023: set(rng.choice(P.property_id, round(3 * N_PROPS / 50), replace=False)), 2024: set(rng.choice(P.property_id, round(2 * N_PROPS / 50), replace=False)), 2025: set()}
issue_base = {}
for p in props:
    for y in (2023, 2024, 2025):
        pe = date(y, 12, 31)
        issue_base[(p["property_id"], y)] = pe + timedelta(days=int(rng.integers(375, 440) if p["property_id"] in late_props[y] else rng.integers(150, 320)))
stmts, lines = [], []
sid = 0
for r in agg.itertuples():
    u = UREC[r.unit_id]; pf = pfac[u["property_id"]]; area = u["area_m2"]
    sid += 1
    st_id = f"NK{r.year}-{sid:06d}"
    total = 0.0
    for ct, (rates, key) in COST_TYPES.items():
        if ct == "Aufzug" and not pf["lift"]: continue
        if ct == "Gartenpflege" and not pf["garden"]: continue
        rate = rates[r.year] * pf["gen"]
        if ct == "Heizung/Warmwasser": rate = rates[r.year] * pf["heat"] * rng.normal(1, .22)
        elif ct == "Wasser/Abwasser": rate *= rng.normal(1, .25)
        elif ct == "Grundsteuer" and r.year == 2025: rate *= pf["gst25"]
        amt = round(max(rate, 0) * area * r.months, 2)
        total += amt
        lines.append(dict(statement_id=st_id, cost_type=ct, allocation_key=key, actual_cost=amt))
    issued = issue_base[(u["property_id"], r.year)]
    if rng.random() < .02:
        issued += timedelta(days=int(rng.integers(60, 160)))  # individual rework / correction
    status = "Versendet" if issued <= SNAP else "In Erstellung"
    stmts.append(dict(statement_id=st_id, unit_id=r.unit_id, tenant_id=r.tenant_id, property_id=u["property_id"],
                      period_year=int(r.year), period_start=date(int(r.year), 1, 1), period_end=date(int(r.year), 12, 31),
                      months_billed=int(r.months), prepayments_total=round(r.prepaid, 2), actual_costs_total=round(total, 2),
                      balance_eur=round(total - r.prepaid, 2), legal_deadline=date(int(r.year) + 1, 12, 31),
                      issued_date=issued if issued <= SNAP else None, status=status))
SC = pd.DataFrame(stmts); SCL = pd.DataFrame(lines)
print(f"statements={len(SC)} lines={len(SCL)}")

# ---------------------------------------------------------------- energy (per building, monthly)
HDD = {1: .17, 2: .15, 3: .12, 4: .08, 5: .04, 6: .01, 7: .005, 8: .005, 9: .03, 10: .08, 11: .13, 12: .16}
SPEC = {"ALT": 150, "NEU": 95, "WEG": 130, "RET": 120, "OFF": 110}  # kWh/m2/yr heating (assumed)
parea = U.groupby("property_id")["area_m2"].sum().to_dict()
en = []
for p in props:
    c = p["property_type_code"]; nu = len(units_by_prop[p["property_id"]])
    for m in MONTHS:
        eff = {2024: 1.0, 2025: .97, 2026: .95}[m.year]
        en.append(dict(property_id=p["property_id"], period_month=m,
                       heating_kwh=round(parea[p["property_id"]] * SPEC[c] * HDD[m.month] / sum(HDD.values()) * weather[m] * eff * rng.normal(1, .05)),
                       common_electricity_kwh=round(nu * rng.normal(25, 4) * (1.15 if m.month in (11, 12, 1, 2) else 1) + (350 if p["has_lift"] else 0))))
EN = pd.DataFrame(en)

# ---------------------------------------------------------------- dim_date
dd = pd.DataFrame({"date": pd.date_range("2023-01-01", "2026-12-31", freq="D")})
dd["year"] = dd.date.dt.year; dd["quarter"] = dd.date.dt.quarter; dd["month"] = dd.date.dt.month
dd["month_start"] = dd.date.dt.to_period("M").dt.to_timestamp()
dd["year_month"] = dd.date.dt.strftime("%Y-%m")
MN_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]
dd["month_name_de"] = dd.month.map(lambda x: MN_DE[x - 1]); dd["month_name_en"] = dd.date.dt.strftime("%B")
dd["iso_week"] = dd.date.dt.isocalendar().week.astype(int); dd["weekday"] = dd.date.dt.dayofweek + 1
dd["is_weekend"] = dd.weekday >= 6
dd["is_heating_season"] = dd.month.isin([10, 11, 12, 1, 2, 3, 4])
dd["is_month_end"] = dd.date.dt.is_month_end
dd["date"] = dd.date.dt.date; dd["month_start"] = dd.month_start.dt.date

# ================================================================ DELIBERATE DATA-QUALITY ISSUES
dq = {}
# DQ1: duplicate ticket rows (double import from portal sync)
dup = MT.sample(round(30 * SCALE), random_state=SEED)
MT = pd.concat([MT, dup], ignore_index=True)
dq["DQ1_duplicate_ticket_rows"] = sorted(dup.ticket_id.tolist())
# DQ2: resolved_at before created_at (timestamp entry / timezone error)
cand = MT[(MT.status == "Erledigt")].drop_duplicates("ticket_id").sample(round(14 * SCALE), random_state=SEED + 1).index
MT.loc[cand, "resolved_at"] = MT.loc[cand, "created_at"] - pd.to_timedelta(rng.integers(2, 72, len(cand)), unit="h")
dq["DQ2_resolved_before_created"] = sorted(MT.loc[cand, "ticket_id"].tolist())
# DQ3: missing / zero living area in unit master data
bad_u = U[U._c.isin(list(RESIDENTIAL))].sample(round(7 * SCALE), random_state=SEED + 2).index
_k0 = round(4 * SCALE)
U.loc[bad_u[:_k0], "area_m2"] = 0.0
U.loc[bad_u[_k0:], "area_m2"] = np.nan
dq["DQ3_units_zero_or_null_area"] = sorted(U.loc[bad_u, "unit_id"].tolist())
# DQ4: orphan rent-roll lines (unit IDs from a migrated portfolio not yet in unit master)
orph = []
N_MIG = round(2 * SCALE)  # migrated units missing from master, 12 months each
for i in range(N_MIG * 12):
    m = MONTHS[-12 + (i % 12)]
    rrid += 1
    kalt = round(rng.uniform(450, 900), 2); nk = round(rng.uniform(150, 250), 2)
    orph.append(dict(rent_roll_id=rrid, period_month=m, due_date=third_working_day(m), unit_id=f"UMIG{(i // 12) + 1:03d}",
                     tenant_id=f"TMIG{(i // 12) + 1:03d}", kaltmiete_due=kalt, nk_prepayment_due=nk, total_due=round(kalt + nk, 2), year=m.year))
RR = pd.concat([RR, pd.DataFrame(orph)], ignore_index=True)
dq["DQ4_orphan_rent_roll_unit_ids"] = [f"UMIG{k:03d}" for k in range(1, N_MIG + 1)]
# DQ5: duplicated bank-statement import (same bank_ref, new payment_id)
dp = PAY[PAY.payment_date >= date(2026, 3, 1)].sample(round(12 * SCALE), random_state=SEED + 3).copy()
dp["payment_id"] = [f"PM{payid + i + 1:07d}" for i in range(len(dp))]
PAY = pd.concat([PAY, dp], ignore_index=True)
dq["DQ5_duplicate_bank_refs"] = sorted(dp.bank_ref.tolist())
# DQ6: service-charge statements with issued_date inside the billing period (impossible)
bad_s = SC[(SC.period_year == 2024) & SC.issued_date.notna()].sample(round(5 * SCALE), random_state=SEED + 4).index
SC.loc[bad_s, "issued_date"] = [date(2024, int(rng.integers(3, 11)), int(rng.integers(1, 28))) for _ in bad_s]
dq["DQ6_statement_issued_before_period_end"] = sorted(SC.loc[bad_s, "statement_id"].tolist())

# ================================================================ write
def w(df, name):
    df = df[[c for c in df.columns if not c.startswith("_")]]
    df.to_csv(os.path.join(OUT, name + ".csv"), index=False)
    print(f"  {name}.csv  {len(df):>7} rows")
P["is_synthetic"] = True
V["days_vacant"] = V["days_vacant"].astype("Int64"); V["applications_received"] = V["applications_received"].astype("Int64")
U["rooms"] = U["rooms"].astype("Int64")
w(P.drop(columns=["n_units_planned", "rent_mult", "demand"]), "dim_property")
w(U, "dim_unit")
w(T, "dim_tenant")
w(dd, "dim_date")
w(CTR, "dim_contractor")
w(PRI, "dim_priority")
w(RR.drop(columns=["year"]), "fact_rent_roll")
w(PAY, "fact_payment")
w(MT, "fact_maintenance_ticket")
w(V, "fact_vacancy_reletting")
w(SC, "fact_service_charge_statement")
w(SCL, "fact_service_charge_cost")
w(EN, "fact_energy_monthly")
with open(os.path.join(OUT, "_dq_injection_log.json"), "w") as f:
    json.dump(dict(seed=SEED, scale="33k units / 680 properties (synthetic)", note="Deliberately injected data-quality issues (for QA demo), scaled x%.2f." % SCALE, issues=dq), f, indent=2, default=str)
print("done; snapshot date", SNAP)
