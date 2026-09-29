"""
Pruebas de coherencia de resultados/ ANTES de construir el HTML.

Comprueba que el motor dejó todo lo que las páginas necesitan y que las cifras son coherentes
entre sí (optimización incluida). Si algo falla, construir_html.py no arranca.

Uso:  python motor/test_resultados.py          (también lo llama construir_html.py automáticamente)
Sale con código 0 si todo está OK, 1 si hay fallos. Los avisos no bloquean.
"""
import json, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RES, G = RAIZ / "resultados", RAIZ / "resultados" / "graficos"
GRAFICOS = ["01_equity", "02_operaciones_ano", "03_libro_vs_tis", "04_grid", "05_montecarlo", "06_monkey", "07_pf_anual", "08_underwater",
            "09_walkforward", "10_riesgo", "11_robustez_4d", "11b_robustez_barras", "11_robustez_mapas", "12_robustez_dist", "13_aed_forward",
            "14_aed_rachas", "15_aed_regimen", "16_operacion_ejemplo", "17_atr", "18_aed_colas", "19_meses", "20_dd_bins"]
fallos, avisos = [], []


def ok(cond, msg):
    if not cond: fallos.append(msg)


def aviso(cond, msg):
    if not cond: avisos.append(msg)


def num(x):
    return isinstance(x, (int, float)) and x == x  # no NaN


# ------------------------------------------------------------------ ficheros
for f in ["metricas.json", "equity_semanal.json", "trades.csv", "equity_diaria.csv"]:
    ok((RES / f).exists(), f"falta resultados/{f}")
for g in GRAFICOS:
    p = G / f"{g}.png"; ok(p.exists() and p.stat().st_size > 5000, f"falta o está vacío el gráfico {g}.png")
if fallos:
    print("FALLOS:\n- " + "\n- ".join(fallos)); sys.exit(1)

M = json.loads((RES / "metricas.json").read_text(encoding="utf-8"))
SEM = json.loads((RES / "equity_semanal.json").read_text(encoding="utf-8"))

# ------------------------------------------------------------------ meta
meta = M["meta"]
for k in ["activo", "fuente", "desde", "hasta", "velas", "rsi", "sma", "is_desde", "is_hasta", "oos_desde", "oos_hasta", "generado"]:
    ok(k in meta and meta[k] not in (None, ""), f"meta.{k} vacío")
ok(meta["is_hasta"] < meta["oos_desde"], "la construcción no termina antes de que empiece la validación")
ok(meta["velas"] > 1000, f"muy pocas velas ({meta['velas']})")
aviso("Yahoo" not in meta["fuente"] or "Norgate" not in meta["fuente"], "fuente ambigua (Yahoo y Norgate a la vez)")

# ------------------------------------------------------------------ fase 1
f1 = M["fase1"]; I, O, T = f1["IS"], f1["OOS"], f1["TODO"]
for nombre, m in [("IS", I), ("OOS", O), ("TODO", T), ("OOS_atr", f1["OOS_atr"]), ("TODO_atr", f1["TODO_atr"]), ("OOS_atr2", f1["OOS_atr2"]), ("OOS_x2", f1["OOS_x2"])]:
    for k in ["n", "pf", "pfnb", "mdd", "wr", "expectancy", "ret_total", "cagr", "mdd_diario"]:
        ok(k in m and num(m[k]), f"fase1.{nombre}.{k} falta o no es número")
    ok(m["pfnb"] <= m["pf"] + 1e-9, f"fase1.{nombre}: PF sin mejor trade ({m['pfnb']:.2f}) > PF ({m['pf']:.2f})")
    ok(-1 <= m["mdd_diario"] <= m["mdd"] + 1e-9, f"fase1.{nombre}: el drawdown día a día ({m['mdd_diario']:.3f}) debería ser ≤ operación a operación ({m['mdd']:.3f})")
    ok(0 <= m["wr"] <= 1, f"fase1.{nombre}: win rate fuera de [0,1]")
