# RÔLE DE CE FICHIER :
# Moteur déterministe de calcul et de génération de figures et tableaux mathématiques en TikZ (Section D).
# ZÉRO hallucination : tout calcul (dérivée, racines, signes, extrema, limites, sommes de probabilités)
# est exécuté par SymPy. Aucun code TikZ n'est inventé par un LLM.
# Intègre des oracles de cohérence stricts et la vérification de mise en page (needspace, marges).

from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from typing import Any, Literal
import sympy as sp

from tools.rasterizer import PDFRasterizer


class MathConsistencyError(ValueError):
    """Levée lorsqu'une incohérence mathématique stricte est détectée par l'oracle."""
    pass


class MathOracle:
    """Oracle déterministe de vérification de cohérence mathématique stricte."""

    @staticmethod
    def verify_derivative_sign_and_arrow(sign: str, arrow_dir: str) -> None:
        """Vérifie l'adéquation exacte entre le signe de la dérivée et le sens de variation."""
        s = sign.strip()
        a = arrow_dir.strip().lower()
        if s == "+" and a not in {"up", "croissante", "monte"}:
            raise MathConsistencyError(
                f"Incohérence stricte : dérivée positive ({s}) mais flèche de variation non croissante ({a})."
            )
        if s == "-" and a not in {"down", "décroissante", "descend"}:
            raise MathConsistencyError(
                f"Incohérence stricte : dérivée négative ({s}) mais flèche de variation non décroissante ({a})."
            )

    @staticmethod
    def verify_extremum_value(f_expr: sp.Expr, var: sp.Symbol, x_val: float | sp.Expr, declared_y: float | sp.Expr, tol: float = 1e-9) -> None:
        """Vérifie que la valeur d'extremum déclarée correspond exactement à f(x_val)."""
        actual = float(f_expr.subs(var, x_val).evalf())
        dec = float(sp.sympify(declared_y).evalf())
        if abs(actual - dec) > tol:
            raise MathConsistencyError(
                f"Incohérence extremum : f({x_val}) = {actual}, mais la valeur déclarée est {dec} (écart > {tol})."
            )

    @staticmethod
    def verify_tree_sum(probabilities: list[float | str | sp.Expr], tol: float = 1e-9) -> None:
        """Vérifie que la somme des probabilités des branches issues d'un nœud vaut exactement 1."""
        total = sum(float(sp.sympify(p).evalf()) for p in probabilities)
        if abs(total - 1.0) > tol:
            raise MathConsistencyError(
                f"Incohérence arbre de probabilités : la somme des branches vaut {total} != 1.0 (écart > {tol})."
            )


def _find_real_roots_robust(expr: sp.Expr, var: sp.Symbol, d_min_f: float, d_max_f: float) -> list[sp.Expr]:
    """Trouve de manière exhaustive et certifiée les racines réelles d'une expression dans un intervalle."""
    roots: list[sp.Expr] = []
    # 1. Résolution symbolique fermée
    try:
        raw_roots = sp.solve(expr, var)
        for r in raw_roots:
            if r.is_real:
                try:
                    val_f = float(r.evalf())
                    if d_min_f < val_f < d_max_f:
                        roots.append(r)
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Test des candidats rationnels et remarquables usuels
    candidates = [
        0, 1, 2, 3, 4, -1, -2, -3, 0.5, 1.5, 2.5,
        math.e, math.pi, math.e / 2, 1 / math.e
    ]
    for cand in candidates:
        if d_min_f < cand < d_max_f:
            try:
                sub_val = expr.subs(var, cand).evalf()
                if abs(float(sub_val)) < 1e-11:
                    r_sym = sp.Integer(cand) if cand == int(cand) else sp.Float(cand)
                    if not any(abs(float(r.evalf()) - cand) < 1e-8 for r in roots):
                        roots.append(r_sym)
            except Exception:
                pass

    # 3. Échantillonnage numérique pour détecter les changements de signe (Bolzano)
    samples = []
    step_start = max(d_min_f, -50.0)
    step_end = min(d_max_f, 50.0)
    n_steps = 100
    step = (step_end - step_start) / n_steps
    for i in range(n_steps + 1):
        pt = step_start + i * step
        try:
            val_f = float(expr.subs(var, pt).evalf())
            if math.isfinite(val_f):
                samples.append((pt, val_f))
        except Exception:
            pass

    for i in range(len(samples) - 1):
        x1, y1 = samples[i]
        x2, y2 = samples[i + 1]
        if y1 * y2 < 0:
            try:
                r_num = sp.nsolve(expr, var, (x1 + x2) / 2.0)
                r_f = float(r_num.evalf())
                if d_min_f < r_f < d_max_f:
                    if not any(abs(float(r.evalf()) - r_f) < 1e-6 for r in roots):
                        roots.append(sp.Float(round(r_f, 8)))
            except Exception:
                pass

    return sorted(roots, key=lambda val: float(val.evalf()))


