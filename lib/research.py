"""research.py — riset topik otomatis buat auto-post.

Alur: cari post rame di Threads per keyword (scraper.search_posts) -> LLM
rangkum jadi daftar sudut/topik segar -> dipakai sebagai topic_hint generate_random.
Hasil di-cache per (niche, lang) biar gak scrape tiap tick.
Aktif kalau RESEARCH_ENABLED=1 di .env. Gagal = diam-diam fallback ke tanpa riset.
"""
import json
import os
import random
import re
import time

from lib import ai

CACHE_TTL = 6 * 3600
_cache = {}  # (niche, lang) -> (ts, [angles])


def enabled():
    return os.environ.get("RESEARCH_ENABLED", "0") == "1"


def _min_likes():
    return int(os.environ.get("RESEARCH_MIN_LIKES", "100"))


def parse_angles(raw):
    """Ambil list string dari output LLM (JSON array, fallback per baris)."""
    m = re.search(r"\[.*\]", raw or "", re.S)
    if m:
        try:
            arr = json.loads(m.group(0))
            return [str(a).strip() for a in arr if str(a).strip()][:8]
        except ValueError:
            pass
    lines = [re.sub(r"^[\-\*\d\.\)\s]+", "", ln).strip() for ln in (raw or "").splitlines()]
    return [ln for ln in lines if ln][:8]


def _angles_from_posts(niche, posts, lang):
    corpus = "\n".join(f"- ({p['likes']} likes) {p['text'][:300]}" for p in posts[:12])
    bahasa = "Bahasa Indonesia" if lang == "id" else "English"
    prompt = (
        f"Berikut post Threads yang lagi rame soal '{niche}':\n{corpus}\n\n"
        "Tarik 5 sudut/topik edukasi yang BELUM basi dan relevan dengan tren di atas. "
        "Jangan copy kalimat post. Tiap sudut satu kalimat pendek, spesifik. "
        f"Tulis dalam {bahasa}. Balas HANYA JSON array berisi string."
    )
    return parse_angles(ai._chat([{"role": "user", "content": prompt}], max_tokens=500))


def get_angle(niche, lang="id", avoid=None):
    """Return 1 sudut topik hasil riset buat niche ini, atau None."""
    if not enabled():
        return None
    key = (niche, lang)
    hit = _cache.get(key)
    if not hit or time.time() - hit[0] > CACHE_TTL:
        try:
            from lib import scraper
            posts = scraper.search_posts(niche, min_likes=_min_likes(),
                                         max_age_hours=48, limit=15)
            angles = _angles_from_posts(niche, posts, lang) if posts else []
        except Exception as e:
            print(f"[research] '{niche}' gagal: {str(e)[:120]}", flush=True)
            angles = []
        _cache[key] = (time.time(), angles)
        hit = _cache[key]
    pool = [a for a in hit[1] if not avoid or a not in avoid]
    return random.choice(pool) if pool else None