ok(abs(I["n"] + O["n"] - T["n"]) <= 1, f"IS ({I['n']}) + OOS ({O['n']}) ≠ total ({T['n']})")
crit = f1["criterios"]
ok(crit["pf"] == (O["pf"] >= 1.3), "criterio PF OOS mal evaluado")
ok(crit["n"] == (O["n"] >= 30), "criterio N OOS mal evaluado")
ok(crit["mdd"] == (O["mdd"] > -0.20), "criterio MaxDD OOS mal evaluado")
ok(crit["pfnb"] == ((O["pfnb"] or 0) > 1.0), "criterio PF sin mejor trade mal evaluado")
ok(f1["pasa"] == all(crit.values()), "fase1.pasa no coincide con sus criterios")
# sizings: más riesgo → más retorno y más drawdown (o igual)
ok(f1["TODO_atr"]["ret_total"] <= f1["TODO_atr2"]["ret_total"] + 1e-9 <= T["ret_total"] + 1e-9, "los retornos por sizing no están ordenados (1 % ≤ 2 % ≤ 100 %)")
ok(f1["TODO_atr"]["mdd_diario"] >= f1["TODO_atr2"]["mdd_diario"] - 1e-9 >= T["mdd_diario"] - 1e-9, "los drawdowns por sizing no están ordenados (1 % ≤ 2 % ≤ 100 %)")
ok(f1["TODO_x2"]["mdd_diario"] <= T["mdd_diario"] + 1e-9, "el apalancado 1:2 debería tener más drawdown que el 100 %")

# ------------------------------------------------------------------ control y libro
ok(num(M["control_salida_cierre_a_cierre"]["pf"]), "falta el control de salida cierre-a-cierre")
lb = M["libro"]; ok(num(lb["TODO"]["pf"]) and num(lb["OOS"]["pf"]) and lb["TODO"]["n"] > 30, "métricas del libro incompletas")

# ------------------------------------------------------------------ fase 2
f2 = M["fase2"]
ok(len(f2["ventanas"]) >= 10, f"walk-forward con pocas ventanas ({len(f2['ventanas'])})")
ok(num(f2.get("eficiencia")) and num(f2["pct_positivas"]) and num(f2["peor_mdd"]), "walk-forward sin eficiencia / % positivas / peor mdd")
ok(f2["pasa"] == (f2["eficiencia"] >= 0.5 and f2["pct_positivas"] >= 0.6 and f2["peor_mdd"] > -0.20), "fase2.pasa no coincide con sus criterios")
anos = [v["ano"] for v in f2["ventanas"]]; ok(anos == sorted(anos) and len(set(anos)) == len(anos), "ventanas del walk-forward desordenadas o repetidas")

# ------------------------------------------------------------------ fase 3 (optimización)
f3 = M["fase3"]; RS, SM = f3["rsi"], f3["sma"]
ok(meta["rsi"] in RS and meta["sma"] in SM, f"la configuración que opera (RSI {meta['rsi']}, SMA {meta['sma']}) no está en la rejilla")
ia, ib = RS.index(meta["rsi"]), SM.index(meta["sma"])
ok(0 < ia < len(RS) - 1 and 0 < ib < len(SM) - 1, "la configuración que opera está en el borde de la rejilla: no hay meseta 3×3 evaluable")
pf = f3["pf"]; nn = f3["n"]
ok(all(num(v) and v > 0 for fila in pf for v in fila), "hay celdas vacías o no numéricas en la rejilla")
ok(abs(pf[ia][ib] - f3["centro"]) < 1e-3, "fase3.centro no coincide con la celda de la rejilla")
ok(abs(pf[ia][ib] - I["pf"]) < 0.02, f"el PF de la celda que opera ({pf[ia][ib]:.3f}) no coincide con el PF IS de la Fase 1 ({I['pf']:.3f})")
vec = [pf[a][b] for a in range(ia - 1, ia + 2) for b in range(ib - 1, ib + 2)]; nvec = [nn[a][b] for a in range(ia - 1, ia + 2) for b in range(ib - 1, ib + 2)]
meseta = all(v >= 1.3 for v in vec) and all(n >= 30 for n in nvec)
ok(f3["meseta_3x3"] == meseta, "fase3.meseta_3x3 no coincide con la rejilla")
caida = max(1 - v / f3["centro"] for v in vec) * 100
ok(abs(caida - f3["peor_caida_vecino_pct"]) < 0.5, "fase3.peor_caida_vecino_pct no coincide con la rejilla")
ok(f3["anticliff"] == (caida <= 30), "fase3.anticliff mal evaluado")
ok(f3["pasa"] == (meseta and caida <= 30), "fase3.pasa no coincide con sus criterios")
ok(f3["optimo"]["pf"] >= f3["centro"], "el óptimo del grid es menor que el centro")
aviso(f3["optimo"]["rsi"] != meta["rsi"] or f3["optimo"]["sma"] != meta["sma"], "la configuración que opera ES el óptimo del grid: revisar que no se eligió el pico")

