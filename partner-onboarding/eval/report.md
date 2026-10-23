# Partner updates: evaluation

Current version (v3). Only final_test_3 was blind for v3; see README for the blind result of each version. Each message is a partner's free-text update. Correct = the final proposal (after the code checks) has exactly the expected checklist changes and customer count. Model: qwen2.5:3b, temperature 0.

## tuning: 15/15 correct

Wrongly proposed as done: **0**. Clauses decided as 'no change' (with the reason in the last column): 8. Average 0.1s per message.

| Message | Result | Expected | Proposed | No change, and why |
|---|---|---|---|---|
| Hallo Frau Becker, kurzes Update: Die Betriebshaftpflicht ist seit gestern abgeschlossen,  | ✅ | haftpflicht=erledigt | haftpflicht=erledigt | haftpflicht: keine Vergangenheit, kein Zustand: keine Änderung |
| Gewerbe ist angemeldet und das Geschäftskonto bei der Sparkasse ist auch eröffnet. | ✅ | gewerbe=erledigt, konto=erledigt | gewerbe=erledigt, konto=erledigt |  |
| Den Antrag auf Anerkennung haben wir noch nicht abgeschickt, uns fehlt noch ein Formular v | ✅ | antrag=blockiert | antrag=blockiert | antrag: Plan, Frage oder 'noch nicht': keine Änderung |
| Mit dem Büro klappt es leider nicht, der Vermieter hat kurzfristig abgesagt. | ✅ | buero=blockiert | buero=blockiert |  |
| Wir haben zwei Alltagshelferinnen eingestellt, beide fangen am Ersten an. | ✅ | helfer=erledigt | helfer=erledigt |  |
| Die Startschulung machen wir im Dezember, der Termin im Oktober war schon voll. | ✅ | keine | keine | schulung: keine Vergangenheit, kein Zustand: keine Änderung |
| Seit Montag haben wir unseren ersten Kunden, er bekommt zweimal pro Woche Einkaufshilfe. | ✅ | erster_kunde=erledigt | erster_kunde=erledigt (Kunden: 1 → 1) |  |
| Wir betreuen jetzt 11 Kunden - das Ziel ist geschafft! | ✅ | erster_kunde=erledigt, zehn_kunden=erledigt | erster_kunde=erledigt, zehn_kunden=erledigt (Kunden: 11 → 11) |  |
| Hallo, wie lange dauert eigentlich die Bearbeitung des Antrags bei der Behörde? Danke! | ✅ | keine | keine | antrag: Plan, Frage oder 'noch nicht': keine Änderung |
| Der Bescheid ist da: Wir sind offiziell als Angebot zur Unterstützung im Alltag anerkannt! | ✅ | antrag=erledigt, zulassung=erledigt | zulassung=erledigt, antrag=erledigt |  |
| Flyer sind gedruckt und verteilt, die Anzeige im Wochenblatt erscheint am Samstag. | ✅ | marketing=erledigt | marketing=erledigt | marketing: keine Vergangenheit, kein Zustand: keine Änderung |
| Die Führungszeugnisse für beide Helfer liegen vor, die Schulung haben sie auch hinter sich | ✅ | fuehrungszeugnis=erledigt | fuehrungszeugnis=erledigt |  |
| Hi, quick update from Essen: we signed the office lease today, 32 m² near the station. | ✅ | buero=erledigt | buero=erledigt |  |
| Die Versicherung zickt noch rum, die wollen erst die Handelsregistereintragung sehen. Die  | ✅ | haftpflicht=blockiert | haftpflicht=blockiert | gewerbe: Plan, Frage oder 'noch nicht': keine Änderung; gewerbe: keine Vergangenheit, kein Zustand: keine Änderung |
| Wir haben im Moment 6 Kunden, Tendenz steigend. | ✅ | erster_kunde=erledigt | erster_kunde=erledigt (Kunden: 6 → 6) | erster_kunde: KI: keine Änderung (Der Punkt ist nebenbei erwähnt, da der erste Kundeneinsatz noch in der Zukunft liegt) |

