### Partie C : Optimisation et intersection

Dans le même repère orthonormal $(O ; I, J)$, on considère la droite $(\Delta)$ d'équation réduite $y = -x + 2$.

1. **Positions relatives :** 
   Étudier la position relative de la parabole représentant la fonction $f$ (définie par $f(x) = -x^2 + 4$) et de la droite $(\Delta)$ en résolvant l'équation $f(x) = (-x + 2)$.
2. **Coordonnées des points d'intersection :** 
   En déduire les coordonnées exactes des points d'intersection de la parabole et de la droite $(\Delta)$.
3. **Optimisation géométrique :** 
   Soit $M$ un point de la parabole d'abscisse $x$ appartenant à l'intervalle $[0 ; 2]$. On considère le rectangle $OMNP$ où $N$ est le projeté orthogonal de $M$ sur l'axe des abscisses et $P$ sur l'axe des ordonnées. Exprimer l'aire de ce rectangle en fonction de $x$, puis déterminer pour quelle valeur de $x$ cette aire est maximale.

---

### Corrigé détaillé

#### Partie C
1. **Positions relatives :**
   On étudie le signe de la différence $f(x) - (-x + 2)$ :
   $$(-x^2 + 4) - (-x + 2) = -x^2 + x + 2$$
   Cherchons les racines du polynôme $-x^2 + x + 2$ en calculant son discriminant $\Delta$ :
   $$\Delta = 1^2 - 4 \times (-1) \times 2 = 1 + 8 = 9$$
   Puisque $\Delta > 0$, il y a deux racines distinctes :
   - $x_1 = \frac{-1 - 3}{2 \times (-1)} = \frac{-4}{-2} = 2$
   - $x_2 = \frac{-1 + 3}{2 \times (-1)} = \frac{2}{-2} = -1$
   Le coefficient dominant étant négatif ($a = -1$), le trinôme est positif entre ses racines et négatif à l'extérieur. Ainsi, la parabole est au-dessus de la droite sur l'intervalle $[-1 ; 2]$.

2. **Points d'intersection :**
   Les points d'intersection correspondent aux valeurs où la différence s'annule, soit $x = -1$ et $x = 2$.
   - Pour $x = -1$, $y = -(-1) + 2 = 3$. On obtient le point $A(-1 ; 3)$.
   - Pour $x = 2$, $y = -(2) + 2 = 0$. On obtient le point $B(2 ; 0)$.
   La parabole et la droite se coupent donc exactement aux points $A$ et $B$.

3. **Optimisation de l'aire :**
   Les coordonnées du point $M$ sur la parabole sont $(x ; -x^2 + 4)$ pour $x \in [0 ; 2]$.
   Les dimensions du rectangle $OMNP$ sont la longueur $ON = x$ et la largeur $OP = -x^2 + 4$.
   L'aire du rectangle est donc donnée par la fonction $\mathcal{A}(x) = x(-x^2 + 4) = -x^3 + 4x$.
   Pour trouver le maximum de cette aire sur $[0 ; 2]$, on étudie la dérivée $\mathcal{A}'(x)$ :
   $$\mathcal{A}'(x) = -3x^2 + 4$$
   La dérivée s'annule lorsque $3x^2 = 4$, soit $x^2 = \frac{4}{3}$, ce qui donne sur $[0 ; 2]$ :
   $$x = \frac{2}{\sqrt{3}} = \frac{2\sqrt{3}}{3} \approx 1{,}15$$
   Le tableau de variations de $\mathcal{A}$ montre qu'elle est croissante de $0$ à $\frac{2\sqrt{3}}{3}$, puis décroissante. L'aire est donc maximale lorsque l'abscisse de $M$ vaut $\frac{2\sqrt{3}}{3}$.
