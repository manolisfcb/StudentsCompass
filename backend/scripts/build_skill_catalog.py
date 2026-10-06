"""Build the skill catalogue seed from ESCO and O*NET (TASK-082, plan 11 §5).

Two steps, so the network is touched once and the file in the repository is
reproducible from what was downloaded:

    # 1. Download the sources into a cache directory (not committed).
    python scripts/build_skill_catalog.py fetch --cache /tmp/skill-sources

    # 2. Apply the rules and write app/data/skill_catalog/skill_catalog_v1.json.gz
    python scripts/build_skill_catalog.py build --cache /tmp/skill-sources

Then load it with ``scripts/seed_skill_catalog.py`` and embed the new skills
with ``scripts/sync_skill_embeddings.py``.

Sources and licences (attribution is kept in the generated file):

* ESCO v1.2 skills (European Commission), through its public API: English and
  Spanish labels and alternative labels, skill type, reuse level. Free reuse
  with attribution (Commission Decision 2011/833/EU).
* O*NET 31.0 Software Skills (U.S. Department of Labor, Employment and Training
  Administration), CC BY 4.0: the named tools workers use.

Why the rules exist: the extractor matches a key wherever its words appear,
and a key that is also an everyday word turns every posting into a false
requirement. The rules below are what keeps a catalogue of thousands as
precise as the 117 hand-written skills it extends; ``catalog_rules.json``
holds the reviewed word lists they use.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.analytics.skillNormalizer import SkillNormalizer  # noqa: E402

DATA_DIR = ROOT_DIR / "app" / "data" / "skill_catalog"
RULES_PATH = DATA_DIR / "catalog_rules.json"
OUTPUT_PATH = DATA_DIR / "skill_catalog_v1.json.gz"
CATALOG_VERSION = "esco1.2_onet31_v1"

ONET_VERSION = "31.0"
ONET_SOFTWARE_URL = f"https://www.onetcenter.org/dl_files/database/db_{ONET_VERSION.replace('.', '_')}_csv/software_skills.csv"
ESCO_SEARCH_URL = "https://ec.europa.eu/esco/api/search?language=en&type=skill&full=true"
ESCO_PAGE = 20
ESCO_WORKERS = 4

#: A label longer than this is a sentence, not a name: ESCO's "handle financial
#: overviews of the store" will never appear verbatim in a posting, and every
#: key costs memory in every lookup.
MAX_LABEL_TOKENS = 4
MIN_LABEL_CHARS = 2

normalize = SkillNormalizer.normalize_text


# -- fetch --------------------------------------------------------------------


def _curl(url: str) -> bytes | None:
    """curl rather than urllib: it verifies TLS against the system store."""
    for attempt in range(3):
        proc = subprocess.run(["curl", "-sSfL", "--max-time", "120", url], capture_output=True)
        if proc.returncode == 0:
            return proc.stdout
        time.sleep(2 * (attempt + 1))
    return None


def _esco_row(record: dict) -> dict:
    links = record.get("_links", {})
    return {
        "uri": record["uri"],
        "pref": {lang: record["preferredLabel"].get(lang) for lang in ("en", "es")},
        "alt": {lang: (record.get("alternativeLabel") or {}).get(lang, []) for lang in ("en", "es")},
        "skill_type": [link.get("title") for link in links.get("hasSkillType", [])],
        "reuse_level": [link.get("title") for link in links.get("hasReuseLevel", [])],
        "status": record.get("status"),
    }


def fetch(cache: Path) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    software = _curl(ONET_SOFTWARE_URL)
    if software is None:
        raise SystemExit("could not download O*NET software skills")
    (cache / "onet_software_skills.csv").write_bytes(software)

    # ESCO's `offset` is a page index for the given `limit`, and some records
    # break the full view with a 500: such a page is read record by record and
    # what still fails is listed, never silently dropped.
    first = json.loads(_curl(f"{ESCO_SEARCH_URL}&limit=1&offset=0"))
    total = first["total"]
    pages_dir = cache / "esco_pages"
    pages_dir.mkdir(exist_ok=True)

    def page(index: int) -> None:
        path = pages_dir / f"{index:04d}.json"
        if path.exists():
            return
        raw = _curl(f"{ESCO_SEARCH_URL}&limit={ESCO_PAGE}&offset={index}")
        rows, failed = [], []
        if raw is not None:
            rows = [_esco_row(r) for r in json.loads(raw)["_embedded"]["results"]]
        else:
            for record_index in range(index * ESCO_PAGE, min((index + 1) * ESCO_PAGE, total)):
                one = _curl(f"{ESCO_SEARCH_URL}&limit=1&offset={record_index}")
                results = json.loads(one)["_embedded"]["results"] if one else []
                if results:
                    rows.extend(_esco_row(r) for r in results)
                else:
                    failed.append(record_index)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"rows": rows, "failed": failed}))
        tmp.replace(path)

    pages = range((total + ESCO_PAGE - 1) // ESCO_PAGE)
    with ThreadPoolExecutor(ESCO_WORKERS) as pool:
        list(pool.map(page, pages))

    skills, failed = [], []
    for index in pages:
        data = json.loads((pages_dir / f"{index:04d}.json").read_text())
        skills.extend(data["rows"])
        failed.extend(data["failed"])
    (cache / "esco_skills.json").write_text(json.dumps({"total": total, "skills": skills, "failed_indexes": failed}))
    print(f"ESCO: {len(skills)} of {total} skills, {len(failed)} unreadable; O*NET software written.")


# -- build --------------------------------------------------------------------


def _load_rules() -> dict:
    rules = json.loads(RULES_PATH.read_text())
    # Compared in the form the extractor matches in (plurals folded):
    # "securities" is "security" by then, and "security" is prose.
    return {
        "everyday_words": {SkillNormalizer.match_key(word) for word in rules["everyday_words"]},
        "single_word_allow": {SkillNormalizer.match_key(word) for word in rules["single_word_allow"]},
        "blocked_labels": {normalize(label) for label in rules["blocked_labels"]},
        "vendor_prefixes": sorted(rules["vendor_prefixes"], key=len, reverse=True),
        "generic_vendor_remainders": {normalize(label) for label in rules["generic_vendor_remainders"]},
    }


def _usable(label: str, rules: dict, *, single_ok: bool = True) -> bool:
    """Whether ``label`` may become a key. ``single_ok`` False refuses one-word labels."""
    key = normalize(label)
    if len(key) < MIN_LABEL_CHARS or key in rules["blocked_labels"]:
        return False
    tokens = key.split()
    if len(tokens) > MAX_LABEL_TOKENS:
        return False
    if all(token.isdigit() for token in tokens):
        return False
    folded = SkillNormalizer.match_key(label)
    if len(tokens) == 1 and folded not in rules["single_word_allow"]:
        # A one-word key that is ordinary prose ("lead", "access", "it")
        # matches sentences, not skills.
        if not single_ok or folded in rules["everyday_words"] or len(key) <= 2:
            return False
    return True


_TRAILING_ACRONYM = re.compile(r"^(?P<name>.+?)\s+(?P<acronym>[A-Z][A-Z0-9+#.]{1,7})(?:\s+software)?$")


def _onet_aliases(example: str, rules: dict) -> list[str]:
    """`Microsoft Excel` → Excel; `Structured query language SQL` → SQL and the long name.

    An acronym is taken only when it abbreviates the name before it (same
    first letter, a name of two words or more): "RESTful API" does not make
    every API a RESTful one, and "Accurate NXG" does not make "accurate" a
    tool. The leftover name becomes an alias only when it is more than one
    word, for the same reason.
    """
    aliases = []
    for prefix in rules["vendor_prefixes"]:
        if example.startswith(prefix + " "):
            remainder = example[len(prefix) + 1 :]
            if normalize(remainder) not in rules["generic_vendor_remainders"]:
                aliases.append(remainder)
            break
    match = _TRAILING_ACRONYM.match(example)
    if match:
        name, acronym = match.group("name"), match.group("acronym")
        if len(name.split()) >= 2 and name[0].lower() == acronym[0].lower():
            aliases.extend([acronym, name])
    if example.endswith(" software"):
        aliases.append(example[: -len(" software")])
    return aliases


_GENERIC_CATEGORY = re.compile(r"^[A-Z0-9]?[a-z0-9 ,\-/&()]+ (software|systems?|programs?|applications?)$")


def _onet_skills(cache: Path, rules: dict) -> list[dict]:
    occupations: dict[str, set[str]] = defaultdict(set)
    hot: set[str] = set()
    category: dict[str, str] = {}
    with open(cache / "onet_software_skills.csv", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            example = row["Workplace Example"].strip()
            occupations[example].add(row["O*NET-SOC Code"])
            category.setdefault(example, row["Element Name"])
            if row["Hot Technology"] == "Y" or row["In Demand"] == "Y":
                hot.add(example)

    skills = []
    for example in sorted(occupations):
        # "Accounts payable software", "Web browser software": a kind of
        # tool, not a tool. Nobody lists it as a skill by that name.
        if _GENERIC_CATEGORY.match(example):
            continue
        # A tool one occupation names once is noise at this scale; a hot or
        # in-demand one is kept whatever its spread.
        if len(occupations[example]) < 2 and example not in hot:
            continue
        if not _usable(example, rules):
            continue
        keep = [example, *(alias for alias in _onet_aliases(example, rules) if _usable(alias, rules))]
        skills.append(
            {
                "display": example,
                "category": "software",
                "source": f"onet_{ONET_VERSION}",
                "reference": f"onet:{category[example]}",
                "labels": keep,
            }
        )
    return skills


def _esco_skills(cache: Path, rules: dict) -> list[dict]:
    data = json.loads((cache / "esco_skills.json").read_text())
    skills = []
    for record in data["skills"]:
        if record.get("status") not in (None, "released"):
            continue
        english = record["pref"].get("en")
        if not english:
            continue
        knowledge = "knowledge" in record["skill_type"]
        # A one-word label is kept only as the preferred term: ESCO's one-word
        # alternatives are where the prose hides ("it" for ICT, "confidence",
        # "hearing", "sounds"), while its preferred ones are fields of study
        # ("accounting", "biostatistics").
        if not _usable(english, rules):
            continue
        # Alternatives only when they are a form of the preferred term
        # ("business models", "meeting commitments"). ESCO's other
        # alternatives are loose synonyms — "banking" and "financial data"
        # for economics, "help customers" for advise customers — and each one
        # turned an ordinary sentence into the wrong skill.
        keep = [english]
        spanish = record["pref"].get("es")
        if spanish and _usable(spanish, rules):
            keep.append(spanish)
        for language, preferred in (("en", english), ("es", spanish)):
            for label in record["alt"].get(language, []):
                if preferred and _is_variant(label, preferred) and _usable(label, rules, single_ok=False):
                    keep.append(label)
        if not keep:
            continue
        skills.append(
            {
                "display": english[:160],
                "category": "esco_knowledge" if knowledge else "esco_skill",
                "source": "esco_1.2",
                "reference": record["uri"],
                "labels": keep,
            }
        )
    return skills


_STEM = 5


def _stems(label: str) -> set[str]:
    return {token[:_STEM] for token in normalize(label).split() if len(token) > 2}


def _is_variant(alternative: str, preferred: str) -> bool:
    """Every content word of the preferred term is in the alternative, by stem."""
    wanted = _stems(preferred)
    return bool(wanted) and wanted <= _stems(alternative)


def build(cache: Path) -> dict:
    rules = _load_rules()
    candidates = _onet_skills(cache, rules) + _esco_skills(cache, rules)

    # Each normalized key belongs to one skill: the first claimant, and O*NET's
    # tool names come before ESCO's broader concepts. A skill whose display
    # name was already taken by another skill is merged into that one's labels
    # rather than created twice.
    owner: dict[str, int] = {}
    merged: list[dict] = []
    for candidate in candidates:
        display_key = normalize(candidate["display"])
        if display_key in owner:
            target = merged[owner[display_key]]
            target["aliases"].extend(label for label in candidate["labels"] if normalize(label) not in owner)
            for label in candidate["labels"]:
                owner.setdefault(normalize(label), owner[display_key])
            continue
        index = len(merged)
        name = SkillNormalizer.normalize_canonical_name(candidate["display"])[:120]
        aliases = []
        for label in candidate["labels"]:
            key = normalize(label)
            if key in owner:
                continue
            owner[key] = index
            if key != display_key:
                aliases.append(label)
        merged.append(
            {
                "name": name,
                "display": candidate["display"],
                "category": candidate["category"],
                "source": candidate["source"],
                "reference": candidate["reference"],
                "aliases": aliases,
            }
        )

    catalog = {
        "version": CATALOG_VERSION,
        "attribution": [
            "ESCO v1.2, European Commission (https://esco.ec.europa.eu). Reuse authorised under Commission Decision 2011/833/EU.",
            "O*NET 31.0 Database, U.S. Department of Labor, Employment and Training Administration (USDOL/ETA). CC BY 4.0. "
            "Used under the CC BY 4.0 license; modified by StudentsCompass.",
        ],
        "skills": merged,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT_PATH, "wt", encoding="utf-8") as handle:
        json.dump(catalog, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    print(
        f"{len(merged)} skills, {sum(len(s['aliases']) for s in merged)} aliases → {OUTPUT_PATH.relative_to(ROOT_DIR)}"
    )
    return catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("step", choices=["fetch", "build"])
    parser.add_argument("--cache", type=Path, required=True, help="Where the downloaded sources live.")
    args = parser.parse_args()
    if args.step == "fetch":
        fetch(args.cache)
    else:
        build(args.cache)


if __name__ == "__main__":
    main()
