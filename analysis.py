#!/usr/bin/env python3
"""
Outfit Analyzer — dialogue terminal
------------------------------------
Complémentaire à outfit_tester.py : parcourt historique_outfits.json,
filtre selon le contexte choisi, classe les tenues par note décroissante
et calcule des KPIs (répartition des notes, couverture, meilleurs/pires
éléments, règles d'incompatibilité actives...).

À placer dans le même dossier que outfit_tester.py (le module est réutilisé
pour rester cohérent : mêmes règles, même garde-robe, même historique).
"""

import statistics
from collections import Counter, defaultdict

import outfit_tester as ot

RESET, BOLD, DIM = ot.RESET, ot.BOLD, ot.DIM
CYAN, GREEN, YELLOW, MAGENTA, RED = ot.CYAN, ot.GREEN, ot.YELLOW, ot.MAGENTA, ot.RED

FIELD_LABELS = {
    'shirt': 'Chemise',
    'tshirt': 'T-shirt',
    'bottom': 'Bas',
    'shoes': 'Chaussures',
    'pull': 'Pull',
    'coat': 'Manteau',
}

RANK_COLOR = {5: GREEN, 4: GREEN, 3: YELLOW, 2: RED, 1: RED}

WIDTH = 60


def line(char="─"):
    ot.line(char, WIDTH)


def title(text):
    ot.title(text, WIDTH)


# ----------------------------------------------------------------------
# Normalisation / filtrage
# ----------------------------------------------------------------------

def ask_filter_outdoor():
    print(f"{YELLOW}Filtrer sur 'dehors' ?{RESET}")
    print("  [1] Tous")
    print("  [2] Extérieur uniquement")
    print("  [3] Intérieur uniquement")
    while True:
        rep = input("> ").strip()
        if rep == '1' or rep == '':
            return None
        if rep == '2':
            return True
        if rep == '3':
            return False
        print(f"{RED}Entrée invalide (1, 2 ou 3).{RESET}")


def ask_filter_temp():
    print(f"{YELLOW}Filtrer sur le palier de température ?{RESET}")
    print("  [1] Tous")
    print("  [2] Froid")
    print("  [3] Medium")
    print("  [4] Chaud")
    options = {'2': 'froid', '3': 'medium', '4': 'chaud'}
    while True:
        rep = input("> ").strip()
        if rep == '1' or rep == '':
            return None
        if rep in options:
            return options[rep]
        print(f"{RED}Entrée invalide (1 à 4).{RESET}")


def ask_top_n(default=10):
    rep = input(f"{YELLOW}Combien de tenues afficher dans le classement ?{RESET} "
                f"{DIM}(Entrée = {default}){RESET}\n> ").strip()
    if rep.isdigit() and int(rep) > 0:
        return int(rep)
    return default


# ----------------------------------------------------------------------
# KPIs
# ----------------------------------------------------------------------

def outfit_summary_line(outfit):
    parts = [outfit['top'], outfit['bottom'], outfit['shoes']]
    if outfit.get('pull'):
        parts.append(outfit['pull'])
    if outfit.get('coat'):
        parts.append(outfit['coat'])
    return " | ".join(parts)


def print_rank_distribution(ranks):
    counts = Counter(ranks)
    max_count = max(counts.values()) if counts else 1
    for note in (5, 4, 3, 2, 1):
        c = counts.get(note, 0)
        bar_width = int((c / max_count) * 30) if max_count else 0
        bar = "█" * bar_width
        color = RANK_COLOR[note]
        print(f"  {note} {DIM}|{RESET} {color}{bar}{RESET} {DIM}({c}){RESET}")


def compute_item_stats(filtered):
    """Pour chaque élément élémentaire (chemise, t-shirt, bas, chaussures,
    pull, manteau), calcule la note moyenne et le nombre d'apparitions."""
    stats = defaultdict(list)
    for entry in filtered:
        for field, value in ot.combo_items(entry['outfit']):
            stats[(field, value)].append(entry['rank'])
    return stats


def print_best_worst_items(stats, min_count=1):
    by_field = defaultdict(list)
    for (field, value), ranks in stats.items():
        if len(ranks) >= min_count:
            by_field[field].append((value, statistics.mean(ranks), len(ranks)))

    for field, label in FIELD_LABELS.items():
        items = by_field.get(field)
        if not items:
            continue
        items.sort(key=lambda x: x[1], reverse=True)
        best_value, best_avg, best_n = items[0]
        worst_value, worst_avg, worst_n = items[-1]
        print(f"  {BOLD}{label:<12}{RESET} "
              f"{GREEN}meilleur : {best_value} ({best_avg:.1f}/5, {best_n} essai(s)){RESET}")
        if len(items) > 1:
            print(f"  {'':<12} "
                  f"{RED}pire     : {worst_value} ({worst_avg:.1f}/5, {worst_n} essai(s)){RESET}")