r4 = M["robustez_4d"]
ok(r4["n_combos"] == len(r4["rsi"]) * len(r4["sma"]) * len(r4["salidas"]) * len(r4["costes"]), "robustez_4d: n_combos no cuadra")
for k in r4["cubos"]:
    ok(k in r4["cubos_mdd"] and k in r4["cubos_n"], f"robustez_4d: falta mdd o n para '{k}'")
    ok(all(num(v) for fila in r4["cubos"][k] for v in fila), f"robustez_4d: valores no numéricos en '{k}'")
base = next(k for k in r4["cubos"] if k.startswith("Dos velas verdes") and "5 bps" in k)
ok(abs(r4["cubos"][base][ia][ib] - pf[ia][ib]) < 1e-6, "robustez_4d: el cubo base no coincide con la rejilla de la Fase 3")
ok(abs(r4["pf_vigente"] - pf[ia][ib]) < 1e-3, "robustez_4d.pf_vigente no coincide con la celda que opera")
ok(0 <= r4["percentil_vigente"] <= 1 and 0 <= r4["pct_pf13"] <= 1, "robustez_4d: percentiles fuera de rango")
ok(r4["por_coste"][r4["costes"][0]] >= r4["por_coste"][r4["costes"][1]], "robustez_4d: con más coste el PF medio debería bajar")

# ------------------------------------------------------------------ fase 4
for nombre in ["fase4", "fase4_atr"]:
    f4 = M[nombre]
    ok(f4["n_sim"] >= 5000, f"{nombre}: menos de 5.000 simulaciones")
    ok(f4["p5_ret"] <= f4["p50_ret"] <= f4["p95_ret"], f"{nombre}: percentiles de retorno desordenados")
    ok(f4["mdd_p5"] <= f4["mdd_p50"] <= f4["mdd_p95"] <= 0, f"{nombre}: percentiles de drawdown desordenados")
    ok(f4["mdd_peor"] <= f4["mdd_p5"], f"{nombre}: el peor drawdown no es peor que el p5")
    ok(0 <= f4["prob_ruina"] <= 1 and 0 <= f4["prob_mdd_25"] <= 1, f"{nombre}: probabilidades fuera de rango")
    ok(f4["pasa"] == (f4["p5_ret"] > 0 and f4["mdd_p5"] > -0.25 and f4["prob_ruina"] < 0.05), f"{nombre}.pasa no coincide con sus criterios")
ok(M["fase4_atr"]["mdd_p5"] >= M["fase4"]["mdd_p5"], "el Monte Carlo con 1 % ATR debería tener menos drawdown que con 100 %")

# ------------------------------------------------------------------ fase 5
f5 = M["fase5"]
ok(f5["costes_x2"]["n"] == O["n"], "estrés costes×2 no tiene las mismas operaciones que la validación")
ok(f5["costes_x2"]["pf"] <= O["pf"] + 1e-9, "con el doble de costes el PF no puede subir")
ok(len(f5["sin_2_mejores_anos"]["anos"]) == 2 and f5["sin_2_mejores_anos"]["n"] < O["n"], "estrés sin 2 mejores años mal construido")
ok(f5["pasa"] == (f5["costes_x2"]["pasa"] and f5["sin_2_mejores_anos"]["pasa"]), "fase5.pasa no coincide con sus criterios")

