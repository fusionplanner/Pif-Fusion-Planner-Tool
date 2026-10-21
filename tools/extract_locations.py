"""
extract_locations.py
Scans the game's map events to find where each TM/HM is obtained (item ball, gift, shop)
and where move tutors are, for Pokemon Infinite Fusion (and Hoenn, if installed next to it).

Usage:
    python -I extract_locations.py "<game folder>" <output.json>
The output is cached by build_page.py; rerun after a game update.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_pif_data import MarshalReader, unscramble  # noqa: E402

ITEM = r"(?:PBItems::|:)((?:TM|HM)\d{2,3})\b"
MOVE = r"(?:PBMoves::|:)([A-Z0-9_]+)"
RX_BALL = re.compile(r"pbItemBall\(\s*" + ITEM)
RX_GIFT = re.compile(r"pbReceiveItem\(\s*" + ITEM)
RX_MART = re.compile(r"pbPokemonMart\(\s*\[(.*?)\]", re.S)
RX_MART_ITEM = re.compile(ITEM)
RX_TUTOR = re.compile(r"pbMoveTutorChoose\(\s*" + MOVE)
GENERIC = {"pokemon center", "pokémon center", "pok�mon center", "pokemart", "poke mart", "pokémart", "house",
           "harbour", "harbor", "gym", "inside", "interior", "building", "lab", "b1f", "1f", "2f", "3f"}


def load(p: Path):
    return MarshalReader(unscramble(p.read_bytes())).load()


def scan_game(folder: Path, label: str, found: dict):
    data = folder / "Data"
    infos = load(data / "MapInfos.rxdata")
    names = {k: (v.get("@name") or f"Map {k}") for k, v in infos.items()}
    parents = {k: v.get("@parent_id") for k, v in infos.items()}

    def place(mid):
        n = names.get(mid, f"Map {mid}").replace("�", "é")
        par = parents.get(mid)
        if n.lower().strip() in GENERIC or n.lower().endswith((" gym", " house", "center")):
            if par and par in names and names[par] != n and names[par].lower() not in n.lower():
                return f"{n} ({names[par]})".replace("�", "é")
        return n

    def add(kind, key, how, where):
        lst = found.setdefault(kind, {}).setdefault(key, [])
        entry = {"game": label, "how": how, "where": where}
        if entry not in lst:
            lst.append(entry)

    for mp in sorted(data.glob("Map[0-9][0-9][0-9].rxdata")):
        mid = int(mp.stem[3:])
        try:
            m = load(mp)
        except Exception:
            continue
        where = place(mid)
        for ev in (m.get("@events") or {}).values():
            for page in ev.get("@pages") or []:
                # join each script command with its continuation lines (code 655)
                scripts, cur = [], None
                for cmd in page.get("@list") or []:
                    code, params = cmd.get("@code"), cmd.get("@parameters") or []
                    text = " ".join(str(p) for p in params if isinstance(p, str))
                    if code in (355, 111):
                        if cur is not None:
                            scripts.append(cur)
                        cur = text
                    elif code == 655 and cur is not None:
                        cur += "\n" + text
                    else:
                        if cur is not None:
                            scripts.append(cur)
                            cur = None
                if cur is not None:
                    scripts.append(cur)
                for s in scripts:
                    for it in RX_BALL.findall(s):
                        add("tm", it, "item", where)
                    for it in RX_GIFT.findall(s):
                        add("tm", it, "gift", where)
                    for lst in RX_MART.findall(s):
                        for it in RX_MART_ITEM.findall(lst):
                            add("tm", it, "shop", where)
                    for mv in RX_TUTOR.findall(s):
                        add("tutor", mv, "tutor", where)


def main():
    game = Path(sys.argv[1])
    out = Path(sys.argv[2])
    found = {}
    scan_game(game, "PIF", found)
    hoenn = game.parent / "InfiniteFusion2"
    if hoenn.exists() and hoenn.resolve() != game.resolve():
        scan_game(hoenn, "Hoenn", found)
    out.write_text(json.dumps(found, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"Locations: {len(found.get('tm', {}))} TMs/HMs, {len(found.get('tutor', {}))} tutor moves -> {out.name}")


if __name__ == "__main__":
    main()
