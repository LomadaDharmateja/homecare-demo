# n8n version: evaluation

The 50 partner messages from eval/updates.json, sent through the live n8n workflow F2 (dry run: nothing saved). Model qwen2.5:3b through n8n's Ollama + Basic LLM Chain nodes.

**All: 47/50 correct. Wrongly proposed as done: 0.**

## tuning: 15/15 correct

| Message | Result | Expected | Proposed | Time |
|---|---|---|---|---|
| Hallo Frau Becker, kurzes Update: Die Betriebshaftpflicht ist seit gestern abges | ✅ | haftpflicht=erledigt | haftpflicht=erledigt | 2.2s |
| Gewerbe ist angemeldet und das Geschäftskonto bei der Sparkasse ist auch eröffne | ✅ | gewerbe=erledigt, konto=erledigt | gewerbe=erledigt, konto=erledigt | 2.1s |
| Den Antrag auf Anerkennung haben wir noch nicht abgeschickt, uns fehlt noch ein  | ✅ | antrag=blockiert | antrag=blockiert | 2.1s |
| Mit dem Büro klappt es leider nicht, der Vermieter hat kurzfristig abgesagt. | ✅ | buero=blockiert | buero=blockiert | 2.1s |
| Wir haben zwei Alltagshelferinnen eingestellt, beide fangen am Ersten an. | ✅ | helfer=erledigt | helfer=erledigt | 2.1s |
| Die Startschulung machen wir im Dezember, der Termin im Oktober war schon voll. | ✅ | keine | keine | 2.1s |
| Seit Montag haben wir unseren ersten Kunden, er bekommt zweimal pro Woche Einkau | ✅ | erster_kunde=erledigt | erster_kunde=erledigt | 3.1s |
| Wir betreuen jetzt 11 Kunden - das Ziel ist geschafft! | ✅ | erster_kunde=erledigt, zehn_kunden=erledigt | erster_kunde=erledigt, zehn_kunden=erledigt | 2.9s |
| Hallo, wie lange dauert eigentlich die Bearbeitung des Antrags bei der Behörde?  | ✅ | keine | keine | 2.1s |
| Der Bescheid ist da: Wir sind offiziell als Angebot zur Unterstützung im Alltag  | ✅ | antrag=erledigt, zulassung=erledigt | zulassung=erledigt, antrag=erledigt | 2.1s |
| Flyer sind gedruckt und verteilt, die Anzeige im Wochenblatt erscheint am Samsta | ✅ | marketing=erledigt | marketing=erledigt | 2.1s |
| Die Führungszeugnisse für beide Helfer liegen vor, die Schulung haben sie auch h | ✅ | fuehrungszeugnis=erledigt | fuehrungszeugnis=erledigt | 2.2s |
| Hi, quick update from Essen: we signed the office lease today, 32 m² near the st | ✅ | buero=erledigt | buero=erledigt | 2.1s |
| Die Versicherung zickt noch rum, die wollen erst die Handelsregistereintragung s | ✅ | haftpflicht=blockiert | haftpflicht=blockiert | 2.1s |
| Wir haben im Moment 6 Kunden, Tendenz steigend. | ✅ | erster_kunde=erledigt | erster_kunde=erledigt | 3.2s |

## final_test: 15/15 correct

| Message | Result | Expected | Proposed | Time |
|---|---|---|---|---|
| Guten Morgen! Die Haftpflichtversicherung haben wir abgeschlossen, Deckungssumme | ✅ | haftpflicht=erledigt, konto=erledigt | haftpflicht=erledigt, konto=erledigt | 2.1s |
| Das Büro ist angemietet, die Schlüsselübergabe war heute. Die Helfersuche läuft  | ✅ | buero=erledigt, helfer=blockiert | buero=erledigt, helfer=blockiert | 3.1s |
| Ich habe den Login für die Partnersoftware immer noch nicht bekommen, können Sie | ✅ | software=blockiert | software=blockiert | 2.1s |
| Wir werden den Antrag nächste Woche einreichen. | ✅ | keine | keine | 2.1s |
| Antrag ist raus! Haben ihn gestern persönlich beim Amt abgegeben. | ✅ | antrag=erledigt | antrag=erledigt | 2.1s |
| Die Startschulung in Düsseldorf war super, vielen Dank an das ganze Team! | ✅ | schulung=erledigt | schulung=erledigt | 3.1s |
| Leider ist eine der beiden neuen Helferinnen wieder abgesprungen, wir suchen Ers | ✅ | helfer=blockiert | helfer=blockiert | 2.1s |
| Wir haben unseren ersten Einsatz für nächsten Dienstag geplant. | ✅ | keine | keine | 2.1s |
| Stand heute: 4 Kunden aktiv, 2 weitere im Erstgespräch. | ✅ | erster_kunde=erledigt | erster_kunde=erledigt | 2.1s |
| Die Zulassung ist noch nicht da, die Behörde hat Unterlagen nachgefordert. | ✅ | zulassung=blockiert | zulassung=blockiert | 2.2s |
| Hello, the business registration is done and our bank account is open. Insurance | ✅ | gewerbe=erledigt, konto=erledigt | gewerbe=erledigt, konto=erledigt | 2.2s |
| Kurze Frage: Muss das Führungszeugnis erweitert sein oder reicht das normale? | ✅ | keine | keine | 2.1s |
| Das Abschlussgespräch können wir gern am 15. machen. Bis dahin haben wir hoffent | ✅ | keine | keine | 3.2s |
| Unsere Website ist online und die ersten Plakate hängen. Leider hat die Druckere | ✅ | marketing=erledigt | marketing=erledigt | 2.2s |
| Notartermin war heute, die GmbH ist gegründet und das Gewerbe angemeldet. Die Ve | ✅ | gewerbe=erledigt | gewerbe=erledigt | 3.0s |

