# Partner analytics: evaluation

Scores the step where the local model (qwen2.5:3b) turns a question into the query form. A question counts as correct only if every expected field matches. Numbers are computed by Python from the form, so a correct form means a correct number.

## tuning: 20/20 correct (100%)

Rules corrected the model on 11 questions. Average time 0.7s per question.

| Question | Result | Wrong fields (expected → got) |
|---|---|---|
| What was our total revenue last month? | ✅ |  |
| Which 5 locations have the most customers? | ✅ |  |
| Which locations lost the most customers in the last 6 months? | ✅ |  |
| Do partners who founded with a friend open a second location faster? | ✅ |  |
| How did total revenue develop over the last 12 months? | ✅ |  |
| Which 3 locations have the least cash? | ✅ |  |
| Wie hoch war der Umsatz in Bayern im letzten Monat? | ✅ |  |
| Profit by state over the last 3 months | ✅ |  |
| How many locations do we have in NRW? | ✅ |  |
| Which locations are furthest below their business plan? | ✅ |  |
| What is the conversion rate from enquiries to new customers by state? | ✅ |  |
| How many staff does Essen have? | ✅ |  |
| Which share of partners has opened a second location, by founder type? | ✅ |  |
| How has the number of enquiries changed over the last 3 months compared to before? | ✅ |  |
| Top 10 locations by hours delivered in the last 12 months | ✅ |  |
| Wie hat sich der Gewinn in Oberhausen in den letzten 3 Monaten verändert? | ✅ |  |
| Revenue by opening year | ✅ |  |
| Which state grew revenue the most over the last 6 months? | ✅ |  |
| How many new customers did we win last month? | ✅ |  |
| Show the trend of customers in Sachsen | ✅ |  |

## final_test: 14/15 correct (93%)

Rules corrected the model on 9 questions. Average time 0.7s per question.

| Question | Result | Wrong fields (expected → got) |
|---|---|---|
| Which 4 locations made the highest profit last month? | ✅ |  |
| Welche Standorte haben am wenigsten Liquidität? | ✅ |  |
| Are friend-founded partners more likely to open a second site? | ✅ |  |
| How did costs develop over the last 6 months? | ✅ |  |
| What's the revenue versus plan for Bavaria? | ✅ |  |
| Customers per state last month | ✅ |  |
| Which locations had the biggest drop in revenue over the last 3 months? | ✅ |  |
| How much cash does Krefeld have? | ✅ |  |
| Wie viele Anfragen hatten wir in den letzten 12 Monaten? | ✅ |  |
| Conversion rate by founder type | ✅ |  |
| Show monthly profit for the whole network over the last year | ✅ |  |
| Which 5 locations gained the most customers in the last 6 months? | ❌ | metric: customers → new_customers |
| How many locations opened per year? | ✅ |  |
| Average months until a second location, all partners | ✅ |  |
| Staff numbers by state | ✅ |  |

## german_tuning: 10/10 correct (100%)

Rules corrected the model on 7 questions. Average time 0.7s per question.

| Question | Result | Wrong fields (expected → got) |
|---|---|---|
| Welche 5 Standorte hatten letzten Monat den höchsten Umsatz? | ✅ |  |
| Wie hat sich die Zahl der Kunden in den letzten 12 Monaten entwickelt? | ✅ |  |
| Welche Standorte liegen am weitesten unter ihrem Businessplan? | ✅ |  |
| Wie viel Liquidität hat Hagen? | ✅ |  |
| Gewinn nach Bundesland in den letzten 3 Monaten | ✅ |  |
| Eröffnen Partner, die mit Freunden gegründet haben, schneller einen zweiten Standort? | ✅ |  |
| Wie viele Standorte haben wir in Sachsen? | ✅ |  |
| Welche 3 Standorte haben in den letzten 6 Monaten die meisten Kunden verloren? | ✅ |  |
| Wie viele Neukunden hatten wir im letzten Monat? | ✅ |  |
| Wie hoch ist die Conversion Rate nach Gründertyp? | ✅ |  |

## german_test: 10/10 correct (100%)

Rules corrected the model on 6 questions. Average time 0.7s per question.

| Question | Result | Wrong fields (expected → got) |
|---|---|---|
| Welche 4 Standorte haben die wenigsten Mitarbeiter? | ✅ |  |
| Wie haben sich die Kosten in NRW im letzten Jahr entwickelt? | ✅ |  |
| Wie hoch war der Gewinn in Oberhausen im letzten Monat? | ✅ |  |
| Umsatz nach Eröffnungsjahr | ✅ |  |
| Welches Bundesland ist in den letzten 6 Monaten beim Umsatz am stärksten gewachsen? | ✅ |  |
| Wie viele Stunden wurden in den letzten 3 Monaten insgesamt geleistet? | ✅ |  |
| Wie viel Prozent der Partner haben einen zweiten Standort eröffnet? | ✅ |  |
| Welche Standorte hatten in den letzten 3 Monaten den stärksten Rückgang bei den Anfragen? | ✅ |  |
| Liquidität nach Bundesland | ✅ |  |
| Wie hat sich der Umsatz in Krefeld in den letzten 3 Monaten im Vergleich zu davor verändert? | ✅ |  |