## final_test: 15/15 correct

Wrongly proposed as done: **0**. Clauses decided as 'no change' (with the reason in the last column): 10. Average 0.2s per message.

| Message | Result | Expected | Proposed | No change, and why |
|---|---|---|---|---|
| Guten Morgen! Die Haftpflichtversicherung haben wir abgeschlossen, Deckungssumme 3 Mio. Au | ✅ | haftpflicht=erledigt, konto=erledigt | haftpflicht=erledigt, konto=erledigt |  |
| Das Büro ist angemietet, die Schlüsselübergabe war heute. Die Helfersuche läuft noch, bish | ✅ | buero=erledigt, helfer=blockiert | buero=erledigt, helfer=blockiert | helfer: keine Vergangenheit, kein Zustand: keine Änderung |
| Ich habe den Login für die Partnersoftware immer noch nicht bekommen, können Sie da nachha | ✅ | software=blockiert | software=blockiert |  |
| Wir werden den Antrag nächste Woche einreichen. | ✅ | keine | keine | antrag: Plan, Frage oder 'noch nicht': keine Änderung |
| Antrag ist raus! Haben ihn gestern persönlich beim Amt abgegeben. | ✅ | antrag=erledigt | antrag=erledigt |  |
| Die Startschulung in Düsseldorf war super, vielen Dank an das ganze Team! | ✅ | schulung=erledigt | schulung=erledigt |  |
| Leider ist eine der beiden neuen Helferinnen wieder abgesprungen, wir suchen Ersatz. | ✅ | helfer=blockiert | helfer=blockiert |  |
| Wir haben unseren ersten Einsatz für nächsten Dienstag geplant. | ✅ | keine | keine | erster_kunde: Plan, Frage oder 'noch nicht': keine Änderung |
| Stand heute: 4 Kunden aktiv, 2 weitere im Erstgespräch. | ✅ | erster_kunde=erledigt | erster_kunde=erledigt (Kunden: 4 → 4) |  |
| Die Zulassung ist noch nicht da, die Behörde hat Unterlagen nachgefordert. | ✅ | zulassung=blockiert | zulassung=blockiert | zulassung: Plan, Frage oder 'noch nicht': keine Änderung |
| Hello, the business registration is done and our bank account is open. Insurance is next o | ✅ | gewerbe=erledigt, konto=erledigt | gewerbe=erledigt, konto=erledigt | haftpflicht: Plan, Frage oder 'noch nicht': keine Änderung |
| Kurze Frage: Muss das Führungszeugnis erweitert sein oder reicht das normale? | ✅ | keine | keine | fuehrungszeugnis: Plan, Frage oder 'noch nicht': keine Änderung |
| Das Abschlussgespräch können wir gern am 15. machen. Bis dahin haben wir hoffentlich 10 Ku | ✅ | keine | keine | abschluss: KI: keine Änderung (Abschlussgespräch am 15. bereits geplant); erster_kunde: Plan, Frage oder 'noch nicht': keine Änderung |
| Unsere Website ist online und die ersten Plakate hängen. Leider hat die Druckerei die Flye | ✅ | marketing=erledigt | marketing=erledigt |  |
| Notartermin war heute, die GmbH ist gegründet und das Gewerbe angemeldet. Die Versicherung | ✅ | gewerbe=erledigt | gewerbe=erledigt | gewerbe: KI: keine Änderung (Gewerbeangaben sind nicht Teil des Notartermins); haftpflicht: Plan, Frage oder 'noch nicht': keine Änderung |

## final_test_2: 8/10 correct

Wrongly proposed as done: **1**. Clauses decided as 'no change' (with the reason in the last column): 3. Average 0.1s per message.

