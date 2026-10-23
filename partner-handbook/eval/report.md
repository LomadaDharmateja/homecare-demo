# Partner handbook assistant: evaluation

Local models: qwen2.5:3b (answers) and granite-embedding:278m (search). Questions were written before the assistant was built.

## tuning: 17/17 passed (100%)

Average 1.5s per question. 0 answers were replaced by the handbook excerpt because the check failed.

| Question | Status | Pass | Problem | Answer |
|---|---|---|---|---|
| Bis wann muss ich mit der Pflegekasse abrechnen? | answered | ✅ |  | Bis zum 5. Werktag des Folgemonats müssen Sie mit der Pflegekasse abrechnen. |
| Wie hoch ist der Entlastungsbetrag? | answered | ✅ |  | Der Entlastungsbetrag beträgt bis zu 131 Euro im Monat für Pflegebedürftige im Pflegegrad 1. |
| Wann verfallen übertragene Beträge vom Entlastungsbetrag? | answered | ✅ |  | Die übertragenen Beträge verfallen am 30. Juni des Folgejahres. |
| Welche Deutschkenntnisse brauchen Alltagshelfer? | answered | ✅ |  | Eine Deutschkenntnis mindestens auf Niveau B2 ist erforderlich. |
| Wie lange dauert die Startschulung für neue Partner? | answered | ✅ |  | Die Startschulung dauert 5 Tage und findet in der Zentrale in Düsseldorf statt. |
| Was mache ich, wenn ein Kunde nicht die Tür öffnet? | answered | ✅ |  | Anrufen und wenn nicht erreichbar die Ansprechperson kontaktieren. Bei Sorge um den Kunden die Polizei unter 110 verstehen. |
| Darf ich als Alltagshelfer ein Geschenk von einer Kundin annehmen? | answered | ✅ |  | Nein, Alltagshelfer dürfen keine Geld- oder Sachgeschenke annehmen. Ausgenommen sind kleine Aufmerksamkeiten bis zu einem Wert von 10 Euro, zum Beispiel Praline |
| Dürfen wir WhatsApp mit Kunden nutzen? | answered | ✅ |  | WhatsApp und andere private Messenger sind für Kundendaten verboten. |
| Wie hoch ist die Franchisegebühr? | answered | ✅ |  | Die laufende Franchisegebühr beträgt 6 Prozent vom Nettoumsatz. |
| Bis wann muss ein verpasster Anruf zurückgerufen werden? | answered | ✅ |  | Bis 4 Stunden während der Geschäftszeiten muss ein verpasster Anruf zurückgerufen werden. |
| Eine Anfrage kommt aus einem Gebiet eines anderen Partners. Was tun? | answered | ✅ |  | Die Anfrage wird innerhalb von 24 Stunden an den zuständigen Partner weitergeleitet. Die Zuordnung steht in der Gebietsliste in der Partnersoftware. |
| Wie viele Kunden sollte ich nach 90 Tagen haben? | answered | ✅ |  | Nach 90 Tagen sollten Sie mindestens 10 aktive Kunden haben. |
| Bis wann muss sich ein Alltagshelfer krankmelden? | answered | ✅ |  | Bis spätestens 7 Uhr am Einsatztag |
| How much cash should a partner keep in the bank account? | answered | ✅ |  | Jeder Partner sollte mindestens zwei Monatsausgaben abdecken, wie als Faustregel festgelegt. |
| Wie hoch ist das Gehalt der Geschäftsführung in der Zentrale? | not_found | ✅ |  | Dazu steht nichts im Partnerhandbuch. Bitte wende dich an die Zentrale. Die Frage wurde notiert, damit das Handbuch ergänzt werden kann. |
| Ein Kunde ist gestürzt und atmet schwer. Was soll ich tun? | emergency | ✅ |  | 🚨 Bei Lebensgefahr, Bewusstlosigkeit oder Atemnot sofort den Notruf 112 wählen. Danach die Partnerleitung informieren.  Bei Lebensgefahr, Bewusstlosigkeit, Atem |
| Welche Versicherung brauche ich als neuer Partner? | answered | ✅ |  | Die Betriebshaftpflichtversicherung mit einer Mindestdeckungssumme von 3 Millionen Euro ist abzuschließen. |

## final_test: 14/15 passed (93%)

Average 1.1s per question. 2 answers were replaced by the handbook excerpt because the check failed.

