#!/usr/bin/env python3
"""
Outfit Tester — dialogue terminal
----------------------------------
Calcule le nombre de combinaisons de tenues possibles selon le contexte
(dehors / palier de température : chaud, medium, froid), propose des tenues
aléatoires jamais rejouées, demande une note et les éléments qui ne vont pas
ensemble, puis sauvegarde tout proprement dans un fichier JSON.
"""

import itertools
import json
import os
import random
import shutil
import sys
from datetime import datetime
from pathlib import Path

# ----------------------------------------------------------------------
# Données
# ----------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

# Garde-robe personnelle (ignorée par git) ; à défaut, l'exemple versionné.
WARDROBE_FILE = BASE_DIR / "wardrobe.json"
WARDROBE_EXAMPLE_FILE = BASE_DIR / "wardrobe.example.json"
REQUIRED_WARDROBE_KEYS = ('shirts', 't-shirts', 'trousers', 'shorts', 'shoes', 'coats', 'pull')


def load_wardrobe():
    path = WARDROBE_FILE if WARDROBE_FILE.exists() else WARDROBE_EXAMPLE_FILE
    try:
        with path.open('r', encoding='utf-8') as f:
            wardrobe = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        sys.exit(f"Garde-robe illisible ({path.name}) : {exc}")
    missing = [k for k in REQUIRED_WARDROBE_KEYS if k not in wardrobe]
    if missing:
        sys.exit(f"Garde-robe incomplète ({path.name}), clé(s) manquante(s) : {', '.join(missing)}")
    wardrobe.setdefault('no_layer_tshirts', [])  # trop chargés pour aller sous une chemise
    wardrobe.setdefault('heavy_coats', [])       # manteaux réservés au froid
    return wardrobe


WARDROBE = load_wardrobe()

# Ancré sur le dossier du script : indépendant du répertoire courant.
HISTORY_FILE = BASE_DIR / "historique_outfits.json"

# ----------------------------------------------------------------------
# Couleurs terminal (ANSI, sans dépendance)
# ----------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RED = "\033[91m"


WIDTH = 56


def line(char="─", width=WIDTH, color=DIM):
    print(f"{color}{char * width}{RESET}")


def title(text, width=WIDTH):
    line("═", width)
    print(f"{BOLD}{CYAN}{text.center(width)}{RESET}")
    line("═", width)


# ----------------------------------------------------------------------
# Génération des combinaisons possibles
# ----------------------------------------------------------------------

def generate_tops():
    """Retourne la liste des tops possibles (labels)."""
    tops = []
    tops.extend(WARDROBE['shirts'])
    tops.extend(WARDROBE['t-shirts'])

    layerable = [t for t in WARDROBE['t-shirts'] if t not in WARDROBE['no_layer_tshirts']]
    for s in WARDROBE['shirts']:
        for t in layerable:
            tops.append(f'{s} + {t}')

    return tops


def generate_bottoms(temp):
    if temp == 'chaud':
        return list(WARDROBE['trousers'] + WARDROBE['shorts'])
    return list(WARDROBE['trousers'])  # medium et froid : pas de short


def generate_pulls(temp):
    if temp == 'chaud':
        return [None]
    return WARDROBE['pull'] + [None]  # optionnel en medium et froid


def generate_coats(outdoor, temp):
    if not outdoor or temp == 'chaud':
        return [None]
    coats = list(WARDROBE['coats'])
    if temp == 'medium':
        coats = [c for c in coats if c not in WARDROBE['heavy_coats']]  # réservés au froid
    return coats + [None]  # même dehors, on peut sortir sans manteau


def generate_all_combos(outdoor, temp, forbidden_pairs=None):
    """Génère toutes les tenues distinctes possibles pour ce contexte (outdoor/temp),
    en excluant celles qui contiennent une paire d'éléments jugée incompatible."""
    forbidden_pairs = forbidden_pairs or set()

    tops = generate_tops()
    bottoms = generate_bottoms(temp)
    shoes_list = WARDROBE['shoes']
    pulls = generate_pulls(temp)
    coats = generate_coats(outdoor, temp)

    combos = (
        {'top': top, 'bottom': bottom, 'shoes': shoes, 'pull': pull, 'coat': coat}
        for top, bottom, shoes, pull, coat
        in itertools.product(tops, bottoms, shoes_list, pulls, coats)
    )
    return [c for c in combos if is_combo_allowed(c, forbidden_pairs)]


