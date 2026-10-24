# PROGRAMME DE MATHÉMATIQUES — TERMINALE (OPTION MATHS EXPERTES)
Source officielle : Ministère de l'Éducation Nationale (BO)

## 1. Nombres Complexes
### A. Forme algébrique et plan complexe
- Définition de $\mathbb{C}$, unité imaginaire $i^2 = -1$.
- Forme algébrique : $z = a + ib$ ($a = \text{Re}(z)$, $b = \text{Im}(z)$).
- Conjugué : $\bar{z} = a - ib$. Propriétés : $\overline{z + z'} = \bar{z} + \bar{z}'$, $\overline{zz'} = \bar{z} \bar{z}'$, $z\bar{z} = a^2 + b^2 = |z|^2$.
- Équations du second degré à coefficients réels : calcul du discriminant $\Delta = b^2 - 4ac$. Si $\Delta < 0$, deux racines complexes conjuguées $z = \frac{-b \pm i\sqrt{-\Delta}}{2a}$.

### B. Forme trigonométrique et exponentielle
- Module : $|z| = \sqrt{a^2 + b^2}$. Argument : $\arg(z) \equiv \theta \pmod{2\pi}$ avec $\cos\theta = \frac{a}{|z|}$, $\sin\theta = \frac{b}{|z|}$.
- Notation exponentielle : $e^{i\theta} = \cos\theta + i\sin\theta$. Formule d'Euler : $\cos\theta = \frac{e^{i\theta} + e^{-i\theta}}{2}$, $\sin\theta = \frac{e^{i\theta} - e^{-i\theta}}{2i}$.
- Formule de Moivre : $(\cos\theta + i\sin\theta)^n = \cos(n\theta) + i\sin(n\theta) \iff (e^{i\theta})^n = e^{in\theta}$.
- Racines n-ièmes de l'unité : solutions de $z^n = 1$, données par $\omega_k = e^{i\frac{2k\pi}{n}}$ pour $k \in \{0, \dots, n-1\}$.

### C. Applications géométriques des complexes
- Translation de vecteur $\vec{u}$ d'affixe $b$ : $z' = z + b$.
- Homothétie de centre $\Omega(\omega)$ et de rapport $k \in \mathbb{R}^*$ : $z' - \omega = k(z - \omega)$.
- Rotation de centre $\Omega(\omega)$ et d'angle $\theta$ : $z' - \omega = e^{i\theta}(z - \omega)$.
- Alignement et orthogonalité : $\frac{z_C - z_A}{z_B - z_A} \in \mathbb{R} \iff A, B, C$ alignés ; $\frac{z_C - z_A}{z_B - z_A} \in i\mathbb{R} \iff (AB) \perp (AC)$.

## 2. Arithmétique
### A. Divisibilité et division euclidienne
- Relation de divisibilité dans $\mathbb{Z}$ : $a | b \iff \exists k \in \mathbb{Z}, b = ka$.
- Division euclidienne dans $\mathbb{Z}$ : pour $a \in \mathbb{Z}$ et $b \in \mathbb{Z}^*$, il existe un unique couple $(q, r) \in \mathbb{Z} \times \mathbb{N}$ tel que $a = bq + r$ avec $0 \le r < |b|$.
- Congruences : $a \equiv b \pmod n \iff n | (a - b)$. Compatibilité avec l'addition et la multiplication.

### B. PGCD, théorèmes fondamentaux et équations diophantiennes
- Algorithme d'Euclide pour le calcul du PGCD.
- Théorème de Bézout : Deux entiers $a$ et $b$ sont premiers entre eux si et seulement s'il existe $(u, v) \in \mathbb{Z}^2$ tel que $au + bv = 1$.
- Théorème de Gauss : Si $a | bc$ et si $\text{PGCD}(a, b) = 1$, alors $a | c$.
- Équations diophantiennes linéaires $ax + by = c$ : ont des solutions si et seulement si $\text{PGCD}(a, b) | c$.
- Nombres premiers : Définition, infinité de l'ensemble des nombres premiers, théorème fondamental de l'arithmétique (existence et unicité de la décomposition en facteurs premiers).
- Petit théorème de Fermat : Si $p$ est premier et ne divise pas $a$, alors $a^{p-1} \equiv 1 \pmod p$.
- Applications au chiffrement RSA : génération de clés, chiffrement et déchiffrement modulaire.

## 3. Graphes et Matrices
### A. Calcul matriciel
- Matrices à coefficients réels, addition, multiplication par un scalaire.
- Produit matriciel : non commutatif en général. Matrice identité $I_n$.
- Matrice inverse : $A$ est inversible s'il existe $B$ telle que $AB = BA = I_n$. Pour une matrice $2 \times 2$ : $A = \begin{pmatrix} a & b \\ c & d \end{pmatrix}$, $\det(A) = ad - bc \neq 0 \implies A^{-1} = \frac{1}{ad-bc}\begin{pmatrix} d & -b \\ -c & a \end{pmatrix}$.
- Puissances de matrices $A^n$ : calcul par diagonalisation simple, formule du binôme ou récurrence.

### B. Graphes et Chaînes de Markov
- Graphes orientés et non orientés, sommets, arêtes/arcs, degrés, chaîne, cycle, connexité.
- Matrice d'adjacence $M$ : le terme $(i, j)$ de $M^k$ donne le nombre de chaînes de longueur $k$ reliant le sommet $i$ au sommet $j$.
- Chaînes de Markov : processus aléatoire sans mémoire, matrice de transition stochastique $T$ où la somme de chaque ligne vaut 1.
- État probabiliste à l'étape $n$ : $P_n = P_0 \cdot T^n$.
- Distribution stationnaire : distribution de probabilité $\pi$ vérifiant $\pi T = \pi$.

