def calculer_moyenne(notes):
    if not notes:
        return 0  # Sécurité pour éviter une division par zéro si la liste est vide

    total = 0
    for note in notes:
        total += note

    return total / len(notes)


def afficher_resultat(nom, moyenne):
    print(f"{nom} a obtenu {moyenne:.2f}/20")


notes = [12, 15, 9, 17]
moyenne = calculer_moyenne(notes)

afficher_resultat("Alice", moyenne)