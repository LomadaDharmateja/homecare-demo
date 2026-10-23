"""The 90-day onboarding checklist, taken from the (fictional) partner handbook, chapter 'Onboarding'.

gate=True: must be done before the first customer visit (handbook 'Checkliste vor dem ersten Kundeneinsatz').
words: terms that must appear in the partner's sentence for an update to count for this task (code check).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    id: str
    phase: int
    title: str
    due_day: int
    owner: str
    gate: bool
    words: tuple


TASKS = [
    Task("software", 1, "Zugang zur Partnersoftware eingerichtet", 3, "Zentrale (IT)", False,
         ("software", "login", "zugang", "passwort", "password")),
    Task("gewerbe", 1, "Gewerbe angemeldet, GmbH/UG eingetragen", 21, "Partner", False,
         ("gewerbe", "gmbh", "ug", "handelsregister", "notar", "business registration", "registered", "company")),
    Task("konto", 1, "Geschäftskonto eröffnet", 21, "Partner", False,
         ("konto", "bank", "sparkasse", "volksbank", "account")),
    Task("haftpflicht", 1, "Betriebshaftpflicht abgeschlossen (mind. 3 Mio. €)", 30, "Partner", True,
         ("haftpflicht", "versicherung", "police", "insurance", "versichert")),
    Task("schulung", 1, "Fünftägige Startschulung in Düsseldorf besucht", 45, "Partner + Zentrale", False,
         ("startschulung", "schulung in düsseldorf", "training", "düsseldorf")),
    Task("antrag", 2, "Antrag auf Anerkennung/Zulassung gestellt", 35, "Partner", False,
         ("antrag", "eingereicht", "application", "applied")),
    Task("zulassung", 2, "Anerkennung/Zulassung liegt schriftlich vor", 80, "Behörde", True,
         ("zulassung", "anerkennung", "anerkannt", "bescheid", "genehmig", "approval", "approved", "zugelassen")),
    Task("buero", 2, "Büro angemietet (20-40 m²)", 50, "Partner", False,
         ("büro", "buero", "räume", "mietvertrag", "vermieter", "office", "lease", "schlüssel")),
    Task("helfer", 2, "Erste zwei Alltagshelfer eingestellt", 60, "Partner", False,
         ("helfer", "eingestellt", "mitarbeiter", "bewerb", "personal", "hired", "staff", "carer", "helper")),
    Task("fuehrungszeugnis", 2, "Führungszeugnis und Schulung der Helfer erledigt", 70, "Partner", True,
         ("führungszeugnis", "fuehrungszeugnis", "background check", "criminal record")),
    Task("vorlagen", 2, "Kundenvertragsvorlagen in der Partnersoftware hinterlegt", 60, "Zentrale", True,
         ("vorlage", "vertragsvorlage", "kundenvertrag", "template")),
    Task("marketing", 3, "Lokales Marketing gestartet", 65, "Partner", False,
         ("marketing", "flyer", "anzeige", "plakat", "website", "^werbe", "zeitung", "advert", "ads")),
    Task("erster_kunde", 3, "Erster Kundeneinsatz", 75, "Partner", False,
         ("kunde", "kundin", "einsatz", "customer", "client")),
    Task("zehn_kunden", 3, "10 aktive Kunden erreicht", 90, "Partner", False, ("kunden", "customers", "clients")),
    Task("abschluss", 3, "Abschlussgespräch Tag 90 (Businessplan vs. Ist)", 90, "Partnermanagement", False,
         ("abschlussgespräch", "abschlussgespraech", "final meeting")),
]
BY_ID = {t.id: t for t in TASKS}
GATE = [t.id for t in TASKS if t.gate]
PHASES = {1: "Gründung (Tag 1-30)", 2: "Zulassung und Aufbau (Tag 31-60)", 3: "Start der Kundenbetreuung (Tag 61-90)"}
TARGET_CUSTOMERS = 10
PERMIT_WEEKS = (4, 8)  # handbook: the authority usually needs 4 to 8 weeks