def print_coverage(filtered, forbidden_pairs):
    """Regroupe les tenues filtrées par contexte réellement rencontré et
    affiche le taux de couverture par rapport aux combinaisons possibles
    (seules les tenues testées encore autorisées par les règles comptent)."""
    tested_by_context = defaultdict(set)
    for entry in filtered:
        ctx = ot.normalize_context(entry)
        tested_by_context[(ctx.get('outdoor'), ctx.get('temp'))].add(entry['signature'])

    for (outdoor, temp), tested in sorted(tested_by_context.items(),
                                          key=lambda kv: tuple(map(str, kv[0]))):
        if outdoor is None or temp is None:
            continue
        possible = {ot.signature_of(c)
                    for c in ot.generate_all_combos(outdoor, temp, forbidden_pairs)}
        total = len(possible)
        tested_count = len(tested & possible)
        pct = (tested_count / total * 100) if total else 0
        outdoor_label = "dehors" if outdoor else "intérieur"
        print(f"  {outdoor_label:<10} / {temp:<7} : "
              f"{CYAN}{tested_count}{RESET}/{total} testées "
              f"({YELLOW}{pct:.1f}%{RESET})")


# ----------------------------------------------------------------------
# Affichage
# ----------------------------------------------------------------------

def print_ranking(filtered, top_n, forbidden_pairs):
    ranked = sorted(filtered, key=lambda e: (e['rank'], e['timestamp']), reverse=True)
    title(f"TOP {min(top_n, len(ranked))} DES TENUES")
    for i, entry in enumerate(ranked[:top_n], start=1):
        color = RANK_COLOR.get(entry['rank'], RESET)
        outfit = entry['outfit']
        ctx = ot.normalize_context(entry)
        warn = ""
        if not ot.is_combo_allowed(outfit, forbidden_pairs):
            warn = f" {RED}⚠ contient désormais une paire interdite{RESET}"
        print(f"  {BOLD}#{i:<2}{RESET} {color}{entry['rank']}/5{RESET} "
              f"{DIM}[{'dehors' if ctx.get('outdoor') else 'intérieur'}, {ctx.get('temp')}]{RESET}"
              f"{warn}")
        print(f"       {outfit_summary_line(outfit)}")
    line()


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    title("OUTFIT ANALYZER")
    print(f"{DIM}Analyse de l'historique des tenues testées.{RESET}\n")

    history = ot.load_history()
    if not history:
        print(f"{RED}Aucune tenue testée pour le moment — lance d'abord outfit_tester.py.{RESET}")
        return

    forbidden_pairs = ot.compute_forbidden_pairs(history)

    outdoor_filter = ask_filter_outdoor()
    temp_filter = ask_filter_temp()
    print()

    filtered = [e for e in history if ot.matches_context(e, outdoor_filter, temp_filter)]

    if not filtered:
        print(f"{RED}Aucune tenue testée ne correspond à ce filtre.{RESET}")
        return

    ranks = [e['rank'] for e in filtered]

    # ---- KPIs ----
    title("KPIs")
    print(f"  {BOLD}Tenues testées (filtrées){RESET}       : {CYAN}{len(filtered)}{RESET}")
    print(f"  {BOLD}Note moyenne{RESET}                    : {CYAN}{statistics.mean(ranks):.2f}/5{RESET}")
    print(f"  {BOLD}Meilleure / pire note{RESET}           : "
          f"{GREEN}{max(ranks)}/5{RESET} / {RED}{min(ranks)}/5{RESET}")
    print(f"  {BOLD}Règles d'incompatibilité actives{RESET} : {MAGENTA}{len(forbidden_pairs)}{RESET}")
    print()
    print(f"  {BOLD}Répartition des notes{RESET}")
    print_rank_distribution(ranks)
    print()
    print(f"  {BOLD}Couverture par contexte rencontré{RESET}")
    print_coverage(filtered, forbidden_pairs)
    print()
    print(f"  {BOLD}Meilleurs / pires éléments (note moyenne){RESET}")
    stats = compute_item_stats(filtered)
    print_best_worst_items(stats)
    line("═")
    print()

    # ---- Classement ----
    top_n = ask_top_n()
    print()
    print_ranking(filtered, top_n, forbidden_pairs)


if __name__ == "__main__":
    main()