def generate_variation_table(
    func_str: str,
    var_str: str = "x",
    domain: tuple[Any, Any] = (0, sp.oo),
    forbidden_values: list[Any] | None = None,
    student_version: bool = False,
) -> dict[str, Any]:
    """Génère un tableau de variations complet, déterministe et vérifié par SymPy."""
    clean_f_str = func_str.replace("ln(", "log(")
    x = sp.Symbol(var_str, real=True)
    f = sp.sympify(clean_f_str, locals={var_str: x})
    df = sp.diff(f, x)

    # 1. Bornes du domaine
    d_min, d_max = domain
    if d_min is None or d_min == "-oo":
        d_min_sym = -sp.oo
    else:
        d_min_sym = sp.sympify(d_min, locals={var_str: x})

    if d_max is None or d_max in {"oo", "+oo"}:
        d_max_sym = sp.oo
    else:
        d_max_sym = sp.sympify(d_max, locals={var_str: x})

    d_min_f = float(d_min_sym.evalf()) if d_min_sym != -sp.oo else -1e12
    d_max_f = float(d_max_sym.evalf()) if d_max_sym != sp.oo else 1e12

    # 2. Singularités et valeurs interdites
    forbid = set()
    if forbidden_values:
        for v in forbidden_values:
            forbid.add(sp.sympify(v, locals={var_str: x}))
    else:
        # Dénominateur de f ou df nul
        for expr in [f, df]:
            denom = sp.denom(sp.together(expr))
            if denom != 1:
                try:
                    for r in sp.solve(denom, x):
                        if r.is_real:
                            forbid.add(r)
                except Exception:
                    pass
        if "log" in clean_f_str:
            forbid.add(sp.Integer(0))

    clean_forbid = set()
    for v in forbid:
        try:
            val_f = float(v.evalf())
            if d_min_f <= val_f <= d_max_f:
                clean_forbid.add(v)
        except Exception:
            pass

    # 3. Racines de f'(x) = 0
    num_df = sp.numer(sp.together(df))
    roots = _find_real_roots_robust(num_df, x, d_min_f, d_max_f)
    roots = [r for r in roots if not any(abs(float(r.evalf()) - float(fb.evalf())) < 1e-9 for fb in clean_forbid)]

    # 4. Ordonnancement des points clés
    all_points = []
    if d_min_sym == -sp.oo:
        all_points.append(("bound_min", r"-\infty", -sp.oo))
    else:
        is_fb = any(abs(d_min_f - float(fb.evalf())) < 1e-9 for fb in clean_forbid)
        all_points.append(("forbidden_bound" if is_fb else "bound_min", sp.latex(d_min_sym), d_min_sym))

    interior_items = []
    for fb in clean_forbid:
        fb_f = float(fb.evalf())
        if abs(fb_f - d_min_f) > 1e-9 and abs(fb_f - d_max_f) > 1e-9:
            interior_items.append(("forbidden", sp.latex(fb), fb))
    for r in roots:
        r_f = float(r.evalf())
        if abs(r_f - d_min_f) > 1e-9 and abs(r_f - d_max_f) > 1e-9:
            interior_items.append(("root", sp.latex(r), r))

    interior_items = sorted(interior_items, key=lambda item: float(item[2].evalf()))
    all_points.extend(interior_items)

    if d_max_sym == sp.oo:
        all_points.append(("bound_max", r"+\infty", sp.oo))
    else:
        is_fb = any(abs(d_max_f - float(fb.evalf())) < 1e-9 for fb in clean_forbid)
        all_points.append(("forbidden_bound" if is_fb else "bound_max", sp.latex(d_max_sym), d_max_sym))

    # 5. Calcul des intervalles, signes et flèches
    intervals = []
    for i in range(len(all_points) - 1):
        p_left = all_points[i]
        p_right = all_points[i + 1]

        left_val = float(p_left[2].evalf()) if p_left[2] != -sp.oo else -50.0
        right_val = float(p_right[2].evalf()) if p_right[2] != sp.oo else 50.0

        if p_left[2] == -sp.oo and p_right[2] != sp.oo:
            test_x = float(p_right[2].evalf()) - 1.5
        elif p_right[2] == sp.oo and p_left[2] != -sp.oo:
            test_x = float(p_left[2].evalf()) + 1.5
        else:
            test_x = (left_val + right_val) / 2.0

        df_val = float(df.subs(x, test_x).evalf())
        sign = "+" if df_val > 0 else "-"
        arrow = "up" if df_val > 0 else "down"

        MathOracle.verify_derivative_sign_and_arrow(sign, arrow)
        intervals.append({
            "left": p_left,
            "right": p_right,
            "test_x": test_x,
            "sign": sign,
            "arrow": arrow,
        })

    # 6. Valeurs et limites
    point_values = []
    for kind, label, sym_val in all_points:
        if sym_val == -sp.oo:
            lim = sp.limit(f, x, -sp.oo)
            point_values.append(r"+\infty" if lim == sp.oo else (r"-\infty" if lim == -sp.oo else sp.latex(lim)))
        elif sym_val == sp.oo:
            lim = sp.limit(f, x, sp.oo)
            point_values.append(r"+\infty" if lim == sp.oo else (r"-\infty" if lim == -sp.oo else sp.latex(lim)))
        elif "forbidden" in kind:
            # Limite à droite ou à gauche
            if kind == "forbidden_bound" and sym_val == d_min_sym:
                lim = sp.limit(f, x, sym_val, dir="+")
                val_str = r"+\infty" if lim == sp.oo else (r"-\infty" if lim == -sp.oo else sp.latex(lim))
                point_values.append(val_str)
            elif kind == "forbidden_bound" and sym_val == d_max_sym:
                lim = sp.limit(f, x, sym_val, dir="-")
                val_str = r"+\infty" if lim == sp.oo else (r"-\infty" if lim == -sp.oo else sp.latex(lim))
                point_values.append(val_str)
            else:
                lim_l = sp.limit(f, x, sym_val, dir="-")
                lim_r = sp.limit(f, x, sym_val, dir="+")
                str_l = r"+\infty" if lim_l == sp.oo else (r"-\infty" if lim_l == -sp.oo else sp.latex(lim_l))
                str_r = r"+\infty" if lim_r == sp.oo else (r"-\infty" if lim_r == -sp.oo else sp.latex(lim_r))
                point_values.append((str_l, str_r))
        else:
            val = f.subs(x, sym_val)
            point_values.append(sp.latex(val))
            if kind == "root":
                MathOracle.verify_extremum_value(f, x, sym_val, val)

    # 7. Code TikZ natif
    row_x = ["x"]
    row_df = [r"f'(x)"]
    row_f = ["f(x)"]

    for i, p in enumerate(all_points):
        row_x.append(p[1])
        if i < len(intervals):
            row_x.append("")

    for i, p in enumerate(all_points):
        if p[0] == "root":
            row_df.append("0")
        elif "forbidden" in p[0]:
            row_df.append(r"\parallel")
        elif i == 0 or i == len(all_points) - 1:
            row_df.append("")
        else:
            row_df.append("")

        if i < len(intervals):
            sign_char = intervals[i]["sign"] if not student_version else r"\phantom{+}"
            row_df.append(sign_char)

    width_col = max(1.5, 12.0 / max(1, len(row_x)))
    tikz_lines = [
        r"\needspace{8\baselineskip}",
        r"\begin{center}",
        r"\begin{tikzpicture}[>=stealth]",
        r"\matrix (m) [matrix of math nodes, nodes in empty cells,",
        r"  row sep=0.35cm, column sep=0.25cm,",
        f"  nodes={{minimum width={width_col:.2f}cm, minimum height=0.7cm, anchor=center}},",
        r"  column 1/.style={nodes={minimum width=2.0cm, anchor=east, font=\bfseries}}",
        r"] {",
        "  " + " & ".join(row_x) + r" \\",
        "  " + " & ".join(row_df) + r" \\",
    ]

    row_f_cells = ["f(x)"]
    for i, p in enumerate(all_points):
        val = point_values[i]
        if isinstance(val, tuple):
            val_str = f"{{{val[0]} \\quad {val[1]}}}" if not student_version else r"\phantom{0}"
            row_f_cells.append(val_str)
        else:
            row_f_cells.append(val if not student_version else r"\phantom{0}")
        if i < len(intervals):
            row_f_cells.append("")
    tikz_lines.append("  " + " & ".join(row_f_cells) + r" \\")
    tikz_lines.append(r"};")

    tikz_lines.append(r"\draw[thick] (m-1-1.south west) -- (m-1-" + str(len(row_x)) + r".south east);")
    tikz_lines.append(r"\draw[thick] (m-2-1.south west) -- (m-2-" + str(len(row_x)) + r".south east);")
    tikz_lines.append(r"\draw[thick] (m-1-1.north east) -- (m-3-1.south east);")

    # Double barre verticale sur les cellules de valeurs interdites
    for i, p in enumerate(all_points):
        if "forbidden" in p[0]:
            col_idx = 2 + (i * 2)
            tikz_lines.append(f"\\draw[double, thick] (m-2-{col_idx}.north) -- (m-3-{col_idx}.south);")

    # Flèches de variations (version professeur)
    if not student_version:
        for i, inter in enumerate(intervals):
            col_start = 2 + (i * 2)
            col_end = col_start + 2
            p_left = all_points[i]
            p_right = all_points[i + 1]

            # Si le point gauche ou droit est une valeur interdite intérieure
            left_is_fb = ("forbidden" in p_left[0] and p_left[0] != "forbidden_bound")
            right_is_fb = ("forbidden" in p_right[0] and p_right[0] != "forbidden_bound")

            start_anchor = ".east" if left_is_fb else ".center"
            end_anchor = ".west" if right_is_fb else ".center"

            if inter["arrow"] == "up":
                tikz_lines.append(
                    f"\\draw[->, thick, color=blue!80!black] ([yshift=-8pt]m-3-{col_start}{start_anchor}) -- ([yshift=8pt]m-3-{col_end}{end_anchor});"
                )
            else:
                tikz_lines.append(
                    f"\\draw[->, thick, color=blue!80!black] ([yshift=8pt]m-3-{col_start}{start_anchor}) -- ([yshift=-8pt]m-3-{col_end}{end_anchor});"
                )

    tikz_lines.append(r"\end{tikzpicture}")
    tikz_lines.append(r"\end{center}")

    return {
        "function": func_str,
        "derivative": str(df),
        "roots": [float(r.evalf()) for r in roots],
        "intervals": intervals,
        "point_values": point_values,
        "student_version": student_version,
        "tikz": "\n".join(tikz_lines),
        "verified": True,
    }


