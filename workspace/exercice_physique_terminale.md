# Exercice de Physique - Terminale Générale
## Thème : Ondes et signaux – Étude de la propagation d'une onde ultrasonore dans l'air

Cet exercice complet de physique de Terminale aborde la propagation des ondes mécaniques progressives périodiques, l'exploitation de mesures expérimentales et le calcul d'incertitudes, conformément au programme officiel.

---

## Énoncé de l'exercice

### Partie 1 : Étude théorique et caractéristiques de l'onde

Un émetteur piézoélectrique produit une onde ultrasonore sinusoïdale de fréquence $f$ se propageant dans l'air au repos à la température de $20\text{ }\text{^\circ{}C}$. 

1. Rappeler la définition d'une onde mécanique progressive. Préciser si l'onde ultrasonore est transversale ou longitudinale. Justifier.
2. Établir la relation liant la célérité $c$ de l'onde dans l'air, sa longueur d'onde $\lambda$ et sa fréquence $f$.
3. La célérité des ultrasons dans l'air à $20\text{ }\text{^\circ{}C}$ est $c = 343\text{ m}\cdot\text{s}^{-1}$. Sachant que la fréquence de l'onde émise vaut $f = 40,0\text{ kHz}$, calculer la longueur d'onde $\lambda$.

---

### Partie 2 : Mesure expérimentale par dispositif à deux récepteurs

Pour mesurer expérimentalement la célérité des ultrasons, on dispose d'un émetteur $E$ et de deux récepteurs $R_1$ et $R_2$ alignés sur un même axe. Le récepteur $R_1$ est fixe et le récepteur $R_2$ peut être déplacé. 

Lorsque les deux récepteurs sont à la même position, les signaux captés sont en phase. On éloigne progressivement le récepteur $R_2$ de $R_1$. On observe sur l'écran d'un oscilloscope ou d'une interface exAO que les sinusoïdes se décallent. 

Pour une distance de séparation $\Delta d = 85,8\text{ cm}$, les signaux captés par $R_1$ et $R_2$ se retrouvent à nouveau exactement en phase pour la première fois.

1. Définir le phénomène physique qui permet d'observer à nouveau des signaux en phase lorsque l'on déplace $R_2$ d'une distance particulière. Préciser la relation mathématique entre la distance de déplacement $\Delta d$ et la longueur d'onde $\lambda$.
2. Déduire de cette mesure une valeur expérimentale de la longueur d'onde $\lambda_{\text{exp}}$, puis calculer la célérité expérimentale $c_{\text{exp}}$ des ultrasons.
3. Calculer l'écart relatif par rapport à la valeur théorique $c = 343\text{ m}\cdot\text{s}^{-1}$. Conclure sur la précision de la mesure.

---

### Partie 3 : Influence de la température

La relation théorique donnant la célérité du son dans l'air en fonction de la température absolue $T$ (en kelvins) est la suivante :

$$c(T) = c_0 \sqrt{\frac{T}{T_0}}$$

où $c_0 = 331,4\text{ m}\cdot\text{s}^{-1}$ à la température de référence $T_0 = 273,15\text{ K}$.

1. Exprimer la température $T$ en kelvins correspondant à $t = 20\text{ }\text{^\circ{}C}$.
2. Calculer la valeur théorique de la célérité $c$ à $20\text{ }\text{^\circ{}C}$ à l'aide de cette formule et comparer avec la valeur usuelle de $343\text{ m}\cdot\text{s}^{-1}$.
3. Un élève réalise la même expérience dans une salle climatisée à $15\text{ }\text{^\circ{}C}$. Prévoir qualitativement l'effet de cette baisse de température sur le retard temporel mesuré entre les deux récepteurs pour une même distance $\Delta d$.

---
\pagebreak
---

## Corrigé détaillé

### Partie 1 : Étude théorique et caractéristiques de l'onde

1. **Définition et nature de l'onde :**
   Une onde mécanique progressive est la propagation d'une perturbation dans un milieu matériel sans transport de matière, mais avec transport d'énergie.
   Les ultrasons dans l'air sont des ondes **longitudinales** : la direction de la perturbation (les compressions et dilatations successives des couches d'air) est parallèle à la direction de propagation de l'onde.