| Question | Status | Pass | Problem | Answer |
|---|---|---|---|---|
| Wie lange werden Leistungsnachweise aufbewahrt? | answered | ✅ |  | Leistungsnachweise werden 10 Jahre aufbewahrt. |
| Was ist der Umwandlungsanspruch? | answered | ✅ |  | Bei Pflegegrad 2 bis 5 können bis zu 40 Prozent der nicht genutzten Pflegesachleistung für Angebote zur Unterstützung im Alltag verwendet werden. |
| Wie viele Stunden umfasst die Basisschulung in NRW? | excerpt_shown | ✅ |  | Im Handbuch steht dazu:  Vor dem ersten Einsatz absolviert jeder Alltagshelfer die Basisschulung nach Landesrecht. In NRW umfasst sie 30 Unterrichtsstunden, dav |
| Bis wann können Kunden einen Einsatz kostenlos absagen? | answered | ✅ |  | Kunden können einen Einsatz bis 24 Stunden vorher kostenfrei absagen. |
| Wie schnell muss ich auf eine Beschwerde reagieren? | answered | ❌ | missing ['2 Werktage|zwei Werktage'] | Sie müssen eine Beschwerde noch am selben Tag im Beschwerdeformular erfasst haben. Wenn die Beschwerde nach 10 Werktagen nicht gelöst ist, wird sie an die Zentr |
| Was muss ich bei einer Datenpanne tun? | answered | ✅ |  | In einer Datenpanne muss die Partnerleitung die Datenschutzkoordination der Zentrale sofort informieren und eine Meldung an die Aufsichtsbehörde innerhalb von 7 |
| Bieten wir Wundversorgung an? | answered | ✅ |  | Nein, Wundversorgung gehört nicht zu unseren Leistungen. |
| Wie viel Kilometergeld bekommen die Mitarbeiter? | answered | ✅ |  | 15 Euro brutto plus 0,30 Euro pro gefahrenem Kilometer mit dem eigenen Auto. |
| Wann muss der Einsatzplan für die nächste Woche fertig sein? | answered | ✅ |  | Der Einsatzplan für die nächste Woche steht jeden Donnerstag bis 16 Uhr in der Partnersoftware. |
| Darf ich eigene Flyer gestalten? | answered | ✅ |  | Nein, eigene Designs sind nicht erlaubt. |
| Bis wann melde ich meine monatlichen Kennzahlen? | answered | ✅ |  | Bis zum 10. des Folgemonats meldest du deine Kennzahlen über die Partnersoftware. |
| What is the target utilisation rate for staff? | excerpt_shown | ✅ |  | The handbook says:  - Auslastung: geleistete Stunden geteilt durch bezahlte Arbeitsstunden. Ziel: mindestens 75 Prozent. - Conversion Rate: Neukunden geteilt du |
| Welche Software empfiehlt die Zentrale für die Buchhaltung? | not_found | ✅ |  | Dazu steht nichts im Partnerhandbuch. Bitte wende dich an die Zentrale. Die Frage wurde notiert, damit das Handbuch ergänzt werden kann. |
| Wie viel kostet ein Franchise-Standort in Österreich? | not_found | ✅ |  | Dazu steht nichts im Partnerhandbuch. Bitte wende dich an die Zentrale. Die Frage wurde notiert, damit das Handbuch ergänzt werden kann. |
| Meine Kundin ist bewusstlos, was jetzt? | emergency | ✅ |  | 🚨 Bei Lebensgefahr, Bewusstlosigkeit oder Atemnot sofort den Notruf 112 wählen. Danach die Partnerleitung informieren.  Notfall: Sofort den Notruf 112 wählen. |

## english_tuning: 6/6 passed (100%)

Average 1.6s per question. 0 answers were replaced by the handbook excerpt because the check failed.

| Question | Status | Pass | Problem | Answer |
|---|---|---|---|---|
| Is a gift from a customer allowed? | answered | ✅ |  | No, gifts from customers are not allowed. Small gifts up to a value of 10 Euro, such as chocolates, are permitted. |
| Can a helper accept a present from a client? | answered | ✅ |  | No, Alltagshelfer dürfen keine Geld- oder Sachgeschenke annehmen. Ausgenommen sind kleine Aufmerksamkeiten bis zu einem Wert von 10 Euro. |
| May I accept a gift from a customer? | answered | ✅ |  | No, gifts are not allowed. Small gifts up to 10 Euro, like chocolates, are permitted. |
| How quickly do we have to return a missed call? | answered | ✅ |  | Verpasste Anrufe werden innerhalb von 4 Stunden während der Geschäftszeiten zurückgerufen. |
| Which accounting software does head office recommend? | not_found | ✅ |  | The partner handbook doesn't cover this. Please contact head office. The question has been logged so the handbook can be extended. |
| My client is unconscious, what do I do? | emergency | ✅ |  | 🚨 If life is in danger, the person is unconscious or cannot breathe: call 112 immediately. Then inform the location manager.  Bei Lebensgefahr, Bewusstlosigkeit |

## english_test: 10/10 passed (100%)

Average 1.4s per question. 2 answers were replaced by the handbook excerpt because the check failed.

| Question | Status | Pass | Problem | Answer |
|---|---|---|---|---|
| How much relief allowance can a customer claim per month? | excerpt_shown | ✅ |  | The handbook says:  Pflegebedürftige ab Pflegegrad 1 haben Anspruch auf den Entlastungsbetrag von bis zu 131 Euro im Monat. Nicht genutzte Beträge werden in die |
| By which working day do we have to bill the care insurance fund? | answered | ✅ |  | Abrechnung immer bis zum 5. Werktag des Folgemonats über die Partnersoftware. |
| How long is the starting training for new partners? | answered | ✅ |  | The starting training for new partners lasts for 5 days and is held in the central location in Düsseldorf. sources: [2] Onboarding neuer Franchisepartner – Phas |
| What level of German do helpers need? | answered | ✅ |  | Eine Deutschkenntnis mindestens auf Niveau B2 ist erforderlich. |
| How much mileage allowance do helpers get? | answered | ✅ |  | 15 Euro brutto plus 0,30 Euro pro gefahrenem Kilometer mit dem eigenen Auto. |
| When does next week's schedule have to be ready? | answered | ✅ |  | Der Einsatzplan für die nächste Woche steht jeden Donnerstag bis 16 Uhr in der Partnersoftware. |
| How long do we keep invoices and service records? | answered | ✅ |  | Leistungsnachweise und Rechnungen werden 10 Jahre aufbewahrt. |
| How high is the ongoing franchise fee? | excerpt_shown | ✅ |  | The handbook says:  Die laufende Franchisegebühr beträgt 6 Prozent vom Nettoumsatz, dazu kommt eine Marketingumlage von 1 Prozent. Beide werden monatlich zum 15 |
| Does head office provide partners with a company car? | not_found | ✅ |  | The partner handbook doesn't cover this. Please contact head office. The question has been logged so the handbook can be extended. |
| A customer has chest pain and can't breathe properly! | emergency | ✅ |  | 🚨 If life is in danger, the person is unconscious or cannot breathe: call 112 immediately. Then inform the location manager. |