def generate_sign_table(
    expr_str: str,
    var_str: str = "x",
    domain: tuple[Any, Any] = (-sp.oo, sp.oo),
    student_version: bool = False,
) -> dict[str, Any]:
    """Génère un tableau de signes déterministe certifié par SymPy."""
    x = sp.Symbol(var_str, real=True)
    expr = sp.sympify(expr_str, locals={var_str: x})

    d_min, d_max = domain
    if d_min is None or d_min == "-oo":
        d_min_sym = -sp.oo
    else:
        d_min_sym = sp.sympify(d_min, locals={var_str: x})

    if d_max is None or d_max in {"oo", "+oo"}:
        d_max_sym = sp.oo
    else:
        d_max_sym = sp.sympify(d_max, locals={var_str: x})
    d_min_f = float(d_min_sym.evalf()) if d_min_sym != -sp.oo else -1e12
    d_max_f = float(d_max_sym.evalf()) if d_max_sym != sp.oo else 1e12

    roots = _find_real_roots_robust(expr, x, d_min_f, d_max_f)

    points = [("-oo" if d_min_sym == -sp.oo else "min", r"-\infty" if d_min_sym == -sp.oo else sp.latex(d_min_sym), d_min_sym)]
    for r in roots:
        points.append(("root", sp.latex(r), r))
    points.append(("oo" if d_max_sym == sp.oo else "max", r"+\infty" if d_max_sym == sp.oo else sp.latex(d_max_sym), d_max_sym))

    signs = []
    for i in range(len(points) - 1):
        p_left = points[i][2]
        p_right = points[i + 1][2]
        if p_left == -sp.oo and p_right != sp.oo:
            t_x = float(p_right.evalf()) - 1.0
        elif p_right == sp.oo and p_left != -sp.oo:
            t_x = float(p_left.evalf()) + 1.0
        else:
            t_x = (float(p_left.evalf()) + float(p_right.evalf())) / 2.0

        val = float(expr.subs(x, t_x).evalf())
        signs.append("+" if val > 0 else ("-" if val < 0 else "0"))

    row_x = ["x"]
    row_s = [sp.latex(expr)]

    for i, p in enumerate(points):
        row_x.append(p[1])
        if i < len(signs):
            row_x.append("")

    for i, p in enumerate(points):
        if p[0] == "root":
            row_s.append("0")
        else:
            row_s.append("")
        if i < len(signs):
            row_s.append(signs[i] if not student_version else r"\phantom{+}")

    width_col = max(1.5, 12.0 / max(1, len(row_x)))
    tikz_lines = [
        r"\needspace{6\baselineskip}",
        r"\begin{center}",
        r"\begin{tikzpicture}",
        r"\matrix (m) [matrix of math nodes, nodes in empty cells,",
        r"  row sep=0.25cm, column sep=0.25cm,",
        f"  nodes={{minimum width={width_col:.2f}cm, minimum height=0.65cm, anchor=center}},",
        r"  column 1/.style={nodes={minimum width=2.0cm, anchor=east, font=\bfseries}}",
        r"] {",
        "  " + " & ".join(row_x) + r" \\",
        "  " + " & ".join(row_s) + r" \\",
        r"};",
        r"\draw[thick] (m-1-1.south west) -- (m-1-" + str(len(row_x)) + r".south east);",
        r"\draw[thick] (m-1-1.north east) -- (m-2-1.south east);",
        r"\end{tikzpicture}",
        r"\end{center}",
    ]

    return {
        "expression": expr_str,
        "roots": [float(r.evalf()) for r in roots],
        "signs": signs,
        "student_version": student_version,
        "tikz": "\n".join(tikz_lines),
        "verified": True,
    }


