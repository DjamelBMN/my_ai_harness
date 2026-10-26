# Exercice d'entraînement : Étude complète d'une fonction et dérivation

Cet exercice propose d'étudier une fonction polynomiale et une fonction rationnelle afin de maîtriser le calcul de dérivées, l'étude du signe et la détermination des tangentes.

## Partie A : Étude d'une fonction polynôme du troisième degré

Soit $f$ la fonction définie sur $\mathbb{R}$ par :
$$f(x) = 2x^3 - 3x^2 - 12x + 5$$

1. Calculer la dérivée $f'(x)$ pour tout réel $x$.
2. Étudier le signe de $f'(x)$ sur $\mathbb{R}$ et en déduire les variations de la fonction $f$.
3. Déterminer l'équation réduite de la tangente à la courbe représentative de $f$ au point d'abscisse $x_0 = 0$.

---

## Partie B : Étude d'une fonction rationnelle et application géométrique

Soit $g$ la fonction définie sur l'intervalle $I = ]1; +\infty[$ par :
$$g(x) = \frac{x^2 + 3}{x - 1}$$

1. Montrer que pour tout $x \in ]1; +\infty[$, la dérivée $g'(x)$ peut s'écrire sous la forme :
$$g'(x) = \frac{x^2 - 2x - 3}{(x - 1)^2}$$
2. Déterminer le signe de $g'(x)$ sur l'intervalle $I$ et dresser le tableau de variations complet de $g$.
3. Existe-t-il un ou plusieurs points de la courbe de $g$ où la tangente est horizontale ? Si oui, préciser leurs coordonnées.

---

## Éléments de correction et méthodes

### Correction de la Partie A
1. **Dérivation :** La fonction $f$ est dérivable sur $\mathbb{R}$ en tant que fonction polynôme.
   $$f'(x) = 2(3x^2) - 3(2x) - 12(1) + 0 = 6x^2 - 6x - 12$$
2. **Signe et variations :** On factorise $f'(x) = 6(x^2 - x - 2)$. Le discriminant du trinôme est $\Delta = (-1)^2 - 4(1)(-2) = 9$.
   Les racines sont $x_1 = \frac{1 - 3}{2} = -1$ et $x_2 = \frac{1 + 3}{2} = 2$.
   Par conséquent, $f'(x)$ est positive sur $]-\infty, -1]$ et sur $[2, +\infty[$, et négative sur $[-1, 2]$. La fonction $f$ est donc croissante sur $]-\infty, -1]$, décroissante sur $[-1, 2]$, puis croissante sur $[2, +\infty[$.
3. **Tangente en $0$ :** L'équation de la tangente est $y = f'(0)(x - 0) + f(0)$.
   On a $f(0) = 5$ et $f'(0) = -12$. L'équation réduite est donc :
   $$y = -12x + 5$$

### Correction de la Partie B
1. **Dérivation de la fonction rationnelle :** En utilisant la formule de dérivation d'un quotient $\left(\frac{u}{v}\right)' = \frac{u'v - uv'}{v^2}$ avec $u(x) = x^2 + 3$ et $v(x) = x - 1$ :
   $$g'(x) = \frac{2x(x - 1) - (x^2 + 3)(1)}{(x - 1)^2} = \frac{2x^2 - 2x - x^2 - 3}{(x - 1)^2} = \frac{x^2 - 2x - 3}{(x - 1)^2}$$
2. **Signe et variations :** Le dénominateur $(x - 1)^2$ est strictement positif sur $]1; +\infty[$. Le signe de $g'(x)$ dépend donc uniquement du numérateur $x^2 - 2x - 3$. Les racines de ce trinôme sont $-1$ et $3$. Sur l'intervalle $]1; +\infty[$, le polynôme est négatif pour $x \in ]1, 3[$ et positif pour $x \in ]3, +\infty[$. Ainsi, $g$ est décroissante sur $]1, 3]$ et croissante sur $[3, +\infty[$.
3. **Tangente horizontale :** Une tangente est horizontale si et seulement si son coefficient directeur est nul, c'est-à-dire $g'(x) = 0$. Cela se produit lorsque le numérateur s'annule sur l'intervalle, soit pour $x = 3$ (la valeur $-1$ étant exclue de l'intervalle). En calculant $g(3) = \frac{3^2 + 3}{3 - 1} = \frac{12}{2} = 6$, on obtient un unique point de tangence horizontale de coordonnées $(3, 6)$.
