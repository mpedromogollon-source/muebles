"""Genera la memoria de calculo en PDF a partir de resultados/ .

    python modelo/memoria.py
"""
import datetime
import json
import os
import pickle
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(RAIZ, 'resultados')
FIG = os.path.join(RES, 'figuras')
SALIDA = os.path.join(RES, 'memoria_calculo_closet_PTR.pdf')

_LIB = '/usr/share/fonts/truetype/liberation/LiberationSans-'
for _n, _f in (('DV', 'Regular'), ('DVB', 'Bold'), ('DVI', 'Italic'), ('DVBI', 'BoldItalic')):
    pdfmetrics.registerFont(TTFont(_n, f'{_LIB}{_f}.ttf'))
from reportlab.pdfbase.pdfmetrics import registerFontFamily  # noqa: E402
registerFontFamily('DV', normal='DV', bold='DVB', italic='DVI', boldItalic='DVBI')

TINTA = colors.HexColor('#0b0b0b')
TINTA2 = colors.HexColor('#52514e')
REGLA = colors.HexColor('#d6d5d0')
FONDO = colors.HexColor('#f3f2ef')
OK = colors.HexColor('#e6f4ea')
MAL = colors.HexColor('#fde8e4')
ATN = colors.HexColor('#fdf3dc')

E = {
    'h1': ParagraphStyle('h1', fontName='DVB', fontSize=14, leading=18, spaceBefore=14, spaceAfter=6, textColor=TINTA),
    'h2': ParagraphStyle('h2', fontName='DVB', fontSize=11, leading=14, spaceBefore=10, spaceAfter=4, textColor=TINTA),
    'p': ParagraphStyle('p', fontName='DV', fontSize=9, leading=12.5, alignment=TA_JUSTIFY, spaceAfter=5,
                        textColor=TINTA),
    'li': ParagraphStyle('li', fontName='DV', fontSize=9, leading=12.5, leftIndent=12, bulletIndent=2,
                         spaceAfter=3, textColor=TINTA),
    'cap': ParagraphStyle('cap', fontName='DVI', fontSize=8, leading=10, textColor=TINTA2, spaceAfter=8),
    'td': ParagraphStyle('td', fontName='DV', fontSize=7.6, leading=9.4, textColor=TINTA),
    'th': ParagraphStyle('th', fontName='DVB', fontSize=7.6, leading=9.4, textColor=TINTA),
    'titulo': ParagraphStyle('t', fontName='DVB', fontSize=20, leading=25, textColor=TINTA, spaceAfter=6),
    'sub': ParagraphStyle('s', fontName='DV', fontSize=11, leading=15, textColor=TINTA2, spaceAfter=4),
}


NOMBRES = [  # (prefijo en el SKP, nombre legible, letras del diagrama de corte)
    ('ESPCL-LD-02', 'Lateral exterior', 'C, D'),
    ('lateral aire', 'Lateral aire', 'H, I'),
    ('fondo 15mm', 'Trasero 15 mm', 'A, B'),
    ('ESPCL-PI-02', 'Piso de torre', 'Q, R'),
    ('ESPCL-T-01', 'Travesaño superior de torre', 'AC, AD'),
    ('REPIZA@1#8', 'Panel inferior interior', 'AI, AJ'),
    ('REPIZA@1#9', 'Cubierta de cajones', 'W, X'),
    ('REPIZA@1#7', 'Travesaño bajo cubierta', 'AA, AB'),
    ('PTRSOP024-TO', 'Entrepaño (tope)', 'Y, Z'),
    ('PTRSOP022', 'Amarre trasero bajo entrepaño', 'AF, AH'),
    ('PTRSOP0-125', 'Amarre frontal bajo entrepaño', 'AE, AG'),
    ('ZOCALO-ALANTE-02', 'Zócalo frontal', 'S, T'),
    ('ZOCALO-ATRAS-01', 'Zócalo trasero', 'U, V'),
    ('ZOCALO-DE-03', 'Zócalo lateral', 'AU, AV'),
    ('ZOCALO-IZ-04', 'Zócalo lateral', 'AW, AX'),
    ('MALEST-MA', 'Piso de maletero', 'E'),
    ('MALEST-MR', 'Techo de maletero', 'F'),
    ('MALEST-MI', 'Costado de maletero', 'M'),
    ('MALEST-MD', 'Costado de maletero', 'L'),
    ('MALEST-RI', 'Tira trasera de maletero', 'P'),
    ('MALEST-RD', 'Tira trasera de maletero', 'O'),
    ('REPIZA@1#1', 'Travesaño frontal de maletero', 'G'),
    ('relleno bajo lateral aire', 'Relleno propuesto', 'nuevo'),
]


def legible(txt):
    import re
    for cod, nom, _ in NOMBRES:
        txt = re.sub(re.escape(cod) + r'(#\d+)?', nom, txt)
    return txt.replace(' (torre izq)', '').replace(' (torre der)', '')


def p(txt, est='p'):
    return Paragraph(txt, E[est])


def lista(items):
    return [Paragraph(t, E['li'], bulletText='•') for t in items]


def tabla(filas, anchos, estado=None, enc=1):
    datos = [[Paragraph(str(c), E['th'] if i < enc else E['td']) for c in f] for i, f in enumerate(filas)]
    t = Table(datos, colWidths=[a * cm for a in anchos], repeatRows=enc)
    st = [('LINEBELOW', (0, 0), (-1, enc - 1), 0.8, TINTA2), ('LINEBELOW', (0, enc), (-1, -1), 0.3, REGLA),
          ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('BACKGROUND', (0, 0), (-1, enc - 1), FONDO),
          ('TOPPADDING', (0, 0), (-1, -1), 2.5), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5)]
    if estado:
        for i, s in enumerate(estado):
            if s:
                st.append(('BACKGROUND', (-1, i + enc), (-1, i + enc), {'ok': OK, 'mal': MAL, 'atn': ATN}[s]))
    t.setStyle(TableStyle(st))
    return t


def fig(nombre, ancho_cm, pie):
    ruta = os.path.join(FIG, nombre)
    if not os.path.exists(ruta):
        return [p(f'(figura {nombre} no disponible)', 'cap')]
    from PIL import Image as PI
    w, h = PI.open(ruta).size
    img = Image(ruta, width=ancho_cm * cm, height=ancho_cm * cm * h / w)
    return [KeepTogether([img, p(pie, 'cap')])]