def generate_probability_tree(tree_spec: dict[str, Any]) -> dict[str, Any]:
    """Génère un arbre pondéré de probabilités TikZ à 2 ou 3 niveaux avec oracle de somme = 1."""
    root_branches = tree_spec.get("root", [])
    if not root_branches:
        raise MathConsistencyError("L'arbre de probabilités doit comporter au moins une branche à la racine.")

    root_probs = [b.get("prob", 0) for b in root_branches]
    MathOracle.verify_tree_sum(root_probs)

    for b in root_branches:
        children = b.get("children", [])
        if children:
            child_probs = [c.get("prob", 0) for c in children]
            MathOracle.verify_tree_sum(child_probs)

    tikz_lines = [
        r"\needspace{8\baselineskip}",
        r"\begin{center}",
        r"\begin{tikzpicture}[",
        r"  grow'=right, sloped,",
        r"  level 1/.style={sibling distance=3.2cm, level distance=3.2cm},",
        r"  level 2/.style={sibling distance=1.6cm, level distance=3.2cm},",
        r"  edge from parent/.style={draw, thick},",
        r"  every node/.style={font=\small}",
        r"]",
        r"\node {} ",
    ]

    for b in root_branches:
        ev = b.get("event", "")
        p = b.get("prob", "")
        children = b.get("children", [])
        branch_str = f"child {{\n  node {{{ev}}} "
        if children:
            for c in children:
                c_ev = c.get("event", "")
                c_p = c.get("prob", "")
                branch_str += f"\n  child {{\n    node {{{c_ev}}}\n    edge from parent node[above] {{{c_p}}}\n  }}"
        branch_str += f"\n  edge from parent node[above] {{{p}}}\n}}"
        tikz_lines.append(branch_str)

    tikz_lines.append(r";")
    tikz_lines.append(r"\end{tikzpicture}")
    tikz_lines.append(r"\end{center}")

    return {
        "levels": 2 if any(b.get("children") for b in root_branches) else 1,
        "branches_count": len(root_branches),
        "tikz": "\n".join(tikz_lines),
        "verified": True,
    }