| Message | Result | Expected | Proposed | No change, and why |
|---|---|---|---|---|
| Unser Geschäftskonto ist seit letzter Woche aktiv. | ✅ | konto=erledigt | konto=erledigt |  |
| Die Police für die Betriebshaftpflicht ist heute gekommen. | ✅ | haftpflicht=erledigt | haftpflicht=erledigt |  |
| Wir warten immer noch auf die Vertragsvorlagen in der Software, ohne die können wir keine  | ✅ | vorlagen=blockiert | vorlagen=blockiert |  |
| Die Anzeige in der Lokalzeitung ist erschienen und wir hatten schon drei Anrufe. | ✅ | marketing=erledigt | marketing=erledigt |  |
| Bewerbungsgespräche laufen, nächste Woche stellen wir die zweite Helferin ein. | ✅ | keine | keine | helfer: keine Vergangenheit, kein Zustand: keine Änderung; helfer: Plan, Frage oder 'noch nicht': keine Änderung |
| Die Startschulung wurde leider abgesagt, weil zu wenige Teilnehmer angemeldet waren. | ✅ | schulung=blockiert | schulung=blockiert |  |
| Unser Antrag liegt seit sechs Wochen beim Landesamt, wir haben noch nichts gehört. | ❌ | keine | antrag=erledigt |  |
| Wir haben 8 Kunden und zwei Alltagshelfer im Einsatz. | ❌ | erster_kunde=erledigt, helfer=erledigt | erster_kunde=erledigt (Kunden: 8 → 8) |  |
| The office is ready. Our insurance broker cancelled, so we have no liability insurance yet | ✅ | buero=erledigt, haftpflicht=blockiert | buero=erledigt, haftpflicht=blockiert | haftpflicht: Plan, Frage oder 'noch nicht': keine Änderung |
| Danke für das nette Telefonat gestern! | ✅ | keine | keine |  |

## final_test_3: 8/10 correct

Wrongly proposed as done: **0**. Clauses decided as 'no change' (with the reason in the last column): 5. Average 0.2s per message.

| Message | Result | Expected | Proposed | No change, and why |
|---|---|---|---|---|
| Die Gewerbeanmeldung ist durch, das Konto bei der Commerzbank dauert noch ein paar Tage. | ✅ | gewerbe=erledigt | gewerbe=erledigt | konto: Plan, Frage oder 'noch nicht': keine Änderung |
| Leider hat die Versicherung unseren Antrag auf Haftpflicht abgelehnt. | ✅ | haftpflicht=blockiert | haftpflicht=blockiert |  |
| Wir sind seit heute offiziell zugelassen! | ✅ | zulassung=erledigt, antrag=erledigt | zulassung=erledigt, antrag=erledigt |  |
| Unsere erste Kundin betreuen wir seit Mittwoch. | ❌ | erster_kunde=erledigt | erster_kunde=erledigt (Kunden: 1 → None) |  |
| Ich konnte an der Startschulung nicht teilnehmen, weil ich krank war. | ❌ | schulung=blockiert | keine | schulung: Plan, Frage oder 'noch nicht': keine Änderung |
| Flyer kommen nächste Woche aus der Druckerei. | ✅ | keine | keine | marketing: Plan, Frage oder 'noch nicht': keine Änderung |
| We now look after 10 clients! | ✅ | erster_kunde=erledigt, zehn_kunden=erledigt | erster_kunde=erledigt, zehn_kunden=erledigt (Kunden: 10 → 10) | erster_kunde: keine Vergangenheit, kein Zustand: keine Änderung |
| Der Mietvertrag fürs Büro ist unterschrieben, Einzug ist am Ersten. | ✅ | buero=erledigt | buero=erledigt |  |
| Haben Sie eine Vorlage für den Kundenvertrag? | ✅ | keine | keine | vorlagen: Plan, Frage oder 'noch nicht': keine Änderung |
| Beide Helferinnen haben ihr erweitertes Führungszeugnis abgegeben. | ✅ | fuehrungszeugnis=erledigt | fuehrungszeugnis=erledigt |  |
