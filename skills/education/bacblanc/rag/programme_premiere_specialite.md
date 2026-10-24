# PROGRAMME DE MATHÉMATIQUES — PREMIÈRE GÉNÉRALE (SPÉCIALITÉ)
Source officielle : Ministère de l'Éducation Nationale

## 1. Algèbre
### A. Polynômes du second degré
- Forme développée : $P(x) = ax^2 + bx + c$ ($a \neq 0$).
- Forme canonique : $P(x) = a\left(x + \frac{b}{2a}\right)^2 - \frac{\Delta}{4a}$ où $\Delta = b^2 - 4ac$ est le discriminant.
- Racines et factorisation :
  - Si $\Delta > 0$ : deux racines réelles distinctes $x_{1,2} = \frac{-b \pm \sqrt{\Delta}}{2a}$, $P(x) = a(x - x_1)(x - x_2)$.
  - Si $\Delta = 0$ : une racine double $x_0 = -\frac{b}{2a}$, $P(x) = a(x - x_0)^2$.
  - Si $\Delta < 0$ : aucune racine réelle, non factorisable sur $\mathbb{R}$.
- Signe du trinôme : $P(x)$ est du signe de $a$ à l'extérieur des racines, du signe de $-a$ entre les racines.

### B. Suites numériques
- Définition : suite comme fonction de $\mathbb{N}$ dans $\mathbb{R}$, formes explicite $u_n = f(n)$ et par récurrence $u_{n+1} = f(u_n)$.
- Sens de variation : comparaison de $u_{n+1} - u_n$ à 0 (ou $\frac{u_{n+1}}{u_n}$ à 1 si $u_n > 0$).
- Suites arithmétiques : $u_{n+1} = u_n + r$, terme général $u_n = u_0 + nr = u_p + (n-p)r$, somme des termes $\sum_{k=0}^n u_k = (n+1)\frac{u_0 + u_n}{2}$.
- Suites géométriques : $u_{n+1} = q \cdot u_n$, terme général $u_n = u_0 \cdot q^n = u_p \cdot q^{n-p}$, somme des puissances consécutives pour $q \neq 1$ : $\sum_{k=0}^n q^k = \frac{1 - q^{n+1}}{1 - q}$.

## 2. Analyse
### A. Dérivation
- Taux de variation : $\tau(h) = \frac{f(a+h) - f(a)}{h}$.
- Nombre dérivé $f'(a) = \lim_{h \to 0} \tau(h)$. Équation de la tangente : $y = f'(a)(x - a) + f(a)$.
- Dérivées des fonctions usuelles :
  - $x^n \implies n x^{n-1}$ ($n \in \mathbb{Z}^*$).
  - $\frac{1}{x} \implies -\frac{1}{x^2}$.
  - $\sqrt{x} \implies \frac{1}{2\sqrt{x}}$ pour $x > 0$.
  - $e^x \implies e^x$.
- Règles de dérivation : $(u + v)' = u' + v'$, $(ku)' = k u'$, $(uv)' = u'v + uv'$, $\left(\frac{1}{v}\right)' = -\frac{v'}{v^2}$, $\left(\frac{u}{v}\right)' = \frac{u'v - uv'}{v^2}$.
- Lien dérivation et variations : $f'(x) \ge 0 \iff f$ est croissante ; $f'(x) \le 0 \iff f$ est décroissante ; $f'(x) = 0 \iff f$ est constante.
- Recherche d'extrema locaux : si $f'$ s'annule en changeant de signe en $x_0$, $f(x_0)$ est un extremum local.

### B. Fonction exponentielle
- Caractérisation : unique fonction $f$ dérivable sur $\mathbb{R}$ telle que $f' = f$ et $f(0) = 1$.
- Propriétés algébriques : $e^{x+y} = e^x e^y$, $e^{-x} = \frac{1}{e^x}$, $e^{x-y} = \frac{e^x}{e^y}$, $(e^x)^n = e^{nx}$.
- Signe et variations : pour tout $x \in \mathbb{R}$, $e^x > 0$ et $x \mapsto e^x$ est strictement croissante sur $\mathbb{R}$.

## 3. Géométrie
### A. Produit scalaire dans le plan
- Définition géométrique : $\vec{u} \cdot \vec{v} = \|\vec{u}\| \|\vec{v}\| \cos(\theta) = \vec{u} \cdot \vec{v}_H$ (projection orthogonale).
- Formule des normes : $\vec{u} \cdot \vec{v} = \frac{1}{2}\left(\|\vec{u} + \vec{v}\|^2 - \|\vec{u}\|^2 - \|\vec{v}\|^2\right)$.
- Expression analytique en repère orthonormé : $\vec{u}(x, y)$ et $\vec{v}(x', y') \implies \vec{u} \cdot \vec{v} = xx' + yy'$.
- Théorème d'Al-Kashi (loi des cosinus) : $a^2 = b^2 + c^2 - 2bc \cos(\hat{A})$.
- Théorème de la médiane : $AB^2 + AC^2 = 2AI^2 + \frac{BC^2}{2}$ où $I$ est le milieu de $[BC]$.
- Équation cartésienne d'une droite de vecteur normal $\vec{n}(a, b)$ : $ax + by + c = 0$.

### B. Trigonométrie
- Enroulement de la droite numérique sur le cercle trigonométrique, mesure en radians.
- Angles associés : $\cos(-x) = \cos x$, $\sin(-x) = -\sin x$, $\cos(\pi - x) = -\cos x$, $\sin(\pi - x) = \sin x$, $\cos(\pi + x) = -\cos x$, $\sin(\pi + x) = -\sin x$, $\cos\left(\frac{\pi}{2} - x\right) = \sin x$, $\sin\left(\frac{\pi}{2} - x\right) = \cos x$.
- Formule fondamentale : $\cos^2 x + \sin^2 x = 1$.

## 4. Probabilités et Statistiques
- Conditionnement : $P_B(A) = \frac{P(A \cap B)}{P(B)}$. Formule des probabilités totales : si $\{B_1, \dots, B_n\}$ est une partition de l'univers, $P(A) = \sum_{k=1}^n P(A \cap B_k) = \sum_{k=1}^n P_{B_k}(A) P(B_k)$.
- Indépendance : $A$ et $B$ sont indépendants $\iff P(A \cap B) = P(A) \times P(B) \iff P_B(A) = P(A)$.
- Variables aléatoires réelles : univers image $X(\Omega) = \{x_1, \dots, x_k\}$, loi de probabilité $P(X = x_i) = p_i$ avec $\sum p_i = 1$.
- Espérance : $E(X) = \sum_{i=1}^k x_i p_i$. Variance : $V(X) = E((X - E(X))^2) = \sum_{i=1}^k p_i x_i^2 - (E(X))^2$ (formule de Koenig-Huygens). Écart-type : $\sigma(X) = \sqrt{V(X)}$.
