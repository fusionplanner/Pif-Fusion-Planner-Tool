# Infinite Fusion Planner

A free, unofficial team planner for **Pokémon Infinite Fusion** and **Infinite Fusion: Hoenn**.

**Use it here:** https://fusionplanner.github.io/Pif-Fusion-Planner-Tool/

Import your save (or add Pokémon by hand) and the planner tries every head/body pairing, then picks the best team of fusions, using each Pokémon once, and explains why.

## Features

- **Save import**: reads your party and every PC box straight from `File A/B/C.rxdata`, in your browser (nothing is uploaded). Already-fused Pokémon are split into their two parts.
- **Per-Pokémon settings**: level, IVs, nature and which evolution to plan as.
- **Game-accurate maths**: fusion stats, types, abilities, level `(2 × higher + lower) ÷ 3`, IVs (average of both parents) and natures (one of the two parents') follow the game's own code.
- **Team styles**: Best overall, Hard hitters, Bulky & safe, or Custom weights.
- **Moves you can actually use**: level-up moves at the fusion's level, plus TMs/HMs (with their numbers) and tutor moves either parent can learn.
- **Custom sprite credits**: shows which fusions have a hand-drawn sprite and who drew it, with an option to prefer them.
- **Saved lists** so you can come back to a set of Pokémon later.

It's a single static page (`index.html`) with no server, so it keeps working offline once loaded.

## Where are my saves?

`%APPDATA%\infinitefusion` (Hoenn: `%APPDATA%\infinitefusion-hoenn`). Paste that path into the file window's address bar and pick `File A`, `B` or `C.rxdata`.

## Updating after a game patch

The data is extracted from the game's own files. To rebuild you need Python 3 and the game installed:

```
python tools/extract_pif_data.py "C:\path\to\InfiniteFusion" tools/pif1.json
python tools/build_page.py "C:\path\to\InfiniteFusion" --site .
```

Then upload the new `index.html`.

## Credits

Pokémon Infinite Fusion and Infinite Fusion: Hoenn are made by **Chardub**, with maps by Kiwikelly and Payapon, music by Pory, and many sprite artists and contributors (see the game's `Credits.txt`). Custom sprite credits come from the game's `Sprite Credits.csv`. The game is built on Pokémon Essentials.

Pokémon and all related names are trademarks of Nintendo, Creatures Inc. and Game Freak.

Custom fusion sprites are hand-drawn by the Infinite Fusion community. The page shows them from the community's sprite repository and credits the artist who drew each one; it doesn't include any game files itself.

This is an unofficial fan tool. It is not affiliated with Nintendo, Game Freak, The Pokémon Company or the Infinite Fusion team.

This tool was created with the use of Claude AI Max. Please do not use it if you do not support AI.