def expand_top_value(value):
    """Décompose un 'Haut' en ses composants élémentaires : une tenue en couche
    ('chemise + t-shirt') est en réalité 2 éléments distincts, chacun pouvant
    porter sa propre règle d'incompatibilité."""
    if ' + ' in value:
        shirt_part, tshirt_part = value.split(' + ', 1)
        return [('shirt', shirt_part), ('tshirt', tshirt_part)]
    if value in WARDROBE['shirts']:
        return [('shirt', value)]
    return [('tshirt', value)]


def combo_items(combo):
    """Décompose une tenue en éléments élémentaires (Haut éclaté en
    chemise/t-shirt + les autres champs), pour vérifier les incompatibilités."""
    items = list(expand_top_value(combo['top'])) if combo.get('top') else []
    for field in ('bottom', 'shoes', 'pull', 'coat'):
        value = combo.get(field)
        if value:
            items.append((field, value))
    return items


def is_combo_allowed(combo, forbidden_pairs):
    """Vrai si aucune paire d'éléments élémentaires de cette tenue n'est
    marquée incompatible."""
    return not any(
        frozenset(pair) in forbidden_pairs
        for pair in itertools.combinations(combo_items(combo), 2)
    )


def signature_of(combo):
    return "|".join([
        combo['top'], combo['bottom'], combo['shoes'],
        combo.get('pull') or '-', combo.get('coat') or '-',
    ])


# ----------------------------------------------------------------------
# Historique (fichier JSON)
# ----------------------------------------------------------------------

def load_history():
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        # Ne jamais écraser silencieusement un historique existant : on le met
        # de côté avant que la prochaine sauvegarde ne le remplace.
        backup = HISTORY_FILE.with_name(
            f"{HISTORY_FILE.stem}.corrupt-{datetime.now():%Y%m%d-%H%M%S}{HISTORY_FILE.suffix}")
        try:
            shutil.copy2(HISTORY_FILE, backup)
        except OSError:
            sys.exit(f"{RED}Historique illisible ({exc}) et impossible à sauvegarder : "
                     f"arrêt pour ne pas le perdre.{RESET}")
        print(f"{RED}Attention : historique illisible ({exc}). "
              f"Copie conservée dans {backup.name}, un nouvel historique sera créé.{RESET}")
        return []