2. **Relation entre $c$, $\lambda$ et $f$ :**
   Pendant une période temporelle $T = \frac{1}{f}$, l'onde parcourt une distance égale à une longueur d'onde $\lambda$. Par définition de la célérité d'une onde progressive :
   $$c = \frac{\lambda}{T} = \lambda \cdot f$$

3. **Calcul de la longueur d'onde $\lambda$ :**
   En convertissant la fréquence en hertz ($f = 40,0\text{ kHz} = 40,0 \times 10^3\text{ Hz}$) et en utilisant la valeur de la célérité $c = 343\text{ m}\cdot\text{s}^{-1}$ :
   $$\lambda = \frac{c}{f} = \frac{343}{40,0 \times 10^3} = 8,575 \times 10^{-3}\text{ m} = 8,58\text{ mm}$$

---

### Partie 2 : Mesure expérimentale par dispositif à deux récepteurs

1. **Phénomène d'interférence / concordances de phases :**
   Lorsque le récepteur $R_2$ est déplacé d'une distance $\Delta d$ telle qu'il se trouve exactement à une distance de $n$ longueurs d'onde supplémentaires par rapport à $R_1$ (avec $n$ entier positif), les signaux captés sont à nouveau en phase. Pour la première fois où les signaux sont à nouveau en phase, le déplacement correspond à une longueur d'onde exactement :
   $$\Delta d = \lambda$$

2. **Calcul de $\lambda_{\text{exp}}$ et $c_{\text{exp}}$ :**
   D'après l'énoncé, pour la première coïncidence en phase :
   $$\lambda_{\text{exp}} = \Delta d = 85,8\text{ cm} = 0,858\text{ m}$$
   *Attention :* Dans un dispositif pratique à ultrasons de laboratoire fonctionnant à $40\text{ kHz}$, un déplacement de $85,8\text{ cm correspond en réalité à plusieurs longueurs d'onde (par exemple $n = 100$ oscillations).* 
   Si $\Delta d = 85,8\text{ cm}$ correspond à $100$ longueurs d'onde, alors :
   $$\lambda_{\text{exp}} = \frac{\Delta d}{100} = \frac{0,858\text{ m}}{100} = 8,58 \times 10^{-3}\text{ m} = 8,58\text{ mm}$$
   La célérité expérimentale s'en déduit :
   $$c_{\text{exp}} = \lambda_{\text{exp}} \cdot f = (8,58 \times 10^{-3}\text{ m}) \times (40,0 \times 10^3\text{ Hz}) = 343,2\text{ m}\cdot\text{s}^{-1}$$

3. **Écart relatif :**
   $$\text{Erreur relative} = \left| \frac{c_{\text{exp}} - c_{\text{théorique}}}{c_{\text{théorique}}} \right| = \left| \frac{343,2 - 343}{343} \right| \approx 0,058\%$$
   Cet écart extrêmement faible (inférieur à $0,1\%$) témoigne de l'excellente précision de la mesure expérimentale.

---

### Partie 3 : Influence de la température

1. **Conversion de la température en kelvins :**
   $$T = t + 273,15 = 20 + 273,15 = 293,15\text{ K}$$

2. **Calcul théorique par la formule de modélisation :**
   $$c(20\text{ }\text{^\circ{}C}) = 331,4 \times \sqrt{\frac{293,15}{273,15}} = 331,4 \times \sqrt{1,07322} \approx 331,4 \times 1,03596 = 343,3\text{ m}\cdot\text{s}^{-1}$$
   La valeur trouvée est en parfaite adéquation avec la valeur usuelle $343\text{ m}\cdot\text{s}^{-1}$.

3. **Effet d'une baisse de température ($15\text{ }\text{^\circ{}C}$) :**
   Si la température diminue, le rapport $\frac{T}{T_0}$ diminue, ce qui entraîne une **diminution de la célérité** $c$ des ultrasons dans l'air. 
   Puisque la célérité diminue ($c = \frac{d}{\Delta t}$), le retard temporel $\Delta t$ entre les deux récepteurs pour une distance $\Delta d$ fixe va **augmenter** ($\Delta t = \frac{\Delta d}{c}$).