# ------------------------------------------------------------------ mono, AED, desgaste, drawdowns, mensual
mk = M["monkey"]; ok(mk["n_sim"] >= 1000 and 0 <= mk["pct_pf"] <= 1 and abs(mk["pf_real"] - T["pf"]) < 1e-6, "monkey test incompleto o PF real distinto del total")
ae = M["aed"]; ks = list(ae["forward"].keys())
ok(len(ks) == 4 and all(str(h) in ae["forward"][ks[0]] for h in ae["horizontes"]), "AED forward incompleto")
ok(0 < ae["pct_sobre_sma"] < 1 and ae["senales_ano_media"] > 0 and len(ae["autocorr"]) == 10, "AED: régimen / señales / autocorrelación incompletos")
ed = M["edge_decay"]; ok(len(ed["anual"]) >= 10 and len(ed["movil"]) > 50 and num(ed["ultimos_3"]["pf"]), "edge decay incompleto")
dd = M["drawdowns"]; ok(dd["n"] > 10 and len(dd["peores"]) == 5 and len(dd["bins"]) == 5 and abs(sum(b["n"] for b in dd["bins"]) - dd["n"]) == 0, "drawdowns: episodios, peores o tramos no cuadran")
ok(abs(dd["peores"][0]["prof"] - T["mdd_diario"]) < 1e-6, "la peor caída de la lista no coincide con el drawdown día a día del total")
me = M["mensual"]; ok(len(me["anos"]) == len(me["filas"]) == len(me["matriz"]) and all(len(f) == 12 for f in me["matriz"]), "mensual: matriz mal formada")
ok(me["meses_pos"] + me["meses_neg"] + me["meses_planos"] == sum(len([v for v in f if v is not None]) for f in me["matriz"]), "mensual: el recuento de meses no cuadra")
sz = M["sizing"]; ok(0 < sz["exposicion_media_1pct"] < sz["exposicion_media_2pct"] <= 1 and sz["ejemplo"]["atr"] > 0, "sizing: exposiciones o ejemplo de ATR incoherentes")

# ------------------------------------------------------------------ curvas para el gráfico interactivo
ok(all(k in SEM for k in ["fechas", "oos", "capital", "fijo", "atr1", "atr2", "x2"]), "equity_semanal.json incompleto")
ok(len({len(SEM[k]) for k in ["fechas", "capital", "fijo", "atr1", "atr2", "x2"]}) == 1, "equity_semanal.json: series de distinta longitud")
ok(abs(SEM["capital"][-1] - (1 + T["ret_total"])) < 0.05, "la curva semanal no termina donde dice el retorno total")

# ------------------------------------------------------------------ veredicto
v = M["veredicto"]
ok(v["fase1"] == f1["pasa"] and v["fase2"] == f2["pasa"] and v["fase3"] == f3["pasa"] and v["fase5"] == f5["pasa"], "veredicto no coincide con las fases")
ok(v["fase4"] in (M["fase4"]["pasa"], M["fase4_atr"]["pasa"]), "veredicto.fase4 no corresponde a ningún Monte Carlo calculado")
aviso(all(v.values()), "hay fases NO superadas: " + ", ".join(k for k, x in v.items() if not x) + " (revisar con Mariel antes de publicar)")

# ------------------------------------------------------------------ informe
print(f"Pruebas de resultados · {meta['activo']} · {meta['fuente']} · {meta['desde']} → {meta['hasta']} · generado {meta['generado']}")
print(f"  IS {I['n']} / OOS {O['n']} / total {T['n']} · PF OOS {O['pf']:.2f} · grid {len(RS)}×{len(SM)} centro {f3['centro']:.2f} meseta {f3['meseta_3x3']} · MC {M['fase4']['n_sim']} · veredicto {v}")
if avisos: print("AVISOS:\n- " + "\n- ".join(avisos))
if fallos:
    print("FALLOS:\n- " + "\n- ".join(fallos)); sys.exit(1)
print(f"OK · {len(GRAFICOS)} gráficos · 0 fallos · {len(avisos)} avisos")