def save_history(history):
    """Écriture atomique : on écrit dans un fichier temporaire puis on le
    renomme, pour ne jamais laisser un JSON tronqué en cas d'interruption."""
    tmp = HISTORY_FILE.with_suffix(HISTORY_FILE.suffix + '.tmp')
    with tmp.open('w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, HISTORY_FILE)


def normalize_context(entry):
    """Compatibilité avec d'anciennes entrées qui utilisaient 'cold' (bool)
    au lieu de 'temp' (3 paliers). L'ancien « pas froid » autorisait les pulls,
    il correspond donc au palier 'medium' (le palier 'chaud' les exclut)."""
    context = entry.get('context', {})
    if 'temp' not in context and 'cold' in context:
        return {**context, 'temp': 'froid' if context['cold'] else 'medium'}
    return context


def matches_context(entry, outdoor=None, temp=None):
    """Vrai si l'entrée correspond au contexte (None = pas de filtre)."""
    ctx = normalize_context(entry)
    return ((outdoor is None or ctx.get('outdoor') == outdoor)
            and (temp is None or ctx.get('temp') == temp))


def already_tested_signatures(history, outdoor, temp):
    return {e['signature'] for e in history if matches_context(e, outdoor, temp)}


def elementary_mismatch_keys(mismatch_items):
    """(field, value) élémentaires d'une liste de mismatch_items. Les anciennes
    entrées stockaient un Haut en couche non éclaté (field='top') : on l'éclate
    ici pour que la règle porte bien sur ses deux composants."""
    keys = []
    for item in mismatch_items:
        if item['field'] == 'top':
            keys.extend(expand_top_value(item['value']))
        else:
            keys.append((item['field'], item['value']))
    return keys


def mismatch_pairs(mismatch_items):
    """Paires incompatibles déduites d'une tenue : si 3 éléments ou plus sont
    signalés, chaque paire parmi eux est considérée incompatible."""
    keys = elementary_mismatch_keys(mismatch_items)
    return {frozenset(pair) for pair in itertools.combinations(keys, 2)}


def compute_forbidden_pairs(history):
    """Reconstruit, à partir de tout l'historique (tous contextes confondus),
    l'ensemble des paires d'éléments jugées incompatibles."""
    forbidden = set()
    for entry in history:
        forbidden |= mismatch_pairs(entry.get('mismatch_items') or [])
    return forbidden


# ----------------------------------------------------------------------
# Interactions utilisateur
# ----------------------------------------------------------------------

def ask_yes_no(question):
    while True:
        rep = input(f"{question} {DIM}(o/n){RESET} : ").strip().lower()
        if rep in ('o', 'oui', 'y', 'yes'):
            return True
        if rep in ('n', 'non', 'no'):
            return False
        print(f"{RED}Réponse invalide, tape 'o' ou 'n'.{RESET}")


def ask_temperature():
    options = {'1': 'froid', '2': 'medium', '3': 'chaud'}
    print(f"{YELLOW}Quel temps fait-il ?{RESET}")
    print("  [1] Froid    (gros manteau, pull...)")
    print("  [2] Medium   (pull, éventuellement veste légère)")
    print("  [3] Chaud    (short possible, ni pull ni manteau)")
    while True:
        rep = input("> ").strip()
        if rep in options:
            return options[rep]
        print(f"{RED}Entrée invalide (1, 2 ou 3).{RESET}")


def display_outfit(combo, index, remaining_after):
    title(f"TENUE #{index}")
    fields = [
        ("top", "Haut", combo['top']),
        ("bottom", "Bas", combo['bottom']),
        ("shoes", "Chaussures", combo['shoes']),
        ("pull", "Pull", combo.get('pull')),
        ("coat", "Manteau", combo.get('coat')),
    ]
    numbered = []
    n = 1
    for field, label, value in fields:
        if value:
            print(f"  {GREEN}{label:<12}{RESET}: {value}   {DIM}[{n}]{RESET}")
            numbered.append((n, field, label, value))
            n += 1
    line()
    print(f"{DIM}Combinaisons restantes après celle-ci : {remaining_after}{RESET}")
    line()
    return numbered


def ask_rank():
    while True:
        rep = input(f"{YELLOW}Note cette tenue de 1 (nul) à 5 (excellent), ou 'q' pour quitter{RESET} : ").strip().lower()
        if rep == 'q':
            return None
        if rep.isdigit() and 1 <= int(rep) <= 5:
            return int(rep)
        print(f"{RED}Entrée invalide (1 à 5, ou 'q').{RESET}")


def ask_mismatches(numbered_items):
    if not numbered_items:
        return []
    print(f"{MAGENTA}Quels éléments ne vont pas ensemble ?{RESET} "
          f"{DIM}(numéros séparés par des virgules, Entrée si rien à signaler){RESET}")
    rep = input("> ").strip()
    if not rep:
        return []

    lookup = {num: (field, label, value) for num, field, label, value in numbered_items}
    selected = []
    ignored = []
    for part in filter(None, (p.strip() for p in rep.split(','))):
        if part.isdigit() and int(part) in lookup:
            selected.append(lookup[int(part)])
        else:
            ignored.append(part)
    if ignored:
        print(f"{DIM}Ignoré(s), numéro(s) invalide(s) : {', '.join(ignored)}{RESET}")

    # un "Haut" en couche (chemise + t-shirt) est éclaté en 2 éléments distincts :
    # le cocher seul suffit donc à former une règle entre ses 2 composants.
    expanded = []
    for field, label, value in selected:
        if field == 'top':
            parts = expand_top_value(value)
            if len(parts) == 2:
                (f1, v1), (f2, v2) = parts
                expanded.append({"field": f1, "label": f"{label} (chemise)", "value": v1})
                expanded.append({"field": f2, "label": f"{label} (t-shirt)", "value": v2})
            else:
                sub_field, sub_value = parts[0]
                expanded.append({"field": sub_field, "label": label, "value": sub_value})
        else:
            expanded.append({"field": field, "label": label, "value": value})

    if len(expanded) == 1:
        print(f"{DIM}Un seul élément signalé : aucune règle d'incompatibilité créée "
              f"(il en faut au moins deux).{RESET}")

    return expanded


# ----------------------------------------------------------------------
# Boucle principale
# ----------------------------------------------------------------------

def main():
    title("OUTFIT TESTER")
    print(f"{DIM}Réponds aux quelques questions, puis note les tenues proposées.{RESET}\n")

    outdoor = ask_yes_no("Sors-tu dehors aujourd'hui ?")
    temp = ask_temperature()

    history = load_history()
    forbidden_pairs = compute_forbidden_pairs(history)

    all_combos = generate_all_combos(outdoor, temp, forbidden_pairs)
    total = len(all_combos)

    # seules les tenues testées encore autorisées comptent : celles écartées
    # depuis par une règle ne font plus partie des combinaisons possibles.
    tested = already_tested_signatures(history, outdoor, temp)
    remaining = [c for c in all_combos if signature_of(c) not in tested]
    tested_count = total - len(remaining)

    print()
    line("═")
    print(f"{BOLD}Règles d'incompatibilité actives         : {MAGENTA}{len(forbidden_pairs)}{RESET}")
    print(f"{BOLD}Combinaisons possibles pour ce contexte : {CYAN}{total}{RESET}")
    print(f"{BOLD}Déjà testées                             : {YELLOW}{tested_count}{RESET}")
    print(f"{BOLD}Restantes à découvrir                    : {GREEN}{len(remaining)}{RESET}")
    line("═")
    print()

    if not remaining:
        print(f"{GREEN}Toutes les combinaisons pour ce contexte ont déjà été testées !{RESET}")
        return

    session_count = 0

    while remaining:
        combo = remaining.pop(random.randrange(len(remaining)))

        numbered_items = display_outfit(combo, session_count + 1, len(remaining))

        rank = ask_rank()
        if rank is None:
            print(f"{DIM}Session arrêtée sans sauvegarder cette dernière tenue.{RESET}")
            break

        mismatches = ask_mismatches(numbered_items)
        mismatch_labels = [f"{m['label']}: {m['value']}" for m in mismatches]

        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "context": {"outdoor": outdoor, "temp": temp},
            "signature": signature_of(combo),
            "outfit": combo,
            "rank": rank,
            "mismatches": mismatch_labels,
            "mismatch_items": mismatches,
        }
        history.append(entry)
        save_history(history)
        session_count += 1

        print(f"{GREEN}Tenue enregistrée (note : {rank}/5).{RESET}")

        # si cette tenue crée de nouvelles règles d'incompatibilité, on les applique
        # immédiatement au reste de la sélection en cours
        newly_forbidden = mismatch_pairs(mismatches) - forbidden_pairs
        if newly_forbidden:
            forbidden_pairs |= newly_forbidden
            before = len(remaining)
            remaining = [c for c in remaining if is_combo_allowed(c, forbidden_pairs)]
            removed = before - len(remaining)
            if removed:
                print(f"{MAGENTA}Nouvelle règle appliquée : {removed} combinaison(s) "
                      f"retirée(s) des restantes.{RESET}")

        print()

        if not remaining:
            print(f"{GREEN}Toutes les combinaisons restantes ont été testées !{RESET}")
            break

        if not ask_yes_no("Continuer avec une autre tenue ?"):
            break

    print()
    title("RÉCAPITULATIF")
    print(f"Tenues testées cette session : {CYAN}{session_count}{RESET}")
    print(f"Fichier de sauvegarde        : {CYAN}{HISTORY_FILE.resolve()}{RESET}")
    line("═")


if __name__ == "__main__":
    main()