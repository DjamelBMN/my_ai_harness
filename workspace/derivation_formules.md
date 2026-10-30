# La Dérivation : Guide Complet et Formules Fondamentales

La dérivation est l'un des piliers fondamentaux de l'analyse mathématique. Elle permet d'étudier les variations d'une fonction, de déterminer ses extrema, d'approcher des fonctions complexes par des fonctions affines et de modéliser des vitesses et des taux de variation en physique et en économie.

---

## 1. Nombre dérivé et fonction dérivée

### 1.1 Définition du nombre dérivé
Soit $f$ une fonction définie sur un intervalle $I$ et $a \in I$. On dit que $f$ est dérivable en $a$ si le taux d'accroissement admet une limite finie quand $h$ tend vers 0 :
$$f'(a) = \lim_{h \to 0} \frac{f(a+h) - f(a)}{h}$$

Géométriquement, le nombre dérivé $f'(a)$ représente le **coefficient directeur de la tangente** à la courbe représentative de $f$ au point d'abscisse $a$.

### 1.2 Équation de la tangente
L'équation de la tangente à la courbe de $f$ au point d'abscisse $a$ est donnée par :
$$y = f'(a)(x - a) + f(a)$$

---

## 2. Dérivées des fonctions usuelles

Voici le récapitulatif des dérivées des fonctions de référence (pour $x$ dans leur domaine de définition) :

| Fonction $f(x)$ | Dérivée $f'(x)$ | Domaine de validité |
| :--- | :--- | :--- |
| $c$ (constante) | $0$ | $\mathbb{R}$ |
| $x$ | $1$ | $\mathbb{R}$ |
| $x^n$ ($n \in \mathbb{N}^*$) | $n x^{n-1}$ | $\mathbb{R}$ |
| $\frac{1}{x}$ | $-\frac{1}{x^2}$ | $\mathbb{R}^*$ |
| $\sqrt{x}$ | $\frac{1}{2\sqrt{x}}$ | $]0; +\infty[$ |
| $e^x$ | $e^x$ | $\mathbb{R}$ |
| $\ln(x)$ | $\frac{1}{x}$ | $]0; +\infty[$ |
| $\cos(x)$ | $-\sin(x)$ | $\mathbb{R}$ |
| $\sin(x)$ | $\cos(x)$ | $\mathbb{R}$ |

---

## 3. Opérations sur les dérivées

Soient $u$ et $v$ deux fonctions dérivables sur un intervalle $I$, et $k$ un nombre réel.

* **Linéarité :** $(u + v)' = u' + v'$ et $(k \cdot u)' = k \cdot u'$
* **Produit :** $(u \cdot v)' = u'v + uv'$
* **Inverse :** $\left(\frac{1}{v}\right)' = -\frac{v'}{v^2}$ (sur $I$ où $v \neq 0$)
* **Quotient :** $\left(\frac{u}{v}\right)' = \frac{u'v - uv'}{v^2}$ (sur $I$ où $v \neq 0$)
* **Composée (puissance) :** $(u^n)' = n \cdot u' \cdot u^{n-1}$
* **Composée (exponentielle) :** $(e^u)' = u' \cdot e^u$

---

## 4. Lien entre dérivation et variations

Le signe de la dérivée d'une fonction renseigne directement sur son sens de variation :

* Si $f'(x) > 0$ sur un intervalle $I$, alors $f$ est **strictement croissante** sur $I$.
* Si $f'(x) < 0$ sur un intervalle $I$, alors $f$ est **strictement décroissante** sur $I$.
* Si $f'(x) = 0$ sur un intervalle $I$, alors $f$ est **constante** sur $I$.

### Exemple de tableau de variations

Considérons la fonction $f(x) = 2x^3 - 3x^2 - 12x + 1$ définie sur $\mathbb{R}$.
Sa dérivée est $f'(x) = 6x^2 - 6x - 12 = 6(x^2 - x - 2) = 6(x + 1)(x - 2)$.

Le tableau de variations complet de $f$ s'écrit :

```tableau
x: -oo | -1 | 2 | +oo
f'(x): + 0 - 0 +
f(x): -oo | 8 // -19 | +oo
```

*(Note : la valeur $-19$ en $x=2$ est un minimum local, et $8$ en $x=-1$ est un maximum local).*

### Extremum local
Si $f$ admet un extremum (maximum ou minimum) en un point $a$ (intérieur à l'intervalle) et que $f$ est dérivable en $a$, alors :
$$f'(a) = 0$$
*(Attention : la réciproque est fausse, comme le montre la fonction $f(x) = x^3$ en $x = 0$.)*

---

## 5. Applications pratiques

### 5.1 Étude de fonctions
La dérivation est l'outil central pour dresser le tableau de variations d'une fonction et tracer son allure graphique avec précision.

### 5.2 Optimisation
En physique, en économie ou en ingénierie, la recherche de la valeur maximale ou minimale d'une fonction passe par l'annulation de sa dérivée (recherche des points critiques).

### 5.3 Approximation locale
Pour des valeurs de $h$ proches de $0$, on dispose de l'approximation affine :
$$f(a+h) \approx f(a) + h \cdot f'(a)$$
