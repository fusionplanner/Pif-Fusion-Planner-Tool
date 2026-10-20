"""
extract_pif_data.py
Reads Pokemon Infinite Fusion's compiled data files (species, moves, types,
abilities), undoes the game's XOR scrambling, parses Ruby Marshal, and writes
a compact JSON file for the Fusion Planner page.

Usage:
    python -I extract_pif_data.py "<game folder>" <output.json>
"""
import json
import struct
import sys
from pathlib import Path

# From Data/Scripts/001_Technical/000_Encryption.rb
KEY = bytes([0x4A, 0x8F, 0x2C, 0xE1, 0x73, 0xB5, 0x96, 0x0D,
             0x5E, 0xA2, 0x3F, 0xC7, 0x81, 0x14, 0x6B, 0xD9])


def unscramble(raw: bytes) -> bytes:
    if raw[:2] == b"\x04\x08":          # already plain Marshal
        return raw
    return bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(raw))


class RubyObject:
    def __init__(self, cls):
        self.cls = cls
        self.ivars = {}

    def get(self, name, default=None):
        return self.ivars.get(name, default)


class Sym(str):
    """A Ruby symbol (kept distinct from strings)."""


class MarshalReader:
    """Minimal Ruby Marshal 4.8 reader covering what Essentials data uses."""

    def __init__(self, data: bytes):
        self.d = data
        self.p = 2
        self.syms = []
        self.objs = []

    def byte(self):
        b = self.d[self.p]
        self.p += 1
        return b

    def long(self):
        c = struct.unpack("b", bytes([self.byte()]))[0]
        if c == 0:
            return 0
        if 5 <= c <= 127:
            return c - 5
        if -128 <= c <= -5:
            return c + 5
        if c > 0:
            x = 0
            for i in range(c):
                x |= self.byte() << (8 * i)
            return x
        c = -c
        x = -1
        for i in range(c):
            x &= ~(0xFF << (8 * i))
            x |= self.byte() << (8 * i)
        return x

    def raw_bytes(self):
        n = self.long()
        s = self.d[self.p:self.p + n]
        self.p += n
        return s

    def symbol(self):
        t = chr(self.byte())
        if t == ":":
            s = Sym(self.raw_bytes().decode("utf-8", "replace"))
            self.syms.append(s)
            return s
        if t == ";":
            return self.syms[self.long()]
        raise ValueError(f"expected symbol, got {t!r} at {self.p}")

    def load(self):
        t = chr(self.byte())
        if t == "0":
            return None
        if t == "T":
            return True
        if t == "F":
            return False
        if t == "i":
            return self.long()
        if t == ":":
            s = Sym(self.raw_bytes().decode("utf-8", "replace"))
            self.syms.append(s)
            return s
        if t == ";":
            return self.syms[self.long()]
        if t == "@":
            return self.objs[self.long()]
        if t == "I":                       # object with ivars (usually a String w/ encoding)
            obj = self.load()
            n = self.long()
            for _ in range(n):
                self.symbol()
                self.load()
            return obj
        if t == '"':
            s = self.raw_bytes().decode("utf-8", "replace")
            self.objs.append(s)
            return s
        if t == "f":
            txt = self.raw_bytes().decode()
            v = {"inf": float("inf"), "-inf": float("-inf"), "nan": float("nan")}.get(txt)
            v = float(txt) if v is None else v
            self.objs.append(v)
            return v
        if t == "l":
            sign = chr(self.byte())
            n = self.long() * 2
            x = int.from_bytes(self.d[self.p:self.p + n], "little")
            self.p += n
            x = -x if sign == "-" else x
            self.objs.append(x)
            return x
        if t == "[":
            arr = []
            self.objs.append(arr)
            for _ in range(self.long()):
                arr.append(self.load())
            return arr
        if t in "{}":
            h = {}
            self.objs.append(h)
            for _ in range(self.long()):
                k = self.load()
                h[k if not isinstance(k, list) else tuple(k)] = self.load()
            if t == "}":
                self.load()                # default value
            return h
        if t == "o":
            obj = RubyObject(self.symbol())
            self.objs.append(obj)
            for _ in range(self.long()):
                name = self.symbol()
                obj.ivars[name] = self.load()
            return obj
        if t == "S":
            obj = RubyObject(self.symbol())
            self.objs.append(obj)
            for _ in range(self.long()):
                obj.ivars[self.symbol()] = self.load()
            return obj
        if t == "u":                       # _dump user data
            cls = self.symbol()
            data = self.raw_bytes()
            obj = RubyObject(cls)
            obj.ivars["_data"] = data
            self.objs.append(obj)
            return obj
        if t == "U":                       # marshal_dump
            cls = self.symbol()
            obj = RubyObject(cls)
            self.objs.append(obj)
            obj.ivars["_data"] = self.load()
            return obj
        if t in "eC":                      # extended / user subclass wrapper
            self.symbol()
            return self.load()
        if t == "c" or t == "m" or t == "M":
            name = self.raw_bytes().decode()
            self.objs.append(name)
            return name
        if t == "/":
            src = self.raw_bytes().decode("utf-8", "replace")
            self.byte()
            self.objs.append(src)
            return src
        raise ValueError(f"unsupported marshal type {t!r} at {self.p - 1}")