def estado(u, lim=1.0, atn=0.85):
    return 'mal' if u > lim else ('atn' if u > atn else 'ok')


def f1(x, d=2):
    return f'{x:.{d}f}'


def pie_pagina(canvas, doc):
    canvas.saveState()
    canvas.setFont('DV', 7)
    canvas.setFillColor(TINTA2)
    canvas.drawString(2 * cm, 1.2 * cm, 'Memoria de cálculo estructural. Closet con maleteros sobre PTR 3"x3"')
    canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f'Página {doc.page}')
    canvas.restoreState()


VARIANTES = (('base', 'Proyecto'), ('relleno', 'Con relleno'), ('relleno y entrepano', 'Relleno + entrepaño fijo'))


def lambdas_cr(V):
    from figuras import southwell
    out = {}
    for d in V.get('pandeo') or []:
        n = d['variante']
        var = 'base' if n.startswith('proyecto') else ('relleno y entrepano' if 'entrepa' in n else 'relleno')
        out[(var, 'ELU' in n)] = southwell(d['curva'])
    return out


def _caso_pandeo(V, var, corto):
    for d in V.get('pandeo') or []:
        n = d['variante']
        v = 'base' if n.startswith('proyecto') else ('relleno y entrepano' if 'entrepa' in n else 'relleno')
        if v == var and ('ELU' in n) == corto:
            return d
    return None


def rango_lambda(V, var, corto, dlam=0.5):
    """Texto del factor de carga limite y su cota inferior."""
    d = _caso_pandeo(V, var, corto)
    if d is None:
        return 'n/d', None
    lu = d['lambda_ultimo']
    if d['convergio_hasta_max'] or d.get('nota'):
        return f'> {lu:.1f}', lu
    return f'{lu:.1f} a {lu + dlam:.1f}', lu


def abombamiento(V, var, corto, lam_obj=1.0):
    for d in V.get('pandeo') or []:
        n = d['variante']
        v = 'base' if n.startswith('proyecto') else ('relleno y entrepano' if 'entrepa' in n else 'relleno')
        if v == var and ('ELU' in n) == corto and d['curva']:
            c = min(d['curva'], key=lambda k: abs(k['lam'] - lam_obj))
            if abs(c['lam'] - lam_obj) < 0.01:
                return c['abombamiento_lateral']
    return None


def tabla_resumen(V):
    vs = [v for v, _ in VARIANTES if v in V['ptr']]
    filas = [['Verificación'] + [e for v, e in VARIANTES if v in vs] + ['Criterio']]
    colores = []

    def fila(nombre, textos, crit, us, lim=1.0, atn=0.85):
        filas.append([nombre] + textos + [crit])
        colores.append([estado(u, lim=lim, atn=atn) if u is not None else None for u in us])

    pf = {v: V['ptr'][v]['filas'][0] for v in vs}
    fila('PTR: flexión M<sub>u</sub>/φM<sub>n</sub>', [f1(pf[v]['u_M']) for v in vs], '≤ 1.0', [pf[v]['u_M'] for v in vs])
    uvr = {v: max(pf[v]['u_V'], pf[v]['u_R']) for v in vs}
    fila('PTR: cortante y aplastamiento de paredes', [f1(uvr[v]) for v in vs], '≤ 1.0', [uvr[v] for v in vs])
    fp = {v: V['flechas_ptr'][v]['frente'] for v in vs}
    fila('PTR frontal: flecha a largo plazo', [f'L/{fp[v]["L_sobre_fin"]:.0f}' for v in vs], '≤ L/300',
         [fp[v]['fin'] / fp[v]['lim'] for v in vs])
    ap = {v: max(f['u'] for f in V['apoyo_tableros'][v]) for v in vs}
    fila('Apoyo del PTR en canto de tablero σ/f<sub>c,d</sub>', [f1(ap[v]) for v in vs], '≤ 1.0', [ap[v] for v in vs])
    tb = {v: V['tableros'][f'{v}|ELU-T1 1.35G+1.5Q']['filas'][0]['u'] for v in vs}
    fila('Tableros: índice de esfuerzo máximo', [f1(tb[v]) for v in vs], '≤ 1.0', [tb[v] for v in vs])
    un = {v: max(f['u'] for f in V['uniones'][v]['filas']) for v in vs}
    fila('Uniones: demanda / confirmat típicos', [f1(un[v]) for v in vs], '≤ 1.0', [un[v] for v in vs])
    if V.get('pandeo'):
        for corto, nom in ((True, 'Estabilidad, corto plazo: factor de carga límite λ'),
                           (False, 'Estabilidad, largo plazo: factor de carga límite λ')):
            r = [rango_lambda(V, v, corto) for v in vs]
            fila(nom, [t for t, _ in r], '≥ 3', [3.0 / x if x else None for _, x in r], lim=2.0, atn=1.0)
        vals = [abombamiento(V, v, False) for v in vs]
        fila('Abombamiento de laterales con carga sostenida', [f'{x:.1f} mm' if x else '-' for x in vals],
             '≤ 870/300 = 2.9 mm', [x / 2.9 if x else None for x in vals])
    d = V['desplome']
    fila('Desplome superior de maleteros, G + Q, sin anclaje', [f'{d[v]["uy_max"]:.1f} mm' for v in vs],
         'se recomienda < 5 mm', [d[v]['uy_max'] / 5 for v in vs])
    rp = {v: max(f['u'] for f in V['flechas_repisas'][v]) for v in vs}
    fila('Repisas: flecha diferida máxima / (L/200)', [f1(rp[v]) for v in vs], '≤ 1.0', [rp[v] for v in vs])
    fila('Volteo sin anclaje: aceleración que lo inicia', [f'{V["volteo"]["c_limite"]:.2f} g'] * len(vs),
         'anclar al muro', [2.0] * len(vs))
    t = tabla(filas, [6.4] + [2.6] * len(vs) + [3.3])
    st = []
    paleta = {'ok': OK, 'mal': MAL, 'atn': ATN}
    for i, fila_c in enumerate(colores):
        for j, c in enumerate(fila_c):
            if c:
                st.append(('BACKGROUND', (1 + j, 1 + i), (1 + j, 1 + i), paleta[c]))
    t.setStyle(TableStyle(st))
    return t