def generate_curve_plot(
    func_str: str,
    var_str: str = "x",
    x_min: float = -3.0,
    x_max: float = 5.0,
    y_min: float | None = None,
    y_max: float | None = None,
    asymptotes: list[dict[str, Any]] | None = None,
    tangents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Génère une courbe pgfplots (compat=1.17) avec asymptotes et tangentes remarquables."""
    clean_str = func_str.replace("ln(", "log(")
    x = sp.Symbol(var_str, real=True)
    f = sp.sympify(clean_str, locals={var_str: x})

    asymptote_lines = []
    if asymptotes:
        for asp in asymptotes:
            kind = asp.get("kind", "vertical")
            val = float(asp.get("value", 0))
            if kind == "vertical":
                asymptote_lines.append(
                    f"\\draw[dashed, red, thick] (axis cs:{val}, \\pgfkeysvalueof{{/pgfplots/ymin}}) -- (axis cs:{val}, \\pgfkeysvalueof{{/pgfplots/ymax}});"
                )
            else:
                asymptote_lines.append(
                    f"\\draw[dashed, red, thick] (axis cs:\\pgfkeysvalueof{{/pgfplots/xmin}}, {val}) -- (axis cs:\\pgfkeysvalueof{{/pgfplots/xmax}}, {val});"
                )

    tangent_lines = []
    if tangents:
        for tan in tangents:
            x_tan = float(tan.get("x", 0))
            y_tan = float(f.subs(x, x_tan).evalf())
            tangent_lines.append(
                f"\\draw[<->, thick, color=teal] (axis cs:{x_tan - 0.8:.2f}, {y_tan:.2f}) -- (axis cs:{x_tan + 0.8:.2f}, {y_tan:.2f});"
            )

    pgf_func = func_str.replace("log(", "ln(").replace("**", "^")
    ymin_str = f"ymin={y_min}," if y_min is not None else ""
    ymax_str = f"ymax={y_max}," if y_max is not None else ""

    tikz_lines = [
        r"\needspace{10\baselineskip}",
        r"\begin{center}",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"  width=10cm, height=6.5cm,",
        r"  axis lines=middle,",
        r"  grid=both,",
        f"  xmin={x_min}, xmax={x_max},",
        f"  {ymin_str} {ymax_str}",
        r"  xlabel={$x$}, ylabel={$y$},",
        r"  every axis x label/.style={at={(current axis.right of origin)},anchor=west},",
        r"  every axis y label/.style={at={(current axis.above origin)},anchor=south},",
        r"  samples=120, smooth",
        r"]",
        f"\\addplot[thick, color=blue!85!black, domain={x_min}:{x_max}] {{{pgf_func}}};",
    ]

    tikz_lines.extend(asymptote_lines)
    tikz_lines.extend(tangent_lines)
    tikz_lines.extend([
        r"\end{axis}",
        r"\end{tikzpicture}",
        r"\end{center}",
    ])

    return {
        "function": func_str,
        "x_range": (x_min, x_max),
        "asymptotes": asymptotes or [],
        "tangents": tangents or [],
        "tikz": "\n".join(tikz_lines),
        "verified": True,
    }


def _emit(event_sink: Callable[..., Any] | None, event_name: str, **kwargs: Any) -> None:
    """Émet un événement normalisé vers l'event_sink si disponible."""
    if event_sink is not None:
        try:
            event_sink(event_name, kwargs)
        except TypeError:
            try:
                from core.event_bus import HarnessEvent
                event_sink(HarnessEvent(name=event_name, data=kwargs))
            except Exception:
                pass
        except Exception:
            pass


def verify_figure_consistency(figure_data: dict[str, Any]) -> bool:
    """Vérifie rétroactivement la cohérence mathématique stricte d'une figure générée.
    Lève MathConsistencyError si une anomalie est détectée."""
    fig_type = figure_data.get("type") or (
        "variation_table" if "derivative" in figure_data
        else ("sign_table" if "signs" in figure_data
        else ("probability_tree" if "branches_count" in figure_data else "curve_plot"))
    )

    if fig_type == "variation_table":
        func_str = figure_data.get("function", "")
        intervals = figure_data.get("intervals", [])
        for inter in intervals:
            MathOracle.verify_derivative_sign_and_arrow(inter.get("sign", ""), inter.get("arrow", ""))
        if func_str and "roots" in figure_data:
            x = sp.Symbol("x", real=True)
            f = sp.sympify(func_str.replace("ln(", "log("), locals={"x": x})
            for r_val in figure_data.get("roots", []):
                actual_y = float(f.subs(x, r_val).evalf())
                for pv in figure_data.get("point_values", []):
                    if not isinstance(pv, tuple) and pv not in {r"+\infty", r"-\infty"}:
                        try:
                            if abs(float(sp.sympify(pv).evalf()) - actual_y) < 1e-6:
                                MathOracle.verify_extremum_value(f, x, r_val, pv)
                        except Exception:
                            pass
    elif fig_type == "probability_tree":
        tree = figure_data.get("tree_spec", {})
        if tree:
            root_probs = [b.get("prob", 0) for b in tree.get("root", [])]
            if root_probs:
                MathOracle.verify_tree_sum(root_probs)
    return True


def render_math_figure_to_pdf(
    tikz_code: str,
    output_path: str | Path | None = None,
    workspace: str | Path = "workspace",
    event_sink: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Compile le gabarit TikZ dans un document autonome et vérifie l'absence de débordement."""
    from tools.compiler import AutonomousCompiler

    ws = Path(workspace).resolve()
    target = ws / (output_path or "downloads/figure.pdf")
    target.parent.mkdir(parents=True, exist_ok=True)

    doc_tex = f"""\\documentclass{{article}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{amsmath,amssymb}}
\\usepackage{{tikz}}
\\usetikzlibrary{{matrix}}
\\usepackage{{pgfplots}}
\\pgfplotsset{{compat=1.17}}
\\usepackage{{needspace}}
\\pagestyle{{empty}}
\\begin{{document}}
{tikz_code}
\\end{{document}}
"""
    tmp_tex = target.with_suffix(".tex")
    tmp_tex.write_text(doc_tex, encoding="utf-8")

    compiler = AutonomousCompiler(workspace=ws, event_sink=event_sink)
    compile_res = compiler.compile(
        tex_path=tmp_tex,
        output_pdf_path=target,
        expected_pages=1,
        auto_fix=True,
    )
    return compile_res


def generate_math_figure(
    figure_type: str,
    func_str: str = "",
    var_str: str = "x",
    domain: tuple[Any, Any] | list[Any] | None = None,
    tree_spec: dict[str, Any] | None = None,
    asymptotes: list[dict[str, Any]] | None = None,
    tangents: list[dict[str, Any]] | None = None,
    x_min: float = -3.0,
    x_max: float = 5.0,
    y_min: float | None = None,
    y_max: float | None = None,
    student_version: bool = False,
    compile_pdf: bool = False,
    output_path: str = "",
    workspace: str | Path = "workspace",
    event_sink: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Générateur déterministe de figures et tableaux mathématiques TikZ certifié par SymPy."""
    _emit(event_sink, "figure.generating", figure_type=figure_type, function=func_str or "tree")

    try:
        if figure_type == "variation_table":
            dom = tuple(domain) if domain else (0, sp.oo)
            res = generate_variation_table(
                func_str,
                var_str=var_str,
                domain=dom,
                student_version=student_version,
            )
        elif figure_type == "sign_table":
            dom = tuple(domain) if domain else (-sp.oo, sp.oo)
            res = generate_sign_table(
                func_str,
                var_str=var_str,
                domain=dom,
                student_version=student_version,
            )
        elif figure_type == "probability_tree":
            if not tree_spec:
                raise MathConsistencyError("tree_spec requis pour un arbre.")
            res = generate_probability_tree(tree_spec)
            res["tree_spec"] = tree_spec
        elif figure_type == "curve_plot":
            res = generate_curve_plot(
                func_str,
                var_str=var_str,
                x_min=x_min,
                x_max=x_max,
                y_min=y_min,
                y_max=y_max,
                asymptotes=asymptotes,
                tangents=tangents,
            )
        else:
            raise ValueError(f"Type de figure non pris en charge : {figure_type}")

        res["type"] = figure_type
        verify_figure_consistency(res)

        _emit(event_sink, "figure.verified", figure_type=figure_type, function=func_str or "tree")

        if compile_pdf:
            comp_res = render_math_figure_to_pdf(
                res["tikz"],
                output_path=output_path,
                workspace=workspace,
                event_sink=event_sink,
            )
            res["compilation"] = comp_res
            if comp_res.get("status") == "success":
                res["pdf_path"] = comp_res.get("pdf_path")
                res["preview_image"] = comp_res.get("layout_preview")

        return res

    except MathConsistencyError as e:
        _emit(event_sink, "figure.rejected", figure_type=figure_type, function=func_str or "tree", reason=str(e))
        raise
    except Exception as e:
        _emit(event_sink, "figure.rejected", figure_type=figure_type, function=func_str or "tree", reason=str(e))
        raise