def load_dat(game: Path, name: str):
    raw = (game / "Data" / name).read_bytes()
    return MarshalReader(unscramble(raw)).load()


def iv(obj, name, default=None):
    return obj.get("@" + name, default) if isinstance(obj, RubyObject) else default


def main():
    game = Path(sys.argv[1])
    out = Path(sys.argv[2])

    types_raw = load_dat(game, "types.dat")
    moves_raw = load_dat(game, "moves.dat")
    abil_raw = load_dat(game, "abilities.dat")
    species_raw = load_dat(game, "species.dat")

    types = {}
    for k, t in types_raw.items():
        if isinstance(k, int) or iv(t, "pseudo_type"):
            continue
        types[str(k)] = {
            "name": iv(t, "real_name"),
            "weak": [str(x) for x in iv(t, "weaknesses", [])],
            "resist": [str(x) for x in iv(t, "resistances", [])],
            "immune": [str(x) for x in iv(t, "immunities", [])],
            "special": bool(iv(t, "special_type")),
        }

    moves = {}
    for k, m in moves_raw.items():
        if isinstance(k, int):
            continue
        moves[str(k)] = {
            "name": iv(m, "real_name"),
            "type": str(iv(m, "type")),
            "cat": iv(m, "category"),          # 0 physical, 1 special, 2 status
            "pow": iv(m, "base_damage", 0),
            "acc": iv(m, "accuracy", 0),
            "fn": str(iv(m, "function_code", "")),
            "pri": iv(m, "priority", 0),
        }

    abilities = {}
    for k, a in abil_raw.items():
        if isinstance(k, int):
            continue
        abilities[str(k)] = {"name": iv(a, "real_name"), "desc": iv(a, "real_description")}

    species = []
    for k, s in species_raw.items():
        if isinstance(k, int) or iv(s, "form", 0) != 0:
            continue
        num = iv(s, "id_number")
        if not isinstance(num, int) or num <= 0:
            continue
        stats = iv(s, "base_stats", {})
        evos = []
        for e in iv(s, "evolutions", []) or []:
            # [species, method, parameter, is_prevolution]
            if len(e) >= 4 and e[3]:
                continue
            param = e[2] if len(e) > 2 else None
            evos.append([str(e[0]), str(e[1]) if len(e) > 1 else "", param if isinstance(param, int) else (str(param) if param is not None else None)])
        species.append({
            "id": str(k),
            "num": num,
            "name": iv(s, "real_name"),
            "t1": str(iv(s, "type1")),
            "t2": str(iv(s, "type2") or iv(s, "type1")),
            "hp": stats.get("HP", 1), "atk": stats.get("ATTACK", 1), "def": stats.get("DEFENSE", 1),
            "spa": stats.get("SPECIAL_ATTACK", 1), "spd": stats.get("SPECIAL_DEFENSE", 1),
            "spe": stats.get("SPEED", 1),
            "ab": [str(x) for x in iv(s, "abilities", []) or []],
            "hab": [str(x) for x in iv(s, "hidden_abilities", []) or []],
            "lv": [[lvl, str(mv)] for lvl, mv in (iv(s, "moves", []) or [])],
            "tm": [str(x) for x in iv(s, "tutor_moves", []) or []],
            "egg": [str(x) for x in iv(s, "egg_moves", []) or []],
            "evo": evos,
        })
    species.sort(key=lambda x: x["num"])

    # TM/HM items -> the move each one teaches
    tms = {}
    for k, it in load_dat(game, "items.dat").items():
        if isinstance(k, int) or not iv(it, "move"):
            continue
        tms.setdefault(str(iv(it, "move")), []).append(str(iv(it, "real_name")))

    out.write_text(json.dumps({"types": types, "moves": moves, "abilities": abilities,
                               "species": species, "tms": tms}, separators=(",", ":")), encoding="utf-8")
    print(f"{game.name}: {len(species)} species, {len(moves)} moves, "
          f"{len(abilities)} abilities, {len(types)} types -> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