## final_test_2: 9/10 correct

| Message | Result | Expected | Proposed | Time |
|---|---|---|---|---|
| Unser Geschäftskonto ist seit letzter Woche aktiv. | ✅ | konto=erledigt | konto=erledigt | 2.1s |
| Die Police für die Betriebshaftpflicht ist heute gekommen. | ✅ | haftpflicht=erledigt | haftpflicht=erledigt | 2.1s |
| Wir warten immer noch auf die Vertragsvorlagen in der Software, ohne die können  | ✅ | vorlagen=blockiert | vorlagen=blockiert | 2.1s |
| Die Anzeige in der Lokalzeitung ist erschienen und wir hatten schon drei Anrufe. | ✅ | marketing=erledigt | marketing=erledigt | 2.1s |
| Bewerbungsgespräche laufen, nächste Woche stellen wir die zweite Helferin ein. | ✅ | keine | keine | 2.1s |
| Die Startschulung wurde leider abgesagt, weil zu wenige Teilnehmer angemeldet wa | ✅ | schulung=blockiert | schulung=blockiert | 2.1s |
| Unser Antrag liegt seit sechs Wochen beim Landesamt, wir haben noch nichts gehör | ✅ | keine | keine | 3.1s |
| Wir haben 8 Kunden und zwei Alltagshelfer im Einsatz. | ❌ | erster_kunde=erledigt, helfer=erledigt | erster_kunde=erledigt | 3.1s |
| The office is ready. Our insurance broker cancelled, so we have no liability ins | ✅ | buero=erledigt, haftpflicht=blockiert | buero=erledigt, haftpflicht=blockiert | 2.1s |
| Danke für das nette Telefonat gestern! | ✅ | keine | keine | 2.1s |

## final_test_3: 8/10 correct

| Message | Result | Expected | Proposed | Time |
|---|---|---|---|---|
| Die Gewerbeanmeldung ist durch, das Konto bei der Commerzbank dauert noch ein pa | ✅ | gewerbe=erledigt | gewerbe=erledigt | 3.1s |
| Leider hat die Versicherung unseren Antrag auf Haftpflicht abgelehnt. | ✅ | haftpflicht=blockiert | haftpflicht=blockiert | 2.1s |
| Wir sind seit heute offiziell zugelassen! | ✅ | zulassung=erledigt, antrag=erledigt | zulassung=erledigt, antrag=erledigt | 2.1s |
| Unsere erste Kundin betreuen wir seit Mittwoch. | ❌ | erster_kunde=erledigt | erster_kunde=erledigt | 3.1s |
| Ich konnte an der Startschulung nicht teilnehmen, weil ich krank war. | ❌ | schulung=blockiert | keine | 2.1s |
| Flyer kommen nächste Woche aus der Druckerei. | ✅ | keine | keine | 2.1s |
| We now look after 10 clients! | ✅ | erster_kunde=erledigt, zehn_kunden=erledigt | erster_kunde=erledigt, zehn_kunden=erledigt | 2.1s |
| Der Mietvertrag fürs Büro ist unterschrieben, Einzug ist am Ersten. | ✅ | buero=erledigt | buero=erledigt | 3.1s |
| Haben Sie eine Vorlage für den Kundenvertrag? | ✅ | keine | keine | 2.1s |
| Beide Helferinnen haben ihr erweitertes Führungszeugnis abgegeben. | ✅ | fuehrungszeugnis=erledigt | fuehrungszeugnis=erledigt | 3.2s |
