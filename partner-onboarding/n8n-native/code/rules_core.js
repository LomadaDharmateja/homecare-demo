// Partner update -> proposed checklist changes. Same logic as app/updates.py, written for n8n Code nodes.
// Code splits the message and finds the tasks; clear wording is decided by rules; only unclear clauses go to
// the AI (one small question each). Nothing here changes the checklist: a person approves later.

// JavaScript's \b and \w only know a-z. German needs ä, ö, ü, ß, so both are rebuilt with Unicode classes.
const WORD = '[\\p{L}\\p{N}_]';
const BOUNDARY = `(?:(?<=${WORD})(?!${WORD})|(?<!${WORD})(?=${WORD}))`;
function rx(source, flags = 'iu') {
  return new RegExp(source.replace(/\\b/g, BOUNDARY).replace(/\\w/g, WORD), flags);
}

const BLOCKED = rx('leider|abgesagt|abgesprungen|abgelehnt|fehlt|fehlen|nachgefordert|immer noch nicht|' +
  'warten immer noch|zickt|klappt( es)?( leider)? nicht|keine passenden|problem|cancel+ed|rejected|refused|missing');
const NOT_DONE = rx('\\b(noch nicht|nicht|kein|keine|keinen|werden|wird|planen|geplant|nächste[nrs]?|bald|' +
  'morgen|hoffentlich|sobald|demnächst|wollen|möchten|soll|dauert noch|' +
  'not|no|will|plan|planned|next|soon|tomorrow|hope)\\b|\\?');
const DONE = rx('\\b(abgeschlossen|eröffnet|angemeldet|eingestellt|angemietet|gegründet|verteilt|erschienen|' +
  'gekommen|online|aktiv|eingerichtet|raus|liegt vor|liegen vor|ist da|sind da|zugelassen|anerkannt|' +
  'teilgenommen|besucht|stattgefunden|signed|done|open|ready|hired|approved|registered|completed)\\b');
// The AI may only call something done in a clause that reports the past or a state.
const PAST = rx('\\b(ist|sind|war|waren|wurde|wurden|hat|haben|hatten|seit|bereits|schon|' +
  'is|are|was|were|has|have|had|already)\\b|\\bge\\w+[t|n]\\b|\\w+ed\\b');
const NUM = { ersten: 1, zwei: 2, drei: 3, vier: 4, 'fünf': 5, sechs: 6, sieben: 7, acht: 8, neun: 9,
  zehn: 10, elf: 11, 'zwölf': 12 };
const CUSTOMERS = rx('\\b(\\d{1,3}|' + Object.keys(NUM).join('|') + ')\\s+(?:aktive[n]?\\s+)?(kunden|kundinnen|kunde|kundin|' +
  'customers|clients)\\b');
// Generic words: they mention a task in passing more often than they report on it.
const WEAK = { helfer: ['helfer', 'mitarbeiter', 'personal', 'staff', 'carer', 'helper'],
  erster_kunde: ['kunde', 'kundin', 'customer', 'client'], software: ['software'] };

function sentences(text) {
  return text.split(/(?<=[.!?])\s+|\n+/u).map(s => s.trim()).filter(Boolean);
}
function clauses(sentence) {
  return sentence.split(/,\s+|;\s+|\s+(?:aber|but)\s+/u).map(c => c.trim()).filter(Boolean);
}
const esc = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Position of a word. Long words also inside compounds ('Haftpflichtversicherung'); 4-5 letters at the start
// or end of a word ('Geschäftskonto'); 2-3 letters only as a whole word ('ug' is not in 'Führungszeugnis').
function has(text, word) {
  if (word.startsWith('^')) {
    const m = text.match(rx('(?<!\\w)' + esc(word.slice(1)), 'u'));
    return m ? m.index : -1;
  }
  if (word.length >= 6) return text.indexOf(word);
  const w = esc(word);
  const m = text.match(rx(word.length <= 3 ? `\\b${w}\\b` : `(?<!\\w)${w}|${w}(?!\\w)`, 'u'));
  return m ? m.index : -1;
}

// Tasks a clause talks about, in the order they appear. A generic word only counts when nothing more specific
// is there: 'Führungszeugnisse für beide Helfer liegen vor' is about the certificate.
function mentioned(text, judged) {
  const low = text.toLowerCase().replace(/antrag(s|es)? auf (anerkennung|zulassung)/gu, 'antrag');
  const first = (task, weak) => {
    const hits = task.words.filter(w => (WEAK[task.id] || []).includes(w) === weak).map(w => has(low, w)).filter(h => h >= 0);
    return hits.length ? Math.min(...hits) : null;
  };
  let found = judged.map(t => [t.id, first(t, false)]).filter(([, p]) => p !== null);
  if (!found.length) found = judged.map(t => [t.id, first(t, true)]).filter(([, p]) => p !== null);
  return found.sort((a, b) => a[1] - b[1]).map(([id]) => id);
}

function addDays(iso, n) {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + n);
  return d.toISOString().slice(0, 10);
}