def main():
    V = json.load(open(os.path.join(RES, 'verificaciones.json'), encoding='utf-8'))
    res = pickle.load(open(os.path.join(RES, 'resultados.pkl'), 'rb'))
    T, C = P.TABLERO, P.CARGAS
    hoy = datetime.date.today().strftime('%d/%m/%Y')
    pb = V['ptr']['base']
    cap = pb['capacidad']
    fa1 = pb['filas'][0]
    pr = V['ptr']['relleno']['filas'][0]
    fl = V['flechas_ptr']
    vol = V['volteo']
    des = V['desplome']
    rep_b = V['reparto_apoyos']['base']
    G_kN = V['peso']['G'] / 1e3
    GQ_kN = V['peso']['G_Q'] / 1e3
    pandeo = V.get('pandeo')
    u_apoyo_ext = max(f['u'] for f in V['apoyo_tableros']['base'] if 'frente' in f['apoyo'] and 'exterior' in f['apoyo'])
    s_rec = int(min(f['s_local'] for f in V['uniones']['base']['filas'] if f['u'] > 0.7) // 10 * 10)

    H = []
    # ------------------------------------------------------------------ portada
    H += [Spacer(1, 1.5 * cm), p('Memoria de cálculo estructural', 'titulo'),
          p('Closet con tres maleteros apoyados en dos PTR 3"x3" sobre dos torres de melamina', 'sub'),
          p(f'Archivo de proyecto: <i>closet pedido mx.skp</i> (SketchUp 2023) y diagrama de corte del 15/08/2025.'
            f' Fecha del cálculo: {hoy}.', 'p'), Spacer(1, 0.4 * cm)]
    H += [p('Resumen ejecutivo', 'h2')]
    tiene_ent = 'relleno y entrepano' in V['ptr']

    def abomb(var, corto):
        x = abombamiento(V, var, corto)
        return x if x is not None else float('nan')

    items = [
        f'El PTR 3"x3" cal. 14 resiste con holgura: momento último {f1(fa1["Mu"] / 1e6)} kN·m contra '
        f'φM<sub>n</sub> = {f1(cap["phiMn"] / 1e6)} kN·m ({fa1["u_M"]:.0%}), cortante y aplastamiento local '
        f'por debajo de 10 %. La flecha del PTR frontal es {f1(fl["base"]["frente"]["inst"], 1)} mm instantánea '
        f'y {f1(fl["base"]["frente"]["fin"], 1)} mm a largo plazo (L/{fl["base"]["frente"]["L_sobre_fin"]:.0f}), '
        f'dentro de L/300. Un calibre mayor no es necesario.',
        'El punto débil no es el acero sino cómo llega la carga al piso. El lateral interior de cada torre '
        '("lateral aire", 900 mm) no baja hasta el piso: entre la cubierta de cajones y su canto inferior hay un '
        'hueco abierto de 205 mm. Cuelga de tornillos al tablero trasero, así que casi no toma carga del PTR. '
        f'En el PTR frontal, cada lateral exterior recibe {rep_b["frente|torre izq"].get("lateral exterior", 0) / 1e3:.2f} kN '
        f'en servicio y el lateral aire solo {rep_b["frente|torre izq"].get("lateral aire", 0) / 1e3:.2f} kN: el PTR '
        'trabaja con un claro efectivo de 2.87 m entre laterales exteriores, no de 1.66 m, y su reacción se concentra '
        'en la esquina superior frontal del lateral exterior.',
        '<b>La estabilidad de los laterales gobierna.</b> El canto frontal de los laterales queda prácticamente libre en '
        'el compartimento superior: 870 mm entre el entrepaño (685 mm) y el travesaño superior (1570 mm), la puerta no lo '
        'arriostra y el entrepaño, unido con tornillos, lo restringe solo en parte. El análisis no '
        f'lineal del proyecto deja de converger para λ entre {rango_lambda(V, "base", True)[0]} a corto plazo y entre '
        f'{rango_lambda(V, "base", False)[0]} bajo carga sostenida con fluencia, con {abomb("base", False):.0f} mm de '
        'abombamiento del lateral exterior a la carga sostenida de diseño (λ = 1). Es una deformación visible y un '
        'margen insuficiente.',
        'Otras consecuencias medibles: las uniones del trasero con el lateral aire y con la cubierta quedan al límite '
        'con separaciones típicas de confirmat, el trasero concentra esfuerzos junto al canto inferior del lateral aire y '
        f'los maleteros se inclinan hacia el frente {f1(des["base"]["uy_max"], 1)} mm en su parte alta (sin anclaje al muro).',
        f'Un relleno de 15 mm (585 x 205 mm) bajo cada lateral aire baja el momento del PTR a {f1(pr["Mu"] / 1e6)} kN·m, '
        f'la flecha a {f1(fl["relleno"]["frente"]["inst"], 1)} mm y el desplome a {f1(des["relleno"]["uy_max"], 1)} mm, '
        f'y reparte la carga entre los dos laterales, pero la estabilidad mejora poco: λ límite entre '
        f'{rango_lambda(V, "relleno", True)[0]} a corto plazo y entre {rango_lambda(V, "relleno", False)[0]} a largo plazo.',
    ]
    if tiene_ent:
        items.append(
            '<b>Solución recomendada: relleno más un entrepaño fijo intermedio a 1120 mm en cada torre</b>, confirmado a '
            'ambos laterales y al trasero. Divide a la mitad el tramo libre del canto frontal: el análisis no lineal '
            f'llega a λ {rango_lambda(V, "relleno y entrepano", True)[0]} a corto plazo y {rango_lambda(V, "relleno y entrepano", False)[0]} '
            f'a largo plazo sin perder estabilidad, con {abomb("relleno y entrepano", False):.1f} mm de abombamiento a la '
            'carga sostenida. Cumple todas las verificaciones de resistencia y estabilidad.')
    items += [
        f'Sin anclaje, el mueble se voltea con una aceleración horizontal de {vol["c_limite"]:.2f} g. Hay que fijarlo al '
        f'muro: {vol["anclas"][-1]["F"] / 1e3:.2f} kN por torre y hasta '
        f'{max(a["F"] for a in vol["anclas"] if a["xyz"][2] > 2000) / 1e3:.2f} kN por taquete de maletero con el coeficiente adoptado.',
        'Las repisas de 15 mm (piso de maletero y entrepaños de torre) cumplen resistencia pero, con carga de '
        'almacenamiento sostenida, su flecha diferida supera L/200. Es un tema de servicio y apariencia.',
    ]
    H += lista(items)
    H += [PageBreak(), p('Resumen de verificaciones', 'h2')]
    H += [tabla_resumen(V), p('Verde: cumple con holgura. Amarillo: cumple al límite o requiere atención. '
                              'Rojo: no cumple el criterio indicado.', 'cap')]
    H += [PageBreak()]

    # ------------------------------------------------------------------ 1. alcance
    H += [p('1. Objeto y alcance', 'h1'),
          p('Se verifica la estructura del closet con la modificación indicada por el cliente: dos PTR 3"x3" '
            'colocados bajo los maleteros, a todo lo largo, apoyados sobre las dos torres (módulos verticales). '
            'Se revisan el PTR, los tableros de melamina, las uniones atornilladas, el apoyo del PTR sobre los '
            'cantos de los tableros, la estabilidad de los laterales, las deformaciones y el volteo. El cálculo se '
            'hace con un modelo tridimensional de elementos finitos construido a partir de la geometría real del '
            'archivo SketchUp, complementado con verificaciones analíticas.'),
          p('2. Descripción del mueble', 'h1'),
          p('La geometría se extrajo directamente del archivo .skp (formato SketchUp 2023, árbol binario de '
            'componentes) con un lector propio. Las 89 piezas de melamina de 15 mm extraídas coinciden una a una con '
            'el diagrama de corte (22.41 m² de tablero, 6 hojas de 2440 x 1830 mm). Medidas principales:')]
    H += [tabla([
        ['Elemento', 'Medidas (mm)', 'Composición'],
        ['Conjunto', '2880 de frente x 600 de fondo; altura 2440 en el proyecto, 2516 con los PTR bajo maleteros',
         'Dos torres en los extremos, hueco central de 1640 mm, tres maleteros arriba'],
        ['Torre (x2)', '620 x 600 x 1570 (zócalo 100 + casco 1470)',
         'Lateral exterior 1455, trasero 15 mm de 605 x 1455, piso, 2 cajones, cubierta 605 x 585 a 450, '
         'entrepaño con amarres a 685, travesaños superiores 590 x 100, puerta 618 x 897'],
        ['Lado interior de torre', 'Panel inferior 585 x 335 (z 115 a 450); lateral aire 585 x 900 (z 670 a 1570)',
         'Hueco abierto de 205 mm entre z 465 y 670: el lateral aire no tiene apoyo directo hacia el piso'],
        ['Maletero (x3)', '960 x 870 x 600', 'Costados de altura completa, piso y techo entre costados, dos tiras '
         'traseras de 200 mm, travesaño frontal 930 x 100, dos puertas 478 x 855'],
        ['PTR (x2)', '76.2 x 76.2, L = 2880', 'Uno a paño frontal y otro a paño trasero, bajo los costados y el piso '
         'de los maleteros, apoyados en la parte superior de las torres'],
    ], [3.0, 6.0, 8.5])]
    H += [Spacer(1, 0.3 * cm), p('Nombres usados en este documento y su correspondencia con el diagrama de corte '
                                 '(letras de pieza y nombre de componente en SketchUp):')]
    filas = [['Nombre en la memoria', 'Letras en el diagrama de corte', 'Componente SketchUp']]
    vistos = set()
    for cod, nom, letras in NOMBRES:
        if (nom, letras) in vistos:
            continue
        vistos.add((nom, letras))
        filas.append([nom, letras, cod])
    H += [tabla(filas, [6.0, 4.5, 7.0])]
    H += [Spacer(1, 0.2 * cm)]
    H += fig('fig03_esquema_alzado.png', 16.5,
             'Figura 1. Alzado frontal esquemático. En naranja rayado, el hueco de 205 mm bajo cada lateral aire.')
    H += fig('fig01_modelo_3d.png', 14.5, 'Figura 2. Modelo de elementos finitos (tableros en su plano medio; PTR en naranja).')

    # ------------------------------------------------------------------ 3. materiales
    H += [p('3. Materiales y propiedades adoptadas', 'h1'),
          p('La melamina comercial es tablero de partículas de uso interior (tipo EN 312 P2), que no es un grado '
            'estructural. Se adoptaron valores reducidos a partir de EN 12369-1 (P4, 13 a 20 mm) escalados al mínimo '
            'de P2 y los factores de duración de carga y fluencia de EN 1995-1-1 para tablero de partículas en '
            'clase de servicio 1.')]
    H += [tabla([
        ['Propiedad', 'Valor', 'Fuente o criterio'],
        ['Tablero: espesor, densidad', f'{T["espesor"]:.0f} mm, {T["densidad"]:.0f} kg/m³', 'Diagrama de corte; densidad típica de MDP'],
        ['Módulo de elasticidad medio E, ν', f'{T["E"]:.0f} MPa, {T["nu"]}', 'Mínimo P2 (1600) llevado a valor medio'],
        ['f<sub>m,k</sub> / f<sub>t,k</sub> / f<sub>c,k</sub> / f<sub>v,k</sub>',
         f'{T["fm_k"]} / {T["ft_k"]} / {T["fc_k"]} / {T["fv_k"]} MPa', 'EN 12369-1 P4 escalado a P2'],
        ['k<sub>mod</sub> permanente / largo plazo / corto', f'{T["kmod_permanente"]} / {T["kmod_largo"]} / {T["kmod_corto"]}',
         'EN 1995-1-1 tabla 3.1'],
        ['k<sub>def</sub>, γ<sub>M</sub>', f'{T["kdef"]}, {T["gamma_M"]}', 'EN 1995-1-1 tablas 3.2 y 2.3'],
        ['Acero PTR: E, F<sub>y</sub>', f'{P.ACERO["E"]:.0f} MPa, {P.ACERO["Fy"]:.0f} MPa',
         'F<sub>y</sub> conservador; un ASTM A500 Gr. B tiene 317 MPa'],
        ['PTR 3"x3" cal. 14', f'{cap["t"]:.3f} mm; A = {cap["A"] / 100:.2f} cm²; I = {cap["I"] / 1e4:.1f} cm⁴; '
         f'Z = {cap["Z"] / 1e3:.2f} cm³; {cap["masa"]:.2f} kg/m', 'Integración numérica, radio exterior 2t'],
        ['Confirmat 7 x 50 en melamina 15 mm', f'F<sub>v,k</sub> = {P.CONFIRMAT["Fv_k"] / 1e3:.1f} kN; '
         f'F<sub>ax,k</sub> = {P.CONFIRMAT["Fax_k"] / 1e3:.1f} kN', 'Valores adoptados, verificar con el fabricante'],
    ], [5.5, 5.8, 6.2])]

    # ------------------------------------------------------------------ 4. cargas
    H += [p('4. Cargas y combinaciones', 'h1')]
    H += [tabla([
        ['Caso', 'Descripción', 'Valor'],
        ['G', 'Peso propio de tableros (+5 % por cubrecanto y herrajes), puertas, cajones, correderas y PTR',
         f'{G_kN:.2f} kN en total ({G_kN * 1000 / 9.81:.0f} kg)'],
        ['Q maleteros', 'Contenido sobre el piso de cada maletero', f'{C["q_maletero"] * 1e3:.1f} kN/m² (150 kg/m²)'],
        ['Q torres', 'Cubierta de cajones y entrepaño; contenido de cajones',
         f'{C["q_repisa_torre"] * 1e3:.1f} kN/m²; {C["q_cajon_kg"]:.0f} kg por cajón'],
        ['Q barra', 'Barra de colgar supuesta en el hueco central, fijada a los laterales aire a 1450 mm',
         f'{C["q_barra"]:.2f} kN/m sobre 1.64 m'],
        ['H', 'Fuerza horizontal hacia el frente para dimensionar anclajes', f'{C["c_sismico"]} (G + ψ<sub>2</sub>Q)'],
    ], [2.4, 10.0, 5.1])]
    H += [Spacer(1, 0.2 * cm), p(
        f'Carga total en servicio G + Q = {GQ_kN:.2f} kN. Combinaciones: para el acero, AISC 360-16 con ASCE 7 '
        '(1.2G + 1.6Q y 1.4G). Para tableros y uniones, EN 1990 (1.35G + 1.5Q con k<sub>mod</sub> de largo plazo y '
        '1.35G con k<sub>mod</sub> permanente). Servicio: G + Q instantánea y G + ψ<sub>2</sub>Q con '
        f'ψ<sub>2</sub> = {T["psi2_almacen"]} (almacenamiento) para la deformación diferida, calculada con '
        'E/(1 + k<sub>def</sub>) en tableros y uniones. Anclaje: G + ψ<sub>2</sub>Q + H.')]

    # ------------------------------------------------------------------ 5. modelo
    mal = res['base']['malla']
    H += [p('5. Modelo de elementos finitos', 'h1'),
          p('El modelo se construyó en OpenSeesPy. Las decisiones de idealización son las siguientes:')]
    H += lista([
        f'Cada tablero es un cascarón ShellMITC4 en su plano medio ({mal["cascarones"]} elementos de hasta 75 mm). '
        'Los cantos que llegan a otro tablero se llevan al plano medio de éste.',
        'Cada tablero tiene nodos propios. Las uniones son resortes en traslación sin momento (bisagra lineal): '
        f'{P.K_UNION:.0f} N/mm por mm de unión en corte y tracción (tornillería), y {P.K_APOYO:.0f} N/mm por mm '
        f'en compresión cuando un canto apoya directamente en una cara. Son {mal["uniones"]} resortes de canto y '
        f'{mal["uniones_cara"]} de cara (entrepaños sobre amarres y travesaños, y 4 tornillos entre maleteros contiguos).',
        'Los PTR son vigas elásticas 3D en su eje. El contacto con torres y maleteros es solo a compresión '
        '(el mueble descansa sobre el PTR) con resortes horizontales que representan la fijación. '
        'Se resuelve por Newton para cada combinación.',
        'Base del zócalo articulada en el piso. Puertas y cajones se aplican como cargas en el tablero que los '
        'soporta (bisagras del lado del lateral aire en las torres).',
        'Controles: el peso del modelo coincide con el del despiece; las reacciones igualan la carga aplicada; '
        'los resultados son simétricos entre torres; no quedan contactos en tracción.',
    ])
    H += [p('Variantes analizadas: proyecto; relleno de 15 mm bajo cada lateral aire; relleno más un entrepaño fijo '
            'intermedio a 1120 mm en cada torre (arriostra el canto frontal de los laterales); cada una a corto y largo '
            'plazo; además uniones diez veces más rígidas (sensibilidad), PTR cal. 11 y caso horizontal con anclajes al muro.')]

    # ------------------------------------------------------------------ 6. resultados
    H += [PageBreak(), p('6. Resultados', 'h1'), p('6.1 Cómo llega la carga del PTR a las torres', 'h2'),
          p('La figura 3 compara qué elemento de la torre recibe la reacción de cada PTR. En el proyecto, el PTR '
            'frontal descarga casi todo en el lateral exterior. El lateral aire, que no llega al piso, solo puede '
            'transmitir carga por cortante en los tornillos que lo unen al trasero, que son mucho más flexibles que '
            'el apoyo directo del lateral exterior; por rigidez, la carga se va al lateral exterior. El PTR trasero se '
            'apoya sobre todo en el canto del tablero trasero de 15 mm, que trabaja como muro.')]
    H += fig('fig05_reparto_apoyos.png', 16.5, 'Figura 3. Reacción de cada PTR sobre los elementos de la torre izquierda (la derecha es simétrica), combinación G + Q.')
    vs = [v for v, _ in VARIANTES if v in V['reparto_apoyos']]
    filas = [['PTR / elemento de la torre'] + [f'{e} (kN)' for v, e in VARIANTES if v in vs]]
    for ptr in ('frente', 'fondo'):
        for el in ('lateral exterior', 'lateral aire', 'trasero 15 mm'):
            vals = [V['reparto_apoyos'][v][f'{ptr}|torre izq'].get(el, 0.0) / 1e3 for v in vs]
            if any(vals):
                filas.append([f'PTR {ptr}: {el}'] + [f1(x) for x in vals])
    H += [tabla(filas, [6.5] + [3.6] * len(vs))]

    H += [p('6.2 PTR 3"x3"', 'h2'),
          p(f'Sección cal. 14: b/t = {cap["b_t"]:.1f}, patín no compacto en flexión (λ<sub>p</sub> = '
            f'{cap["lp_f"]:.1f}, λ<sub>r</sub> = {cap["lr_f"]:.1f}); alma compacta. Resistencias de diseño AISC 360-16: '
            f'φM<sub>n</sub> = {f1(cap["phiMn"] / 1e6)} kN·m (F7), φV<sub>n</sub> = {cap["phiVn"] / 1e3:.1f} kN (G4), '
            f'fluencia y aplastamiento local de paredes en el extremo φR<sub>n</sub> = {cap["phiRn_ext"] / 1e3:.1f} kN (J10).')]
    mn = V['manual']
    H += [p('Comprobación manual: tomando toda la carga que los maleteros apoyan en el PTR frontal '
            f'({mn["ELU-A1 1.2G+1.6Q"]["W"] / 1e3:.2f} kN en 1.2G + 1.6Q; {mn["ELS G+Q"]["W"] / 1e3:.2f} kN en G + Q) como '
            'repartida sobre una viga simple de 2865 mm, M<sub>u</sub> = WL/8 = '
            f'{mn["ELU-A1 1.2G+1.6Q"]["M_manual"] / 1e6:.2f} kN·m y la flecha de servicio 5WL³/384EI = '
            f'{mn["ELS G+Q"]["flecha_manual"]:.1f} mm, contra {mn["ELU-A1 1.2G+1.6Q"]["M_fe"] / 1e6:.2f} kN·m y '
            f'{mn["ELS G+Q"]["flecha_fe"]:.1f} mm del modelo. El modelo da algo menos porque las cargas de los costados '
            'extremos caen sobre los apoyos y los maleteros aportan rigidez; el orden de magnitud confirma el resultado.')]
    H += fig('fig04_ptr_diagramas.png', 16.5, 'Figura 4. Momento y cortante últimos (1.2G + 1.6Q) y desplazamiento en servicio (G + Q) a lo largo de cada PTR.')
    filas = [['Variante', 'Combinación', 'M<sub>u</sub> (kN·m)', 'M<sub>u</sub>/φM<sub>n</sub>', 'V<sub>u</sub> (kN)',
              'V<sub>u</sub>/φV<sub>n</sub>', 'R<sub>u</sub> extremo (kN)', 'R<sub>u</sub>/φR<sub>n</sub>']]
    est = []
    for var, etq in (('base', 'Proyecto cal. 14'), ('relleno', 'Con relleno cal. 14'),
                     ('relleno y entrepano', 'Relleno + entrepaño cal. 14'), ('PTR cal. 11', 'Proyecto cal. 11'),
                     ('uniones rigidas', 'Uniones rígidas cal. 14')):
        if var not in V['ptr']:
            continue
        for f in V['ptr'][var]['filas']:
            filas.append([etq, f['combo'].split(' ', 1)[1], f1(f['Mu'] / 1e6, 3), f1(f['u_M']), f1(f['Vu'] / 1e3),
                          f1(f['u_V']), f1(f['Ru_ext'] / 1e3), f1(f['u_R'])])
            est.append(estado(max(f['u_M'], f['u_V'], f['u_R'])))
    H += [tabla(filas, [3.6, 2.4, 1.9, 1.9, 1.6, 1.8, 2.3, 2.0], est)]

    H += [p('6.3 Deformaciones', 'h2')]
    filas = [['Elemento', 'Variante', 'Instantánea G+Q (mm)', 'Largo plazo (mm)', 'Límite (mm)', 'Relación']]
    est = []
    for var, etq in VARIANTES:
        if var not in fl:
            continue
        for ptr in ('frente', 'fondo'):
            d = fl[var][ptr]
            filas.append([f'PTR {ptr} (L = 2865 mm)', etq, f1(d['inst']), f1(d['fin']), f'{d["lim"]:.1f} (L/300)',
                          f'L/{d["L_sobre_fin"]:.0f}'])
            est.append(estado(d['fin'] / d['lim']))
    for var, etq in VARIANTES:
        if var not in V['flechas_repisas']:
            continue
        for d in V['flechas_repisas'][var]:
            nom = legible(d['tablero'])
            filas.append([f'{nom} (L = {d["L"]:.0f})', etq, f1(d['inst']), f1(d['fin']), f'{d["lim"]:.1f} (L/200)',
                          f'L/{d["L"] / d["fin"]:.0f}'])
            est.append(estado(d['u'], atn=0.85))
    H += [tabla(filas, [5.2, 2.4, 2.8, 2.5, 2.6, 2.0], est)]
    H += [p(f'Desplome hacia el frente en la parte alta de los maleteros (G + Q, sin anclaje al muro): '
            f'{f1(des["base"]["uy_max"], 1)} mm en el proyecto y {f1(des["relleno"]["uy_max"], 1)} mm con relleno. '
            'Proviene de que el PTR frontal baja más que el trasero y gira los maleteros; el anclaje superior al muro '
            'lo restringe. Las repisas cumplen resistencia, pero su flecha diferida con 1.2 kN/m² sostenidos excede '
            'L/200; con cargas reales menores o con un refuerzo frontal (canto de 18 mm, perfil de aluminio) el '
            'problema desaparece. No compromete la estabilidad.')]
    H += fig('fig02_deformada.png', 13.0, 'Figura 5. Deformada del proyecto en servicio, amplificada 40 veces.')
    H += fig('fig02b_deformada_relleno.png', 13.0, 'Figura 6. Deformada con relleno bajo el lateral aire, misma escala de amplificación.')

    H += [p('6.4 Esfuerzos en tableros', 'h2'),
          p('Índice de esfuerzo = esfuerzo de membrana / resistencia + esfuerzo de flexión / f<sub>m,d</sub>, por '
            'dirección y en cortante. Se informa el valor promediado en un radio de 75 mm (representativo) y el pico '
            'puntual, que aparece en esquinas de líneas de unión donde el modelo concentra fuerzas en un nodo.')]
    filas = [['Tablero', 'Variante y combinación', 'Pico puntual', 'Índice promediado']]
    est = []
    for clave in ('base|ELU-T1 1.35G+1.5Q', 'base|ELU-T2 1.35G', 'relleno|ELU-T1 1.35G+1.5Q',
                  'relleno y entrepano|ELU-T1 1.35G+1.5Q'):
        if clave not in V['tableros']:
            continue
        var, comb = clave.split('|')
        for t in V['tableros'][clave]['filas'][:4]:
            filas.append([legible(t['tablero']),
                          f'{dict(VARIANTES)[var]}, {comb.split(" ", 1)[1]}',
                          f1(t['u_pico']), f1(t['u'])])
            est.append(estado(t['u']))
    H += [tabla(filas, [5.6, 5.4, 3.0, 3.0], est)]
    tb = V['tableros']['base|ELU-T1 1.35G+1.5Q']['filas'][0]
    H += [p(f'El máximo del proyecto está en el tablero trasero de la torre junto al canto inferior del lateral aire '
            f'(índice {f1(tb["u"])} promediado, {f1(tb["u_pico"])} puntual): ahí entra en el trasero la carga que '
            'cuelga del lateral aire. Con el relleno esa concentración desaparece.')]

    H += [p('6.5 Uniones atornilladas', 'h2'),
          p(f'Capacidad de diseño por confirmat (k<sub>mod</sub> = {T["kmod_largo"]}): corte '
            f'{V["uniones"]["base"]["conector"]["Fv_d"]:.0f} N, extracción {V["uniones"]["base"]["conector"]["Fax_d"]:.0f} N. '
            'La demanda de cada unión es la suma de tracciones (extracción) y cortantes del modelo; la compresión de '
            'canto contra cara no demanda al conector. Se calcula el número necesario con interacción cuadrática y un '
            'factor de reparto desigual de 1.25, y se compara con la cantidad típica (uno a 50 mm de cada extremo y '
            'separación de 200 mm).')]
    filas = [['Unión (pieza de canto contra pieza de cara)', 'L (mm)', 'Tracción (N)', 'Cortante (N)', 'Conectores necesarios',
              'Conectores típicos', 'Separación local máx. (mm)']]
    est = []
    for var, etq in VARIANTES:
        if var not in V['uniones']:
            continue
        for f in V['uniones'][var]['filas'][:4]:
            nom = legible(f['union'])
            filas.append([f'{etq}: {nom}', f'{f["L"]:.0f}', f'{f["T"]:.0f}', f'{f["V"]:.0f}', f'{f["n_req"]}',
                          f'{f["n_tip"]}', f'{min(f["s_local"], 999):.0f}'])
            est.append(estado(f['u'], atn=0.85))
    H += [tabla(filas, [6.2, 1.2, 1.6, 1.6, 2.1, 2.0, 2.4], est)]

    H += [p('6.6 Apoyo del PTR sobre cantos de tablero', 'h2'),
          p('El PTR descansa sobre el canto de 15 mm de los tableros. Se verifica la compresión de canto con el ancho '
            f'del PTR (76.2 mm), contra f<sub>c,d</sub> = {V["apoyo_tableros"]["base"][0]["fc_d"]:.2f} MPa.')]
    filas = [['Apoyo', 'Variante', 'R<sub>d</sub> (kN)', 'σ (MPa)', 'σ/f<sub>c,d</sub>']]
    est = []
    for var, etq in VARIANTES:
        if var not in V['apoyo_tableros']:
            continue
        for f in V['apoyo_tableros'][var]:
            if f['R'] < 50:
                continue
            filas.append([f['apoyo'].replace('torre izq', 'torre'), etq, f1(f['R'] / 1e3), f1(f['sigma']), f1(f['u'])])
            est.append(estado(f['u']))
    H += [tabla(filas, [7.0, 3.0, 2.3, 2.3, 2.4], est)]

    H += [p('6.7 Estabilidad de laterales', 'h2')]
    if pandeo:
        from figuras import southwell
        H += [p('Se repitió el análisis con no linealidad geométrica (cascarones ASDShellQ4 corrotacionales y PTR '
                'corrotacional). La combinación se incrementa por un factor λ con una pequeña perturbación lateral en '
                'el canto libre de cada lateral. Se mide el abombamiento de los laterales respecto al plano de sus '
                'esquinas; el factor crítico se estima con la recta de Southwell sobre esos puntos.')]
        filas = [['Caso', 'Abombamiento a λ = 1 (mm)', 'Pieza que gobierna', 'Factor de carga límite λ',
                  'λ<sub>cr</sub> de Southwell (referencia)']]
        est = []
        for d in pandeo:
            c1 = min(d['curva'], key=lambda k: abs(k['lam'] - 1.0)) if d['curva'] else None
            lc = southwell(d['curva'])
            lu = d['lambda_ultimo']
            if d['convergio_hasta_max'] or d.get('nota'):
                txt = f'> {lu:.1f}'
            else:
                txt = f'{lu:.1f} a {lu + 0.5:.1f}'
            filas.append([d['variante'].replace('gamma_M', 'γM'), f1(c1['abombamiento_lateral']) if c1 else '-',
                          legible(c1['pieza']) if c1 else '-', txt, f'{lc:.1f}' if lc else '-'])
            est.append('mal' if lu < 1.5 else ('atn' if lu < 3.0 else 'ok'))
        H += [tabla(filas, [4.6, 2.8, 3.4, 3.0, 3.7], est)]
        H += [p('El factor de carga límite es el intervalo entre el último paso convergido y el siguiente; en los casos '
                'marcados con ">" la corrida terminó sin pérdida de estabilidad. La recta de Southwell sobreestima '
                'cuando hay pocos puntos y se da solo como referencia. Criterio: con λ mayor que 3 los efectos de segundo orden son menores al 50 % y se '
                'consideran aceptables para un mueble; entre 1.5 y 3 la deformación se amplifica de forma notoria '
                'con el tiempo; por debajo de 1.5 hay riesgo de inestabilidad por fluencia.')]
        H += fig('fig06_pandeo.png', 16.0, 'Figura 7. Factor de carga contra abombamiento máximo de laterales.')
        H += fig('fig07_modo_pandeo.png', 9.5, 'Figura 8. Abombamiento del lateral exterior izquierdo en el último paso '
                 'convergido del proyecto a corto plazo: se concentra en el canto frontal libre entre el entrepaño y el '
                 'travesaño superior.')
    else:
        H += [p('(Análisis no lineal geométrico no disponible en esta corrida.)')]

    H += [p('6.8 Volteo y anclaje al muro', 'h2'),
          p(f'Centro de masa de G + ψ<sub>2</sub>Q a {vol["z_cm"]:.0f} mm de altura y {vol["y_cm"]:.0f} mm detrás del '
            f'frente del zócalo. Sin anclaje, la aceleración horizontal que inicia el volteo es {vol["c_limite"]:.2f} g. '
            f'Con H = {C["c_sismico"]}(G + ψ<sub>2</sub>Q) = {vol["H"] / 1e3:.2f} kN el factor de seguridad sin anclaje '
            f'sería {vol["FS"]:.2f}. Fuerzas en anclajes del modelo con taquetes en la parte alta trasera:')]
    filas = [['Ubicación del anclaje', 'Altura (mm)', 'Fuerza (kN)']]
    for a in sorted(vol['anclas'], key=lambda a: (a['xyz'][2], a['xyz'][0])):
        x = a['xyz'][0]
        lugar = ('lateral exterior torre izq.' if x < 5000 else 'lateral exterior torre der.') if a['xyz'][2] < 2000 \
            else f'tira trasera de maletero, x = {x - 4800:.0f} mm'
        filas.append([lugar, f'{a["xyz"][2]:.0f}', f1(a['F'] / 1e3)])
    H += [tabla(filas, [8.5, 3.0, 3.0])]

    # ------------------------------------------------------------------ 7. conclusiones
    H += [PageBreak(), p('7. Conclusiones y recomendaciones', 'h1')]
    H += lista([
        '<b>El PTR 3"x3" cal. 14 es suficiente</b> en resistencia y rigidez con las cargas adoptadas. Un calibre '
        'mayor no cambia el comportamiento del mueble: lo que controla es la trayectoria de carga en las torres y la '
        'estabilidad del canto frontal libre de los laterales.',
        '<b>Colocar un relleno de melamina de 15 mm (585 x 205 mm) bajo cada lateral aire</b>, entre la cubierta de '
        'cajones y el amarre inferior, confirmado a la cubierta, al trasero y a los amarres. Así el lateral aire '
        'apoya en compresión directa hasta el piso y el PTR queda apoyado en los dos laterales de cada torre. '
        'Alternativa equivalente: un lateral interior de una pieza de 585 x 1455 mm.',
        '<b>Agregar un entrepaño fijo intermedio</b> (590 x 585 x 15 mm, a unos 1120 mm del piso) en el compartimento '
        'superior de cada torre, confirmado a los dos laterales y al trasero con separación máxima de 150 mm. Arriostra '
        'el canto frontal de los laterales, que es el que controla la estabilidad. Si se prefiere no perder el espacio, '
        'la alternativa es un poste metálico (PTR 1" o ángulo de 1 1/2") en cada esquina frontal de la torre, desde el '
        'piso hasta el PTR, de modo que la reacción no pase por los tableros.',
        '<b>Fijar el PTR</b> a cada lateral (exterior y aire) y al trasero con tornillos o ángulos, y los maleteros '
        'al PTR desde el interior. El contacto es a compresión en gravedad, pero la fijación da la restricción '
        'horizontal supuesta en el modelo y la necesaria para el anclaje.',
        '<b>Repartir la reacción del PTR frontal</b> sobre el canto del lateral exterior con una placa o ángulo de '
        'acero (por ejemplo 2" x 2" x 1/8" de 600 mm) si se conserva el proyecto sin relleno: el apoyo en el canto '
        f'de 15 mm trabaja al {u_apoyo_ext:.0%} en promedio pero con concentración en la esquina frontal.',
        '<b>Anclar al muro</b>: dos taquetes en la parte alta trasera de cada torre y dos por maletero, con capacidad '
        'de diseño en tracción no menor que las fuerzas de la sección 6.8, y tornillos de unión entre maleteros contiguos.',
        f'<b>Separación de confirmat</b> no mayor a {s_rec} mm en las uniones del trasero con el lateral aire, la cubierta y '
        'el entrepaño si no se coloca el relleno; con relleno basta la separación típica de 200 mm.',
        '<b>Repisas</b>: con contenidos pesados permanentes conviene un refuerzo frontal en el piso de los maleteros '
        'y en los entrepaños de torre para limitar la flecha diferida.',
    ])
    H += [p('8. Supuestos que conviene confirmar', 'h1')]
    H += lista([
        'Posición de los PTR (a paño frontal y trasero, longitud completa de 2880 mm) y que los maleteros se elevan '
        '76.2 mm sobre las torres. Con eso la altura total pasa de 2440 a 2516 mm; el archivo incluye un elemento de '
        'referencia de 2480 mm de altura detrás del mueble, que podría ser el muro o el plafón del nicho.',
        'Calibre del PTR (se calculó cal. 14 como caso desfavorable) y grado del acero.',
        'Calidad del tablero y del conector: los valores de resistencia son adoptados para melamina de partículas '
        'de uso interior y deben confirmarse con el proveedor.',
        'Existencia de la barra de colgar en el hueco central (se incluyó del lado conservador).',
        'Coeficiente horizontal para anclaje (0.5); debe ajustarse al sitio con la normativa local aplicable.',
    ])
    H += [p('9. Reproducibilidad', 'h1'),
          p('Todo el cálculo está en el repositorio: <i>herramientas/skp_lector.py</i> extrae la geometría del .skp, '
            '<i>modelo/modelo_fe.py</i> arma el modelo, <i>modelo/ejecutar.py</i> corre variantes y combinaciones, '
            '<i>modelo/verificaciones.py</i> hace las revisiones, <i>modelo/pandeo.py</i> el análisis no lineal y '
            '<i>modelo/figuras.py</i> y <i>modelo/memoria.py</i> generan figuras y este documento. Resultados '
            'numéricos completos en <i>resultados/resultados.json</i> y <i>resultados/verificaciones.json</i>.')]

    doc = SimpleDocTemplate(SALIDA, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, title='Memoria de cálculo: closet con PTR 3x3',
                            author='Cálculo estructural con modelo FE')
    doc.build(H, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    print(SALIDA)


if __name__ == '__main__':
    main()
