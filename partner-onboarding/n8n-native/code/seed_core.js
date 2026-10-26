// Demo data: 8 invented partners at different points of their 90 days, relative to today (same as
// data/generate_data.py). Run the setup workflow again before a demo so "day X" stays right.
// Each partner: [name, city, day in onboarding, active customers, {task: [status, day done or null, note]}].
// Tasks not listed: done on their due day if that day has passed, otherwise open.
function seedRows(partners, checklist, today) {
  const plus = (iso, n) => new Date(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10) + n)).toISOString().slice(0, 10);
  const partnerRows = [];
  const taskRows = [];
  partners.forEach(([name, city, day, customers, special], i) => {
    const id = i + 1;
    const start = plus(today, -(day - 1));
    partnerRows.push({ partner_id: id, name, stadt: city, start: start, betreuer: id % 2 ? 'Frau Becker' : 'Herr Yıldız',
      aktive_kunden: customers });
    for (const t of checklist) {
      let status = 'offen', doneDay = null, note = '';
      if (special[t.id]) [status, doneDay, note] = special[t.id];
      else if (t.due_day < day && !['erster_kunde', 'zehn_kunden'].includes(t.id)) [status, doneDay] = ['erledigt', t.due_day];
      taskRows.push({ partner_id: id, aufgabe: t.id, status, erledigt_am: doneDay ? plus(start, doneDay - 1) : '', notiz: note });
    }
  });
  return { partnerRows, taskRows };
}