function doneDate(text, received) {
  const low = text.toLowerCase();
  if (low.includes('vorgestern')) return addDays(received, -2);
  if (low.includes('gestern') || low.includes('yesterday')) return addDays(received, -1);
  const m = low.match(/(?<![\p{L}\p{N}_])am (\d{1,2})\.(\d{1,2})\./u);
  if (m) {
    const [day, month] = [Number(m[1]), Number(m[2])];
    const d = new Date(Date.UTC(Number(received.slice(0, 4)), month - 1, day));
    if (d.getUTCMonth() === month - 1 && d.getUTCDate() === day) return d.toISOString().slice(0, 10);
  }
  return received;
}

// 'Stand heute: 4 Kunden aktiv' -> 4. Not from plans ('hoffentlich 10 Kunden').
function customerCount(message) {
  for (const s of sentences(message)) {
    if (NOT_DONE.test(s)) continue;
    const m = s.match(CUSTOMERS);
    if (m) {
      const n = m[1].toLowerCase();
      return /^\d+$/.test(n) ? Number(n) : NUM[n];
    }
  }
  return null;
}

// Step 1: rules. Returns the events in message order. Clauses the rules cannot decide become 'ai' events,
// one per (clause, task) pair; questions[] is what goes to the AI.
function ruleEvents(message, checklist) {
  const judged = checklist.filter(t => t.id !== 'zehn_kunden');
  const events = [];
  const questions = [];
  for (const s of sentences(message)) {
    let previous = [];
    for (const c of clauses(s)) {
      const tasks = mentioned(c, judged);
      if (!tasks.length) {
        if (BLOCKED.test(c) && previous.length) {  // "..., uns fehlt noch ein Formular"
          events.push({ kind: 'add', task: previous[0], status: 'blockiert', satz: s, how: 'Regel: Hindernis genannt', sentence: s });
        }
        continue;
      }
      previous = tasks;
      if (BLOCKED.test(c)) {
        events.push({ kind: 'add', task: tasks[0], status: 'blockiert', satz: c, how: 'Regel: Hindernis genannt', sentence: s });
      } else if (NOT_DONE.test(c)) {
        events.push({ kind: 'note', satz: c, tasks, grund: "Plan, Frage oder 'noch nicht': keine Änderung" });
      } else if (DONE.test(c)) {
        for (const t of tasks) events.push({ kind: 'add', task: t, status: 'erledigt', satz: c, how: 'Regel: als erledigt gemeldet', sentence: s });
      } else if (!PAST.test(c)) {  // "Die Startschulung machen wir im Dezember": the AI once said done
        events.push({ kind: 'note', satz: c, tasks, grund: 'keine Vergangenheit, kein Zustand: keine Änderung' });
      } else {
        for (const t of tasks) {
          events.push({ kind: 'ai', q: questions.length, satz: c, task: t, sentence: s });
          questions.push({ satz: c, task: t, titel: checklist.find(x => x.id === t).title });
        }
      }
    }
  }
  return { events, questions };
}

// Step 2: replay the events with the AI's answers, then add the customer count and follow-on facts.
function buildProposal(message, events, answers, received) {
  const accepted = {};
  const order = [];
  const notes = [];
  const add = (task, status, satz, how, sentence) => {
    const old = accepted[task];
    if (old && (old.status === 'erledigt' || status === 'blockiert')) return;  // "done" wins
    if (!old) order.push(task);
    accepted[task] = { task, status, satz, entschieden_von: how,
      done_on: status === 'erledigt' ? doneDate(sentence, received) : null };
  };
  for (const e of events) {
    if (e.kind === 'add') add(e.task, e.status, e.satz, e.how, e.sentence);
    else if (e.kind === 'note') notes.push({ satz: e.satz, tasks: e.tasks, grund: e.grund });
    else {
      const a = answers[e.q] || { begruendung: 'ungültige Modellantwort', erledigt: false };
      if (a.erledigt === true) add(e.task, 'erledigt', e.satz, `KI: ${a.begruendung}`, e.sentence);
      else notes.push({ satz: e.satz, tasks: [e.task], grund: `KI: keine Änderung (${a.begruendung})` });
    }
  }
  const customers = customerCount(message);
  const derive = (task, why) => {
    if ((accepted[task] || {}).status !== 'erledigt') {
      if (!accepted[task]) order.push(task);
      accepted[task] = { task, status: 'erledigt', satz: why, entschieden_von: 'Regel: Folgerung', done_on: received };
    }
  };
  if ((accepted.zulassung || {}).status === 'erledigt') derive('antrag', 'Zulassung liegt vor, also wurde der Antrag gestellt');
  if (customers && customers >= 1) derive('erster_kunde', `${customers} aktive Kunden, also hat der erste Einsatz stattgefunden`);
  if (customers && customers >= 10) derive('zehn_kunden', `${customers} aktive Kunden`);
  return { changes: order.map(t => accepted[t]), notes, active_customers: customers };
}

// The checklist comes from a data table: words are stored comma-separated.
function checklistFromRows(rows) {
  return rows.slice().sort((a, b) => a.nr - b.nr).map(r => ({
    id: r.aufgabe, phase: r.phase, title: r.titel, due_day: r.faellig_tag, owner: r.zustaendig,
    gate: r.vor_erstem_kunden === true, words: String(r.stichwoerter).split(',').map(w => w.trim()).filter(Boolean),
  }));
}
