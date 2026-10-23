"""Generate fictional partner figures for 55 franchise locations (all numbers invented).

A few patterns are planted on purpose so the analytics assistant has something real to find:
- partners who founded with a friend open a second location sooner,
- three locations lose customers in the last months,
- one location runs short of cash,
- one location grows unusually fast.
"""
import random
import sqlite3
from datetime import date
from pathlib import Path

random.seed(42)
DB = Path(__file__).parent / "partners.db"
LAST_MONTH = date(2026, 9, 1)  # latest complete month
MONTHS = 24

CITIES = [
    ("Düsseldorf-Nord", "NRW"), ("Düsseldorf-Süd", "NRW"), ("Köln-West", "NRW"), ("Köln-Ost", "NRW"),
    ("Essen", "NRW"), ("Dortmund", "NRW"), ("Bochum", "NRW"), ("Duisburg", "NRW"), ("Wuppertal", "NRW"),
    ("Münster", "NRW"), ("Bielefeld", "NRW"), ("Bonn", "NRW"), ("Mönchengladbach", "NRW"), ("Krefeld", "NRW"),
    ("Neuss", "NRW"), ("Meerbusch", "NRW"), ("Aachen", "NRW"), ("Hagen", "NRW"), ("Solingen", "NRW"),
    ("Oberhausen", "NRW"), ("Gelsenkirchen", "NRW"), ("Mülheim", "NRW"), ("Leverkusen", "NRW"),
    ("Paderborn", "NRW"), ("Siegen", "NRW"),
    ("München-Ost", "Bayern"), ("München-West", "Bayern"), ("Nürnberg-Nord", "Bayern"), ("Ingolstadt", "Bayern"),
    ("Erding", "Bayern"), ("Bad Aibling", "Bayern"), ("Landsberg am Lech", "Bayern"), ("Türkheim", "Bayern"),
    ("Stuttgart-Süd/West", "Baden-Württemberg"), ("Karlsruhe", "Baden-Württemberg"),
    ("Freiburg", "Baden-Württemberg"), ("Breisgau-Kaiserstuhl", "Baden-Württemberg"),
    ("Chemnitz", "Sachsen"), ("Bautzen", "Sachsen"), ("Görlitz", "Sachsen"), ("Niesky", "Sachsen"),
    ("Werdau", "Sachsen"),
    ("Kiel", "Schleswig-Holstein"), ("Flensburg", "Schleswig-Holstein"), ("Eckernförde", "Schleswig-Holstein"),
    ("Friedberg", "Hessen"), ("Friedrichsdorf", "Hessen"),
    ("Berlin", "Berlin"), ("Bremen", "Bremen"), ("Potsdam", "Brandenburg"), ("Gera", "Thüringen"),
    ("Hamburg-Nord", "Hamburg"), ("Hannover", "Niedersachsen"), ("Osnabrück", "Niedersachsen"),
    ("Mainz", "Rheinland-Pfalz"),
]
DECLINING = {"Krefeld", "Hagen", "Werdau"}
CASH_SHORT = "Oberhausen"
FAST_GROWER = "Freiburg"


def add_months(d, n):
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def months_between(a, b):
    return (b.year - a.year) * 12 + b.month - a.month


def main():
    DB.unlink(missing_ok=True)
    con = sqlite3.connect(DB)
    con.executescript("""
    CREATE TABLE partners (
        location TEXT PRIMARY KEY, state TEXT, opened TEXT, founder_type TEXT,
        second_location_opened TEXT, start_capital_eur INTEGER);
    CREATE TABLE monthly (
        location TEXT, month TEXT, customers INTEGER, new_customers INTEGER, enquiries INTEGER,
        hours INTEGER, revenue_eur INTEGER, plan_revenue_eur INTEGER, costs_eur INTEGER,
        staff INTEGER, cash_eur INTEGER, PRIMARY KEY (location, month));
    """)
    first_month = add_months(LAST_MONTH, -(MONTHS - 1))

    for i, (city, state) in enumerate(CITIES):
        # Older locations first, newest opened in 2026.
        opened = add_months(date(2021, 6, 1), int(i * 62 / len(CITIES)) + random.randint(0, 2))
        opened = min(opened, add_months(LAST_MONTH, -3))
        founder = random.choices(["solo", "friends", "couple"], [0.6, 0.16, 0.24])[0]
        if city == FAST_GROWER:
            founder = "friends"
        ramp = random.uniform(0.85, 1.15) * (1.25 if founder == "friends" else 1.0)
        if city == FAST_GROWER:
            ramp *= 1.6
        ceiling = random.randint(140, 260) * (1.15 if founder == "friends" else 1.0)

        # Second location: friends teams expand after ~18 months, others after ~32, and fewer of them do.
        age = months_between(opened, LAST_MONTH)
        p_second = 0.85 if founder == "friends" else 0.3
        wait = int(random.gauss(18, 3)) if founder == "friends" else int(random.gauss(32, 5))
        second = add_months(opened, wait) if (random.random() < p_second and wait <= age) else None

        capital = random.choice([45000, 50000, 55000, 60000])
        con.execute("INSERT INTO partners VALUES (?,?,?,?,?,?)",
                    (city, state, opened.isoformat()[:7], founder,
                     second.isoformat()[:7] if second else None, capital))

        cash = capital * 0.6
        customers = 0
        for k in range(age + 1):
            month = add_months(opened, k)
            # Logistic growth towards the ceiling.
            target = ceiling / (1 + 2.718 ** (-(k - 14 / ramp) * 0.22 * ramp))
            months_left = months_between(month, LAST_MONTH)
            if city in DECLINING and months_left < 5:
                target *= 0.92 ** (5 - months_left)
            prev = customers
            customers = max(3, int(target + random.gauss(0, 3)))
            new_customers = max(0, customers - prev + int(customers * 0.04))
            enquiries = int(new_customers * random.uniform(2.2, 3.2)) + random.randint(2, 6)
            hours = int(customers * random.uniform(9, 11))
            revenue = int(hours * 38.5)
            plan = int(ceiling / (1 + 2.718 ** (-(k - 13) * 0.22)) * 10 * 38.5)
            staff = max(2, round(hours / 85))
            costs = int(staff * 2650 + 2200 + revenue * 0.06)
            if city == CASH_SHORT and months_left < 4:
                costs = int(costs * 1.35)  # new office + hires before revenue followed
            profit = revenue - costs
            # Owners take most of the profit out, so cash stays around one to two months of costs.
            cash += profit - (0.85 * profit if profit > 0 and cash > costs * 1.5 else 0)
            if month >= first_month:
                con.execute("INSERT INTO monthly VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (city, month.isoformat()[:7], customers, new_customers, enquiries, hours,
                             revenue, plan, costs, staff, int(cash)))
    con.commit()
    n_p = con.execute("SELECT COUNT(*) FROM partners").fetchone()[0]
    n_m = con.execute("SELECT COUNT(*) FROM monthly").fetchone()[0]
    print(f"{n_p} locations, {n_m} monthly rows -> {DB}")
    con.close()


if __name__ == "__main__":
    main()
