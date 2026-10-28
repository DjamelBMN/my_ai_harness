# PROGRAMME DE MATHÉMATIQUES — TERMINALE GÉNÉRALE (SPÉCIALITÉ)
Source officielle : Ministère de l'Éducation Nationale (Bulletin Officiel)

## 1. Algèbre et Géométrie dans l'espace
- **Vecteurs dans l'espace** : Définition, colinéarité, vecteurs coplanaires, base et repère de l'espace.
- **Produit scalaire dans l'espace** :
  - Définition par projection orthogonale ou formule trigonométrique $\vec{u} \cdot \vec{v} = \|\vec{u}\| \|\vec{v}\| \cos(\theta)$.
  - Expression dans un repère orthonormé : $\vec{u} \cdot \vec{v} = xx' + yy' + zz'$.
  - Norme d'un vecteur : $\|\vec{u}\| = \sqrt{x^2 + y^2 + z^2}$.
  - Orthogonalité de deux vecteurs : $\vec{u} \cdot \vec{v} = 0 \iff \vec{u} \perp \vec{v}$.
  - Vecteur normal à un plan : un vecteur non nul $\vec{n}$ est normal au plan $\mathcal{P}$ s'il est orthogonal à deux vecteurs non colinéaires de ce plan.
- **Plans et Droites** :
  - Équation cartésienne d'un plan : $ax + by + cz + d = 0$ où $(a, b, c) \neq (0, 0, 0)$ est un vecteur normal.
  - Représentation paramétrique d'une droite passant par $A(x_A, y_A, z_A)$ de vecteur directeur $\vec{u}(a, b, c)$ :
    $\begin{cases} x = x_A + at \\ y = y_A + bt \\ z = z_A + ct \end{cases} \quad (t \in \mathbb{R})$.
  - Positions relatives de droites et de plans : intersection droite-plan, parallélisme, orthogonalité, distance d'un point à un plan.

## 2. Analyse
### A. Suites numériques
- **Raisonnement par récurrence** : Initialisation, hérédité, conclusion.
- **Limites de suites** : Définition formelle, suites convergentes, limites infinies, opérations sur les limites.
- **Théorèmes de comparaison** :
  - Théorème d'encadrement (théorème des gendarmes) : si $u_n \le v_n \le w_n$ et $\lim u_n = \lim w_n = L$, alors $\lim v_n = L$.
  - Théorème de minoration/majoration : si $u_n \ge v_n$ et $\lim v_n = +\infty$, alors $\lim u_n = +\infty$.
- **Théorème de convergence monotone** : Toute suite croissante majorée converge ; toute suite décroissante minorée converge.
- **Suites géométriques** : Limite de $q^n$ selon les valeurs de $q$ ($q > 1$, $q = 1$, $-1 < q < 1$, $q \le -1$).

### B. Fonctions et Calcul différentiel
- **Limites de fonctions** : Asymptotes horizontales, verticales, obliques. Formes indéterminées ($\frac{0}{0}, \frac{\infty}{\infty}, 0 \times \infty, +\infty - \infty$). Croissances comparées ($\lim_{x \to +\infty} \frac{e^x}{x^n} = +\infty$, $\lim_{x \to +\infty} \frac{\ln x}{x^n} = 0$).
- **Continuité** : Définition, continuité sur un intervalle, théorème des valeurs intermédiaires (TVI) et son corollaire pour les fonctions strictement monotones (unicité de la solution de $f(x) = k$).
- **Dérivation et Convexité** :
  - Dérivées des composées : $(g \circ f)' = (g' \circ f) \times f'$.
  - Dérivée de $e^{u(x)}$ : $u'(x) e^{u(x)}$. Dérivée de $\ln(u(x))$ : $\frac{u'(x)}{u(x)}$.
  - Fonction convexe, fonction concave : Définition géométrique (courbe sous/au-dessus des sécantes et tangentes).
  - Critères de convexité : $f$ est convexe sur $I \iff f'$ est croissante $\iff f''(x) \ge 0$ pour tout $x \in I$.
  - Point d'inflexion : Point où la courbe traverse sa tangente $\iff f''$ s'annule en changeant de signe.

### C. Logarithme népérien et Exponentielle
- Logarithme népérien $\ln$ : bijection réciproque de $\exp$, propriétés algébriques ($\ln(ab) = \ln a + \ln b$, $\ln(a/b) = \ln a - \ln b$, $\ln(a^n) = n \ln a$).
- Dérivée, limites aux bornes ($\lim_{x \to 0^+} \ln x = -\infty$, $\lim_{x \to +\infty} \ln x = +\infty$).

### D. Primitives, Équations différentielles et Intégrales
- **Primitives** : Définition, primitives usuelles, linéarité.
- **Équations différentielles** :
  - $y' = ay$ : solutions de la forme $x \mapsto C e^{ax}$ ($C \in \mathbb{R}$).
  - $y' = ay + b$ ($a \neq 0$) : solutions de la forme $x \mapsto C e^{ax} - \frac{b}{a}$.
  - Détermination de la constante par condition initiale $y(x_0) = y_0$.
- **Calcul intégral** :
  - Intégrale d'une fonction continue et positive : aire sous la courbe.
  - Définition par primitive : $\int_a^b f(t) dt = [F(t)]_a^b = F(b) - F(a)$.
  - Propriétés : Linéarité, positivité, relation de Chasles.
  - Valeur moyenne : $\mu = \frac{1}{b-a} \int_a^b f(t) dt$.
  - Intégration par parties : $\int_a^b u'(t) v(t) dt = [u(t)v(t)]_a^b - \int_a^b u(t) v'(t) dt$.

## 3. Probabilités
- **Conditionnement et indépendance** : $P_B(A) = \frac{P(A \cap B)}{P(B)}$, formule des probabilités totales.
- **Loi binomiale $\mathcal{B}(n, p)$** : Schéma de Bernoulli, coefficients binomiaux $\binom{n}{k}$, formule $P(X=k) = \binom{n}{k} p^k (1-p)^{n-k}$, espérance $E(X) = np$, variance $V(X) = np(1-p)$.
- **Loi géométrique** : Temps d'attente du premier succès, $P(X=k) = (1-p)^{k-1} p$, $E(X) = \frac{1}{p}$.
- **Inégalités probabilistes** :
  - Inégalité de Markov : $P(X \ge a) \le \frac{E(X)}{a}$ pour $X \ge 0$.
  - Inégalité de Bienaymé-Tchebychev : $P(|X - E(X)| \ge \epsilon) \le \frac{V(X)}{\epsilon^2}$.
  - Loi faible des grands nombres : pour une suite de variables aléatoires indépendantes et de même loi, la moyenne empirique converge en probabilité vers l'espérance.
