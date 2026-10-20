"""
build_page.py
Packs the extracted game data (pif1.json) plus the game's fusion-name table
into a compact form and bakes it into planner_template.html, producing
"Fusion Planner.html" (a single self-contained page) plus a hostable
index.html.

Usage:
    python -I build_page.py "<game folder>"                 # writes ./github/index.html (+ tools/)
    python -I build_page.py "<game folder>" --site <folder>  # writes <folder>/index.html only
    add --offline to skip downloading the latest sprite credits and use the game's own copies
Run extract_pif_data.py first; it writes pif1.json next to this script.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TYPES = ["NORMAL", "FIGHTING", "FLYING", "POISON", "GROUND", "ROCK", "BUG", "GHOST", "STEEL",
         "FIRE", "WATER", "GRASS", "ELECTRIC", "PSYCHIC", "ICE", "DRAGON", "DARK", "FAIRY"]

# Moves that look strong on paper but are bad picks for a normal moveset
# (recharge, self-KO, charge turn, conditional or gimmick damage).
BAD_MOVES = {
    "HYPERBEAM", "GIGAIMPACT", "BLASTBURN", "HYDROCANNON", "FRENZYPLANT", "ROCKWRECKER",
    "ROAROFTIME", "PRISMATICLASER", "METEORASSAULT", "ETERNABEAM", "EXPLOSION", "SELFDESTRUCT",
    "MISTYEXPLOSION", "SOLARBEAM", "SOLARBLADE", "SKYATTACK", "RAZORWIND", "SKULLBASH",
    "FOCUSPUNCH", "DREAMEATER", "FUTURESIGHT", "DOOMDESIRE", "LASTRESORT", "SYNCHRONOISE",
    "BELCH", "MINDBLOWN", "STEELBEAM", "FLING", "NATURALGIFT", "SNORE", "SPITUP", "TRUMPCARD",
    "SHELLTRAP", "BURNUP", "METEORBEAM", "SKYDROP", "BIDE", "FREEZESHOCK", "ICEBURN",
    "HYPERSPACEFURY", "HYPERSPACEHOLE", "DYNAMAXCANNON", "BEHEMOTHBLADE", "BEHEMOTHBASH",
}
# Two-turn moves: usable, but weaker than their power suggests.
SLOW_MOVES = {"FLY", "DIG", "DIVE", "BOUNCE", "SHADOWFORCE", "PHANTOMFORCE"}


def parse_split_names(game: Path):
    src = (game / "Data/Scripts/052_InfiniteFusion/Fusion/Data/SplitNames.rb").read_text(encoding="utf-8")
    block = src.split("SPLIT_NAMES = [", 1)[1].split("\n  ]", 1)[0]
    pairs = re.findall(r'\[\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*\]', block)
    mapping_block = src.split("NAT_DEX_MAPPING = {", 1)[1].split("}", 1)[0]
    mapping = {int(a): int(b) for a, b in re.findall(r"(\d+)\s*=>\s*(\d+)", mapping_block)}
    return pairs, mapping


SITE_URL = "https://fusionplanner.github.io/Pif-Fusion-Planner-Tool/"  # public address (override with --url)
CREDITS_URL = "https://infinitefusion.net/customsprites/Sprite_Credits.csv"
SPRITE_LIST_URL = "https://raw.githubusercontent.com/infinitefusion/pif-downloadables/refs/heads/master/CUSTOM_SPRITES"


def _fetch_text(url: str):
    import urllib.request
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "pif-fusion-planner-build"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  (couldn't download {url}: {e})")
        return None


def pack_sprite_credits(game: Path, max_num: int = 576, offline: bool = False) -> str:
    """Custom fusion sprites ("head.body[alt letter]", artist, main/alt/temp, tags), newest source first:
    the live credits file the game downloads, the game's updated copy (Data/sprites/Sprite_Credits.csv),
    then the old bundled Data/Sprite Credits.csv. Sprites in the game's file list but missing from the
    credits are added as "unknown".
    Returns base64(gzip(JSON)) of {"a": [artists], "d": {head: "body.v~v~v,..."}} where each version v is
    "<letter>[!]:<artist index>" ("!" = not in the old Bitbucket copy, load it from the game's sprite sheet;
    main version first; numbers in base 36)."""
    import base64, csv, gzip, io
    pat = re.compile(r"^(\d+)\.(\d+)([a-z]*)$")
    old_path = game / "Data" / "Sprite Credits.csv"
    new_path = game / "Data" / "sprites" / "Sprite_Credits.csv"
    list_path = game / "Data" / "sprites" / "CUSTOM_SPRITES"

    text, source = (None, None) if offline else (_fetch_text(CREDITS_URL), "live server")
    if text is None and new_path.exists():
        text, source = new_path.read_text(encoding="utf-8", errors="replace"), str(new_path.relative_to(game))
    if text is None and old_path.exists():
        text, source = old_path.read_text(encoding="utf-8", errors="replace"), str(old_path.relative_to(game))
    if text is None:
        return ""

    # Sprites in the old bundled file are (almost all) on the Bitbucket mirror; newer ones are not
    on_bitbucket = set()
    if old_path.exists():
        with open(old_path, encoding="utf-8", errors="replace", newline="") as fh:
            on_bitbucket = {row[0].strip() for row in csv.reader(fh) if row}

    pairs = {}

    def add(sid, artist, kind):
        """Adds one sprite version; returns True if it was new."""
        m = pat.match(sid)
        if not m:
            return False
        head, body, letter = int(m.group(1)), int(m.group(2)), m.group(3)
        if not (1 <= head <= max_num and 1 <= body <= max_num):
            return False
        versions = pairs.setdefault((head, body), [])
        if any(v[0] == letter for v in versions):
            return False
        versions.append((letter, artist, kind == "main", sid not in on_bitbucket))
        return True

    for row in csv.reader(io.StringIO(text)):
        if row:
            add(row[0].strip(), (row[1] if len(row) > 1 else "").strip() or "unknown",
                (row[2] if len(row) > 2 else "").strip())
    listed = None if offline else _fetch_text(SPRITE_LIST_URL)
    if listed is None and list_path.exists():
        listed = list_path.read_text(encoding="utf-8", errors="replace")
    extra = 0
    for line in (listed or "").splitlines():
        extra += add(line.strip().removesuffix(".png"), "unknown", "")
    print(f"Sprite credits from {source}" + (f" (+{extra} listed sprites without credits)" if extra else ""))
    counts = {}
    for versions in pairs.values():
        for _, a, _, _ in versions:
            counts[a] = counts.get(a, 0) + 1
    artists = sorted(counts, key=lambda a: (-counts[a], a.lower()))
    aidx = {a: i for i, a in enumerate(artists)}
    by_head = {}
    sheet_only = 0
    for (head, body), versions in sorted(pairs.items()):
        # main version first, then the rest by letter ("" before "a" before "b")
        versions.sort(key=lambda v: (not v[2], len(v[0]), v[0]))
        enc = "~".join(f"{letter}{'!' if sheet else ''}:{_b36(aidx[a])}" for letter, a, _, sheet in versions)
        sheet_only += sum(1 for v in versions if v[3])
        by_head.setdefault(head, []).append(f"{_b36(body)}.{enc}")
    blob = json.dumps({"a": artists, "d": {str(h): ",".join(v) for h, v in by_head.items()}},
                      separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    total = sum(len(v) for v in pairs.values())
    print(f"Sprite credits: {total} sprites on {len(pairs)} fusions by {len(artists)} artists "
          f"({sheet_only} newer ones load from the game's sprite sheets)")
    return base64.b64encode(gzip.compress(blob, 9)).decode("ascii")


def _b36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = digits[r] + out
        if n == 0:
            return out


def main():
    game = Path(sys.argv[1])
    site_arg = sys.argv[sys.argv.index("--site") + 1] if "--site" in sys.argv else None
    raw = json.loads((HERE / "pif1.json").read_text(encoding="utf-8"))
    split_names, nat_map = parse_split_names(game)

    # Type chart: chart[attacking][defending]
    tidx = {t: i for i, t in enumerate(TYPES)}
    chart = [[1] * len(TYPES) for _ in TYPES]
    for d, info in raw["types"].items():
        if d not in tidx:
            continue
        for a in info["weak"]:
            if a in tidx:
                chart[tidx[a]][tidx[d]] = 2
        for a in info["resist"]:
            if a in tidx:
                chart[tidx[a]][tidx[d]] = 0.5
        for a in info["immune"]:
            if a in tidx:
                chart[tidx[a]][tidx[d]] = 0

    species = [s for s in raw["species"] if 1 <= s["num"] <= 576]
    sid = {s["id"]: s for s in species}

    # Damaging moves only (status moves don't affect the rankings)
    move_ids = []
    move_index = {}
    moves_out = []

    def mv(mid):
        m = raw["moves"].get(mid)
        if not m or m["cat"] == 2 or m["pow"] <= 1 or m["type"] not in tidx:
            return None
        if mid not in move_index:
            move_index[mid] = len(moves_out)
            moves_out.append([m["name"], tidx[m["type"]], m["cat"], m["pow"], m["acc"],
                              1 if mid in BAD_MOVES else 2 if mid in SLOW_MOVES else 0, m["pri"]])
            move_ids.append(mid)
        return move_index[mid]

    abil_used = {}

    def ab(aid):
        if aid not in abil_used:
            a = raw["abilities"].get(aid, {"name": aid.title(), "desc": ""})
            abil_used[aid] = [a["name"], a.get("desc") or ""]
        return aid

    out_species = []
    for s in species:
        # level-up moves keep the lowest level they're learned at
        lv_map = {}
        for lvl, m in s["lv"]:
            i = mv(m)
            if i is not None and (i not in lv_map or lvl < lv_map[i]):
                lv_map[i] = lvl
        lv = sorted([[i, l] for i, l in lv_map.items()], key=lambda x: (x[1], x[0]))
        tm = sorted({i for m in s["tm"] if (i := mv(m)) is not None} - set(lv_map))
        egg = sorted({i for m in s["egg"] if (i := mv(m)) is not None} - set(lv_map) - set(tm))
        nat = nat_map.get(s["num"], s["num"])
        pre, suf = split_names[nat] if nat < len(split_names) else (s["name"], s["name"].lower())
        # [target dex number, method, level (or null when not level-based), item/other parameter]
        evo = [[sid[e[0]]["num"], e[1], e[2] if isinstance(e[2], int) and "Level" in e[1] else None,
                e[2] if isinstance(e[2], str) else None]
               for e in s["evo"] if e[0] in sid]
        out_species.append([
            s["num"], s["name"], tidx[s["t1"]], tidx[s["t2"]],
            s["hp"], s["atk"], s["def"], s["spa"], s["spd"], s["spe"],
            [ab(a) for a in s["ab"]], [ab(a) for a in s["hab"]],
            lv, tm, egg, evo, pre, suf, s["id"],
        ])

    # TM/HM names for the damaging moves we kept
    tm_names = {}
    for mid, names in raw.get("tms", {}).items():
        if mid in move_index:
            tm_names[move_index[mid]] = "/".join(sorted(names))

    data = {"types": TYPES, "chart": chart, "moves": moves_out, "abilities": abil_used,
            "species": out_species, "tmNames": tm_names}
    payload = json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")

    settings = (game / "Data/Scripts/001_Settings.rb").read_text(encoding="utf-8")
    m = re.search(r'GAME_VERSION_NUMBER\s*=\s*"([^"]+)"', settings)
    version = m.group(1) if m else "unknown"

    template = (HERE / "planner_template.html").read_text(encoding="utf-8")
    page = (template.replace("__PIF_VERSION__", version)
                    .replace("__PIF_SPRITES__", pack_sprite_credits(game, offline="--offline" in sys.argv))
                    .replace("__PIF_DATA__", payload))
    out = HERE / "Fusion Planner.html"
    out.write_text(page, encoding="utf-8")

    # Ready-to-host copy: a full HTML document named index.html, with link-preview and search tags
    site = Path(site_arg) if site_arg else HERE / "github"
    site.mkdir(parents=True, exist_ok=True)
    url = (sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else SITE_URL).rstrip("/") + "/"
    title = "Infinite Fusion Planner: team builder for Pokémon Infinite Fusion"
    desc = ("Import your Pokémon Infinite Fusion save and get the strongest team of fusions, with reasons. "
            "Every head/body pairing scored on stats, typing and moves, with natures, IVs, TMs and custom sprite credits.")
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "WebApplication", "name": "Infinite Fusion Planner",
        "url": url, "description": desc, "applicationCategory": "GameApplication", "operatingSystem": "Any",
        "browserRequirements": "Requires JavaScript", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "image": url + "og-image.png",
    }, ensure_ascii=False)
    head = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            f'<meta name="description" content="{desc}">\n'
            f'<link rel="canonical" href="{url}">\n'
            '<meta name="theme-color" content="#0e1514">\n'
            '<meta property="og:type" content="website">\n'
            '<meta property="og:site_name" content="Infinite Fusion Planner">\n'
            f'<meta property="og:title" content="{title}">\n'
            f'<meta property="og:description" content="{desc}">\n'
            f'<meta property="og:url" content="{url}">\n'
            f'<meta property="og:image" content="{url}og-image.png">\n'
            '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            '<meta property="og:image:alt" content="Infinite Fusion Planner: import your save, get the strongest team of fusions.">\n'
            '<meta name="twitter:card" content="summary_large_image">\n'
            f'<meta name="twitter:title" content="{title}">\n'
            f'<meta name="twitter:description" content="{desc}">\n'
            f'<meta name="twitter:image" content="{url}og-image.png">\n'
            f'<script type="application/ld+json">{ld}</script>\n')
    (site / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {url}sitemap.xml\n", encoding="utf-8")
    (site / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{url}</loc><changefreq>weekly</changefreq></url>\n</urlset>\n', encoding="utf-8")
    (site / "index.html").write_text(head + page.replace("<style>", "<style>\nhtml{color-scheme:light}body{margin:0}\n", 1)
                                     .replace('<div class="wrap">', '</head>\n<body>\n<div class="wrap">', 1)
                                     + "\n</body>\n</html>\n", encoding="utf-8")
    # Keep the build tools next to the site so the repo can rebuild itself
    if not site_arg:
        tools = site / "tools"
        tools.mkdir(exist_ok=True)
        for name in ("extract_pif_data.py", "build_page.py", "planner_template.html", "og_card.html"):
            (tools / name).write_bytes((HERE / name).read_bytes())
    print(f"Game {version}: {len(out_species)} species, {len(moves_out)} damaging moves, {len(abil_used)} abilities "
          f"-> {out.name} ({out.stat().st_size // 1024} KB) and {site / 'index.html'}")


if __name__ == "__main__":
    main()
