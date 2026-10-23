"""Split the handbook into sections and find the relevant ones (meaning + exact words, combined)."""
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
HANDBOOK = ROOT / "handbuch"
CACHE = ROOT / "data" / "index.json"
EMBED_MODEL = "granite-embedding:278m"
OLLAMA = "http://127.0.0.1:11434"


def load_sections():
    """One section per '## ' heading, with document title, owner and date for the citation."""
    sections = []
    for path in sorted(HANDBOOK.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = re.search(r"^# (.+)$", text, re.M).group(1).strip()
        meta = re.search(r"Verantwortlich: (.+?) · Stand: (\S+)", text)
        owner, date = (meta.group(1), meta.group(2)) if meta else ("", "")
        for part in re.split(r"^## ", text, flags=re.M)[1:]:
            heading, _, body = part.partition("\n")
            sections.append({"file": path.name, "doc": title, "section": heading.strip(),
                             "owner": owner, "date": date, "text": body.strip()})
    for i, s in enumerate(sections):
        s["id"] = i
    return sections


def embed(texts):
    try:
        r = httpx.post(f"{OLLAMA}/api/embed", json={"model": EMBED_MODEL, "input": texts}, timeout=120)
    except httpx.ConnectError as e:
        raise RuntimeError("Ollama is not running. Start it with: ollama serve") from e
    r.raise_for_status()
    return r.json()["embeddings"]


def _norm(text):
    return (text.lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss"))


STOP = set("der die das und oder ein eine einer eines einem einen ist sind wird werden wie was wann wer wo mit "
           "von zu im in am an auf fuer bei ich wir sie er es man muss darf kann soll mein meine unser unsere "
           "the a an is are what how when do does i we our of to for".split())


def tokens(text):
    """Lower-case words with a crude German suffix strip, so 'Kunden' matches 'Kunde'."""
    out = []
    for w in re.findall(r"\w+", _norm(text)):
        if w in STOP or len(w) < 2:
            continue
        for suffix in ("ungen", "en", "er", "es", "e", "n", "s"):
            if len(w) > 5 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


class Index:
    def __init__(self):
        self.sections = load_sections()
        texts = [f"{s['doc']} – {s['section']}\n{s['text']}" for s in self.sections]
        digest = hashlib.sha256(("|".join(texts) + EMBED_MODEL).encode()).hexdigest()
        cached = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
        if cached.get("digest") == digest:
            self.vectors = cached["vectors"]
        else:  # handbook changed: re-embed (takes a few seconds)
            self.vectors = embed(texts)
            CACHE.parent.mkdir(exist_ok=True)
            CACHE.write_text(json.dumps({"digest": digest, "vectors": self.vectors}), encoding="utf-8")
        self.doc_tokens = [tokens(t) for t in texts]
        self.avg_len = sum(map(len, self.doc_tokens)) / len(self.doc_tokens)
        df = Counter(t for doc in self.doc_tokens for t in set(doc))
        n = len(self.doc_tokens)
        self.idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
        self.max_idf = max(self.idf.values())  # for compound parts that never appear as a word of their own

    def _bm25(self, query_tokens, i, k1=1.5, b=0.75):
        tf = Counter(self.doc_tokens[i])
        # German compounds, both ways: "versicherung" should hit "betriebshaftpflichtversicherung",
        # and a question about "zielauslastung" should hit "auslastung".
        for qt in query_tokens:
            if len(qt) >= 5 and qt not in tf:
                inside = sum(c for t, c in tf.items() if qt in t)
                if not inside:
                    inside = sum(c for t, c in tf.items() if len(t) >= 6 and t in qt)
                if inside:
                    tf[qt] = inside
        length = len(self.doc_tokens[i])
        return sum(self.idf.get(t, self.max_idf) * tf[t] * (k1 + 1) / (tf[t] + k1 * (1 - b + b * length / self.avg_len))
                   for t in query_tokens if t in tf)

    def search(self, question, k=5):
        """Returns the top sections with both scores. Ranks are merged (reciprocal rank fusion)."""
        q = embed([question])[0]
        qn = math.sqrt(sum(x * x for x in q))
        cos = [sum(a * b for a, b in zip(q, v)) / (qn * math.sqrt(sum(x * x for x in v))) for v in self.vectors]
        qt = tokens(question)
        bm = [self._bm25(qt, i) for i in range(len(self.sections))]
        rank_cos = {i: r for r, i in enumerate(sorted(range(len(cos)), key=lambda i: -cos[i]))}
        rank_bm = {i: r for r, i in enumerate(sorted(range(len(bm)), key=lambda i: -bm[i]))}
        fused = sorted(range(len(cos)), key=lambda i: -(1 / (60 + rank_cos[i]) + 1 / (60 + rank_bm[i])))
        return [dict(self.sections[i], cosine=round(cos[i], 3), bm25=round(bm[i], 2)) for i in fused[:k]]
