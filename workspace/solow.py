# Modèle de Solow
alpha = 0.33
s = 0.3
n = 0.02

k_star = (s / n) ** (1 / (1 - alpha))
c_star = (1 - s) * (k_star ** alpha)
print(f"Capital stationnaire k* : {k_star:.2f}")
print(f"Consommation stationnaire c* : {c_star:.2f}")

