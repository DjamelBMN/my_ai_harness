# Exercice d'application : Étude d'une suite géométrique et modélisation financière

Cet exercice propose d'étudier une suite géométrique à travers un cas concret de placement financier et d'évolution de capital, permettant de manipuler les notions de raison, de terme général et de somme de termes consécutifs.

## Énoncé de l'exercice

Un épargnant place la somme de $1\,000\text{ \euro}$ sur un compte rémunéré au taux annuel composé de $3\,\%$. Les intérêts sont capitalisés chaque année, ce qui signifie qu'à la fin de chaque année, les intérêts s'ajoutent au capital existant pour produire eux aussi des intérêts l'année suivante.

On note $u_n$ le montant du capital (en euros) disponible sur le compte à la fin de l'année $n$, où $n$ est un entier naturel représentant le nombre d'années écoulées depuis l'ouverture du compte. Ainsi, le capital initial est $u_0 = 1\,000$.

1. Calculer le capital $u_1$ disponible à la fin de la première année, puis le capital $u_2$ à la fin de la deuxième année.
2. Exprimer le capital $u_{n+1}$ en fonction du capital $u_n$ pour tout entier naturel $n$. En déduire la nature de la suite $(u_n)$ ainsi que sa raison et son premier terme.
3. Exprimer le terme général $u_n$ en fonction de $n$ pour tout entier naturel $n$.
4. Calculer le capital disponible au bout de 10 ans, arrondi au centime près.
5. Déterminer, à l'aide d'une inéquation, au bout de combien d'années complètes le capital initial aura doublé.

---

## Corrigé détaillé

### 1. Calcul des premiers termes
À la fin de la première année, le capital augmente de $3\,\%$. On a donc :
$$u_1 = u_0 + \frac{3}{100} u_0 = u_0 \times \left(1 + 0{,}03\right) = 1\,000 \times 1{,}03 = 1\,030$$
Le capital disponible à la fin de la première année est de $1\,030\text{ \euro}$.

De même, à la fin de la deuxième année, le capital est égal à $1{,}03$ fois le capital de l'année précédente :
$$u_2 = u_1 \times 1{,}03 = 1\,030 \times 1{,}03 = 1\,060{,}90$$
Le capital disponible à la fin de la deuxième année est de $1\,060{,}90\text{ \euro}$.

### 2. Relation de récurrence et nature de la suite
Chaque année, le capital est multiplié par le coefficient multiplicateur associé à une hausse de $3\,\%$, c'est-à-dire $1 + \frac{3}{100} = 1{,}03$. 
Pour tout entier naturel $n$, on a la relation de récurrence :
$$u_{n+1} = 1{,}03 \times u_n$$

Cette relation montre que chaque terme s'obtient en multipliant le terme précédent par une constante non nulle $q = 1{,}03$. Par conséquent, la suite $(u_n)$ est une **suite géométrique** de raison $q = 1{,}03$ et de premier terme $u_0 = 1\,000$.

### 3. Expression du terme général
Le terme général d'une suite géométrique de premier terme $u_0$ et de raison $q$ est donné par la formule :
$$u_n = u_0 \times q^n$$
En remplaçant $u_0$ et $q$ par leurs valeurs respectives, on obtient pour tout entier naturel $n$ :
$$u_n = 1\,000 \times (1{,}03)^n$$

### 4. Calcul du capital au bout de 10 ans
Pour $n = 10$, on calcule :
$$u_{10} = 1\,000 \times (1{,}03)^{10}$$
À l'aide d'une calculatrice, on trouve :
$$(1{,}03)^{10} \approx 1{,}343916$$
D'où :
$$u_{10} \approx 1\,000 \times 1{,}343916 = 1\,343{,}916$$
Arrondi au centime près, le capital disponible au bout de 10 ans est de **$1\,343{,}92\text{ \euro}$**.

### 5. Recherche du doublement du capital
Le capital initial est de $1\,000\text{ \euro}$. Doubler le capital signifie atteindre ou dépasser la somme de $2\,000\text{ \euro}$. On cherche donc le plus petit entier naturel $n$ tel que :
$$u_n \ge 2\,000$$
Soit :
$$1\,000 \times (1{,}03)^n \ge 2\,000$$
En simplifiant par $1\,000$ :
$$(1{,}03)^n \ge 2$$
Pour résoudre cette inéquation, on applique la fonction logarithme népérien :
$$n \ln(1{,}03) \ge \ln(2)$$
$$n \ge \frac{\ln(2)}{\ln(1{,}03)}$$
En effectuant le calcul numérique :
$$\frac{\ln(2)}{\ln(1{,}03)} \approx \frac{0{,}693147}{0{,}029558} \approx 23{,}45$$

Puisque $n$ représente un nombre d'années entières, il faut arrondir à l'entier supérieur. Au bout de **24 ans**, le capital aura dépassé $2\,000\text{ \euro}$ (en effet, $u_{23} \approx 1\,980\text{ \euro}$ et $u_{24} \approx 2\,039\text{ \euro}$).
