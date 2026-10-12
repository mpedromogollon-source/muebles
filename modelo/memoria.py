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
    'h1': ParagraphStyle('h1', fontName='DVB', fontSize=14, leading=18, spaceBefore=14, spaceAfter=6, textColor=TINTA, keepWithNext=1),
    'h2': ParagraphStyle('h2', fontName='DVB', fontSize=11, leading=14, spaceBefore=10, spaceAfter=4, textColor=TINTA, keepWithNext=1),
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
    canvas.drawString(2 * cm, 1.2 * cm, f'Memoria de cálculo estructural. Closet con maleteros sobre {NOM_PTR}. Revisión 2')
    canvas.drawRightString(letter[0] - 2 * cm, 1.2 * cm, f'Página {doc.page}')
    canvas.restoreState()


REC = 'relleno y entrepano cal. 14 pijas'      # solucion recomendada con fijacion realista
VARIANTES = (('base', 'Proyecto'), ('relleno', 'Con relleno'), ('relleno y entrepano', 'Relleno + entrepaño'),
             (REC, 'Recomendada: relleno + entrepaño, cal. 14, pijas'))
ETQ = dict(VARIANTES)
ETQ.update({'relleno y entrepano cal. 18': 'Relleno + entrepaño, cal. 18',
            'relleno y entrepano pijas': 'Relleno + entrepaño, cal. 16, pijas a 150 mm',
            'relleno y entrepano pijas a 75 mm': 'Relleno + entrepaño, cal. 16, pijas a 75 mm',
            'relleno y entrepano cal. 18 pijas': 'Relleno + entrepaño, cal. 18, pijas a 150 mm',
            REC: 'Relleno + entrepaño, cal. 14, pijas a 150 mm'})
ETQ.update({'30x30 cal. 18': 'Proyecto, cal. 18', '30x30 cal. 14': 'Proyecto, cal. 14',
            'PTR 3x3 pulg': 'Proyecto, PTR de 3" x 3" (76.2 mm), comparación', 'sin tornillos entre maleteros': 'Proyecto sin tornillos entre maleteros',
            'relleno sin tornillos entre maleteros': 'Con relleno, sin tornillos entre maleteros',
            'uniones rigidas': 'Proyecto, uniones 10 veces más rígidas'})
B = P.LADO_BASE
NOM_PTR = f'PTR de {B:.0f} x {B:.0f} mm'


def _var_pandeo(n):
    if n.startswith('proyecto'):
        return 'base'
    return 'relleno y entrepano' if 'entrepa' in n else 'relleno'


def _caso_pandeo(V, var, corto):
    if var == REC:
        var = 'relleno y entrepano'     # la estabilidad de la solucion recomendada se toma de esta variante
    for d in V.get('pandeo') or []:
        if _var_pandeo(d['variante']) == var and ('ELU' in d['variante']) == corto:
            return d
    return None


def rango_lambda(V, var, corto, dlam=0.5):
    """Texto del factor de carga limite y su cota inferior."""
    d = _caso_pandeo(V, var, corto)
    if d is None:
        return 'n/d', None
    return texto_lambda(d, dlam), d['lambda_ultimo']


def _lam(x):
    s = f'{x:.3f}'.rstrip('0')
    return s + '0' if s.endswith('.') else s


def aceleracion(d):
    """Pendiente final / pendiente inicial del abombamiento contra λ (tablero vertical que gobierna).
    Cerca de 1 el comportamiento es lineal; muy por encima de 1 la rigidez se pierde (se acerca el pandeo)."""
    c = d.get('curva') or []
    if len(c) < 3:
        return None
    k = 'abombamiento_global' if 'abombamiento_global' in c[-1] else 'abombamiento_lateral'
    s0 = c[0][k] / c[0]['lam']
    s1 = (c[-1][k] - c[-2][k]) / (c[-1]['lam'] - c[-2]['lam'])
    return s1 / s0 if s0 > 0 else None


def texto_lambda(d, dlam=0.5):
    """Intervalo del factor limite: entre el ultimo paso convergido y el menor subpaso que
    pandeo.barrido intento sin converger (paso_falla)."""
    lu = d['lambda_ultimo']
    if d.get('parcial'):
        return f'> {_lam(lu)} (en curso)'
    if d['convergio_hasta_max'] or d.get('nota'):
        return f'> {_lam(lu)}'
    a = aceleracion(d)
    if a is not None and a < 1.6:
        return f'> {_lam(lu)} (detención numérica)'
    return f'{_lam(lu)} a {_lam(lu + d.get("paso_falla", dlam / 4))}'


def abombamiento(V, var, corto, lam_obj=1.0):
    d = _caso_pandeo(V, var, corto)
    if d and d['curva']:
        c = min(d['curva'], key=lambda k: abs(k['lam'] - lam_obj))
        if abs(c['lam'] - lam_obj) < 0.01:
            return c['abombamiento_lateral']
    return None


def tabla_resumen(V):
    vs = [v for v, _ in VARIANTES if v in V['ptr']]
    filas = [['Verificación'] + [ETQ[v] for v in vs] + ['Criterio']]
    colores = []

    def fila(nombre, textos, crit, us, lim=1.0, atn=0.85):
        filas.append([nombre] + textos + [crit])
        colores.append([estado(u, lim=lim, atn=atn) if u is not None else None for u in us])

    pf = {v: V['ptr'][v]['filas'][0] for v in vs}
    fila('PTR: flexión M<sub>u</sub>/φM<sub>n</sub>', [f1(pf[v]['u_M']) for v in vs], '≤ 1.0', [pf[v]['u_M'] for v in vs])
    uvr = {v: max(pf[v]['u_V'], pf[v]['u_R']) for v in vs}
    fila('PTR: cortante y paredes', [f1(uvr[v]) for v in vs], '≤ 1.0', [uvr[v] for v in vs])
    fp = {v: V['flechas_ptr'][v]['frente'] for v in vs}
    fila('PTR frontal: flecha a largo plazo, tramo que gobierna', [f'L/{fp[v]["L_sobre_fin"]:.0f}' for v in vs], '≤ L/300',
         [fp[v]['fin'] / fp[v]['lim'] for v in vs])
    ap = {v: max(f['u'] for f in V['apoyo_tableros'][v]) for v in vs}
    fila('Apoyo del PTR en canto de 15 mm σ/f<sub>c,d</sub>', [f1(ap[v]) for v in vs], '≤ 1.0', [ap[v] for v in vs])
    aps = {v: max(f['u_suplemento'] for f in V['apoyo_tableros'][v]) for v in vs}
    fila('Apoyo con suplemento de canto en el lateral aire', [f1(aps[v]) for v in vs], '≤ 1.0', [aps[v] for v in vs])
    tb = {v: V['tableros'][f'{v}|ELU-T1 1.35G+1.5Q']['filas'][0]['u'] for v in vs}
    fila('Tableros: índice de esfuerzo máximo', [f1(tb[v]) for v in vs], '≤ 1.0', [tb[v] for v in vs])
    un = {v: max(f['u'] for f in V['uniones'][v]['filas']) for v in vs}
    fila('Uniones: demanda / confirmat típicos', [f1(un[v]) for v in vs], '≤ 1.0', [un[v] for v in vs])
    tm = {v: V['tornillos'].get(v) for v in vs}
    fila('Tornillos entre maleteros', [f1(tm[v]['u']) if tm[v] else '-' for v in vs], '≤ 1.0',
         [tm[v]['u'] if tm[v] else None for v in vs])
    if V.get('pandeo'):
        for corto, nom in ((True, 'Estabilidad, corto plazo: λ límite'), (False, 'Estabilidad, largo plazo: λ límite')):
            r = [rango_lambda(V, v, corto) for v in vs]
            fila(nom, [t if t != 'n/d' else '-' for t, _ in r], '≥ 3', [3.0 / x if x else None for _, x in r],
                 lim=2.0, atn=1.0)
        vals = [abombamiento(V, v, False) for v in vs]
        fila('Abombamiento de laterales con carga sostenida', [f'{x:.1f} mm' if x else '-' for x in vals],
             '≤ 870/300 = 2.9 mm', [x / 2.9 if x else None for x in vals])
    d = V['desplome']
    fila('Desplome superior de maleteros a largo plazo, sin anclaje',
         [f'{d[v]["uy_fin"]:.1f} mm' if v in d else '-' for v in vs], '< 5 mm (se resuelve con el anclaje)',
         [d[v]['uy_fin'] / 5 if v in d else None for v in vs], lim=99.0, atn=1.0)
    rp = {v: max(f['u'] for f in V['flechas_repisas'][v]) for v in vs}
    fila('Repisas: flecha diferida / (L/200)', [f1(rp[v]) for v in vs], '≤ 1.0', [rp[v] for v in vs])
    fila('Volteo sin anclaje: aceleración que lo inicia', [f'{V["volteo"]["c_limite"]:.2f} g'] * len(vs),
         'anclar al muro', [2.0] * len(vs))
    t = tabla(filas, [5.0] + [2.55] * len(vs) + [2.3])
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
    cap = V['ptr']['base']['capacidad']
    fa1 = V['ptr']['base']['filas'][0]
    fl = V['flechas_ptr']
    vol = V['volteo']
    des = V['desplome']
    rep = V['reparto_apoyos']
    G_kN = V['peso']['G'] / 1e3
    GQ_kN = V['peso']['G_Q'] / 1e3
    pandeo = V.get('pandeo')
    mn = V['manual']
    tb = {k.split('|')[0]: d['filas'][0] for k, d in V['tableros'].items() if 'ELU-T1' in k}
    un = {v: max(f['u'] for f in d['filas']) for v, d in V['uniones'].items()}
    ap = {v: max(f['u'] for f in d) for v, d in V['apoyo_tableros'].items()}
    tm = V['tornillos']
    gauges = [v for v in ('30x30 cal. 18', 'base', '30x30 cal. 14') if v in fl]
    Lmin = min(fl[v]['frente']['L_sobre_fin'] for v in gauges)
    Lmax = max(fl[v]['frente']['L_sobre_fin'] for v in gauges)
    s_rec = int(min(f['s_local'] for f in V['uniones']['base']['filas']
                    if f['u'] > 1.0 and 'fondo 15mm' in f['union']) // 10 * 10)
    mA, mS = mn['ELU-A1 1.2G+1.6Q'], mn['ELS G+Q']
    fij = V.get('fijacion', {})
    vac = vol['casos']['vacio']
    st = 'sin tornillos entre maleteros'
    rst = 'relleno sin tornillos entre maleteros'
    e18 = 'relleno y entrepano cal. 18'

    def abomb(var, corto):
        x = abombamiento(V, var, corto)
        return x if x is not None else float('nan')

    def mm(x, d=1):
        return '-' if x != x else f'{x:.{d}f} mm'

    H = []
    # ------------------------------------------------------------------ portada
    H += [Spacer(1, 1.2 * cm), p('Memoria de cálculo estructural', 'titulo'),
          p(f'Closet con tres maleteros apoyados en dos {NOM_PTR} sobre dos torres de melamina', 'sub'),
          p(f'Archivo de proyecto: <i>closet pedido mx.skp</i> (SketchUp 2023) y diagrama de corte del 15/08/2025.'
            f' Fecha del cálculo: {hoy}. Revisión 2: el PTR es de {B:.0f} x {B:.0f} mm (3 x 3 cm); esta revisión '
            'sustituye a la anterior, que suponía un PTR de 3" x 3".', 'p'), Spacer(1, 0.3 * cm)]
    H += [p('Resumen ejecutivo', 'h2')]
    fbase = fl['base']['frente']
    items = [
        f'<b>El {NOM_PTR} trabaja como viga continua sobre los cuatro laterales de las torres</b> (los exteriores y '
        f'los laterales aire). Con apoyos firmes necesitaría {mA["M_continua"] / 1e6:.2f} kN·m, el '
        f'{mA["M_continua"] / cap["phiMn"]:.0%} de su resistencia de {cap["phiMn"] / 1e6:.2f} kN·m, y su flecha de servicio '
        f'sería de unos {mS["flecha_continua"]:.0f} mm en el tramo central: la sección alcanza si los apoyos no ceden. Si '
        f'el lateral aire no lo apoyara, como viga simple de 2865 mm necesitaría {mA["M_manual"] / 1e6:.2f} kN·m '
        f'({mA["M_manual"] / cap["phiMn"]:.1f} veces su resistencia). En el modelo, con la rigidez {fa1["rigidez"]} de la melamina, el '
        f'momento máximo del proyecto es {fa1["Mu"] / 1e6:.2f} kN·m ({fa1["u_M"]:.0%}).',
        f'<b>El proyecto tal cual no cumple.</b> Flecha del PTR frontal {f1(fbase["inst"], 1)} mm instantánea y '
        f'{f1(fbase["fin"], 1)} mm a largo plazo (L/{fbase["L_sobre_fin"]:.0f} en el tramo {fbase["tramo"]}, límite L/300); '
        f'tablero trasero de la torre con índice {f1(tb["base"]["u"])}; uniones al {un["base"]:.0%} de su capacidad; '
        f'tornillos entre maleteros al {tm["base"]["u"]:.0%}; desplome de {f1(des["base"]["uy_max"], 1)} mm; y el lateral '
        f'exterior se abomba {mm(abomb("base", False), 0)} con la carga sostenida. Cambiar el calibre del tubo (18, 16 o '
        f'14) no lo resuelve: la flecha queda entre L/{Lmin:.0f} y L/{Lmax:.0f}.',
        'La causa es el apoyo, no el tubo: el lateral interior de cada torre ("lateral aire", 900 mm) no llega al piso; '
        'entre la cubierta de cajones y su canto inferior hay un hueco abierto de 205 mm. Ese lateral recibe la mayor '
        f'parte de la carga del PTR frontal ({rep["base"]["frente|torre izq"].get("lateral aire", 0) / 1e3:.2f} kN en '
        f'servicio, contra {rep["base"]["frente|torre izq"].get("lateral exterior", 0) / 1e3:.2f} kN del lateral exterior), '
        'cede porque cuelga de tornillos al tablero trasero y lo sobrecarga.',
        f'<b>Con un relleno de 15 mm (585 x 205 mm) bajo cada lateral aire, el lateral aire queda como apoyo firme y el '
        f'sistema cumple en resistencia y flecha con tubo cal. 16</b>: L/{fl["relleno"]["frente"]["L_sobre_fin"]:.0f} a '
        f'largo plazo en el tramo {fl["relleno"]["frente"]["tramo"]}, tableros con índice {f1(tb["relleno"]["u"])} y '
        f'uniones al {un["relleno"]:.0%}. Ese resultado supone una fijación casi rígida entre el tubo y los tableros; con '
        f'una fijación realista de pijas a cada 150 mm la flecha del tramo central queda en '
        f'L/{fl["relleno y entrepano pijas"]["frente"]["L_sobre_fin"]:.0f} con cal. 16, al límite, y en '
        f'L/{fl["relleno y entrepano cal. 18 pijas"]["frente"]["L_sobre_fin"]:.0f} con cal. 18. <b>Con tubo cal. 14 y pijas '
        f'cumple todo</b>: L/{fl[REC]["frente"]["L_sobre_fin"]:.0f}, flexión al {V["ptr"][REC]["filas"][0]["u_M"]:.0%}, '
        f'pija más cargada al {fij[REC][0]["u"]:.0%}.',
    ]
    if pandeo:
        items.append(
            f'<b>Estabilidad.</b> El canto frontal de los laterales queda libre 870 mm en el compartimento superior. En el '
            f'proyecto, con la carga sostenida, el lateral exterior se abomba {mm(abomb("base", False), 0)}. Solo con el '
            f'relleno baja a {mm(abomb("relleno", False))} (límite visual 2.9 mm, λ límite '
            f'{rango_lambda(V, "relleno", False)[0]}). Con relleno y <b>un entrepaño fijo intermedio a 1120 mm</b> en cada '
            f'torre queda en {mm(abomb("relleno y entrepano", False))} y λ {rango_lambda(V, "relleno y entrepano", False)[0]}.')
    ap_sup = max(f['u_suplemento'] for v in ('relleno', rst, e18, REC) for f in V['apoyo_tableros'].get(v, []))
    items += [
        f'<b>El apoyo del tubo sobre los cantos de 15 mm queda al límite</b>: {ap["relleno"]:.2f} de la resistencia con '
        f'relleno y {ap[rst]:.3f} si además se omiten los tornillos entre maleteros. Un suplemento de canto de 15 mm '
        f'encolado y atornillado a la cara interior de cada lateral aire, a ras de su canto superior, lo baja a '
        f'{ap_sup:.2f}.',
        f'Sin anclaje, el mueble vacío se voltea con una aceleración horizontal de {vac["c_limite"]:.2f} g y cargado con '
        f'{vol["casos"]["cargado"]["c_limite"]:.2f} g. Hay que fijarlo al muro: {vol["anclas"][-1]["F"] / 1e3:.2f} kN por '
        f'torre y hasta {max(a["F"] for a in vol["anclas"] if a["xyz"][2] > 2000) / 1e3:.2f} kN por taquete de maletero con '
        'el coeficiente adoptado. El anclaje también limita el desplome en servicio.',
        'Las repisas de 15 mm cumplen resistencia; con carga de almacenamiento sostenida su flecha diferida supera L/200. '
        'Es un tema de apariencia que se corrige con un apoyo intermedio en el piso de los maleteros y un refuerzo '
        'frontal en los entrepaños de torre.',
    ]
    H += lista(items)
    H += [PageBreak(), p('Resumen de verificaciones', 'h2')]
    H += [tabla_resumen(V), p('Verde: cumple con holgura. Amarillo: al límite o requiere atención. Rojo: no cumple. '
                              'Tubo cal. 16 y fijación rígida del PTR salvo indicación; "-" indica caso no analizado. La '
                              'estabilidad de la solución recomendada se toma de la variante con relleno y entrepaño.', 'cap')]
    H += [PageBreak()]

    # ------------------------------------------------------------------ 1. alcance
    H += [p('1. Objeto y alcance', 'h1'),
          p(f'Se verifica la estructura del closet con la modificación indicada por el cliente: dos {NOM_PTR} '
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
        ['Conjunto', f'2880 de frente x 600 de fondo; altura 2440 en el proyecto, {2440 + B:.0f} con los PTR bajo maleteros',
         'Dos torres en los extremos, hueco central de 1640 mm, tres maleteros arriba'],
        ['Torre (x2)', '620 x 600 x 1570 (zócalo 100 + casco 1470)',
         'Lateral exterior 1455, trasero 15 mm de 605 x 1455, piso, 2 cajones, cubierta 605 x 585 a 450, '
         'entrepaño con amarres a 685, travesaños superiores 590 x 100, puerta 618 x 897'],
        ['Lado interior de torre', 'Panel inferior 585 x 335 (z 115 a 450); lateral aire 585 x 900 (z 670 a 1570)',
         'Hueco abierto de 205 mm entre z 465 y 670: el lateral aire no tiene apoyo directo hacia el piso'],
        ['Maletero (x3)', '960 x 870 x 600', 'Costados de altura completa, piso y techo entre costados, dos tiras '
         'traseras de 200 mm, travesaño frontal 930 x 100, dos puertas 478 x 855'],
        ['PTR (x2)', f'{B:.0f} x {B:.0f}, L = 2880', 'Uno a paño frontal y otro a paño trasero, bajo los costados y el piso '
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
    filas = [
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
    ]
    for v in ('30x30 cal. 18', 'base', '30x30 cal. 14'):
        if v in V['ptr']:
            c = V['ptr'][v]['capacidad']
            filas.append([f'{NOM_PTR} {c["perfil"].split(" ", 1)[1]}', f't = {c["t_nom"]:.2f} mm nominal, {c["t"]:.2f} mm de '
                          f'diseño; A = {c["A"] / 100:.2f} cm²; '
                          f'I = {c["I"] / 1e4:.2f} cm⁴; Z = {c["Z"] / 1e3:.2f} cm³; {c["masa"]:.2f} kg/m',
                          'Espesor de diseño 0.93 t (AISC B4.2); radio exterior 2t' + (' (caso base)' if v == 'base' else '')])
    filas.append(['Confirmat 7 x 50 en melamina 15 mm', f'F<sub>v,k</sub> = {P.CONFIRMAT["Fv_k"] / 1e3:.1f} kN; '
                  f'F<sub>ax,k</sub> = {P.CONFIRMAT["Fax_k"] / 1e3:.1f} kN', 'Valores adoptados, verificar con el fabricante. '
                  'Se usan también para los tornillos de unión entre maleteros y las pijas del PTR, del lado conservador'])
    H += [tabla(filas, [5.5, 5.8, 6.2])]

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
        f'Los PTR de {B:.0f} x {B:.0f} mm son vigas elásticas 3D en su eje; los maleteros se elevan {B:.0f} mm. El '
        'contacto vertical con torres y maleteros es solo a compresión (el mueble descansa sobre el PTR); en horizontal '
        'la fijación se supone rígida, y en la sección 6.6 se repite con pijas de rigidez realista. Se resuelve por '
        'Newton para cada combinación.',
        'Base del zócalo articulada en el piso. Puertas y cajones se aplican como cargas en el tablero que los '
        'soporta (bisagras del lado del lateral aire en las torres).',
        'Controles: el peso del modelo coincide con el del despiece; las reacciones igualan la carga aplicada; '
        'los resultados son simétricos entre torres; no quedan contactos en tracción.',
    ])
    H += [p('Variantes analizadas, cada una a corto y largo plazo: proyecto con tubo cal. 18, 16 y 14; proyecto sin '
            'tornillos entre maleteros; relleno de 15 mm bajo cada lateral aire, con y sin tornillos entre maleteros; '
            'relleno más un entrepaño fijo intermedio a 1120 mm en cada torre, con tubo cal. 16 y cal. 18, y con fijación '
            'del PTR por pijas; y, como referencia, el proyecto con PTR de 3" x 3". Las variantes principales se revisan '
            'en estado último también con la rigidez final de la melamina. Además uniones diez veces más rígidas '
            '(sensibilidad) y caso horizontal con anclajes al muro.')]

    # ------------------------------------------------------------------ 6. resultados
    H += [PageBreak(), p('6. Resultados', 'h1'), p('6.1 Cómo trabaja el conjunto y cómo llega la carga a las torres', 'h2'),
          p(f'El tubo de {B:.0f} x {B:.0f} mm se apoya en los cuatro laterales de las torres y comparte la carga con los '
            'maleteros, que son más rígidos que él y están fijados a él. Lo que decide el comportamiento es la rigidez de '
            'los apoyos. La figura 3 y la tabla muestran qué elemento de la torre recibe la reacción de cada PTR. En el '
            'proyecto, el lateral aire recibe la mayor parte del frente aunque no llega al piso; la pasa por tornillos al '
            'tablero trasero y por eso cede. El PTR trasero se apoya sobre todo en el canto del tablero trasero de 15 mm, '
            'que trabaja como muro.')]
    H += fig('fig05_reparto_apoyos.png', 16.5, 'Figura 3. Reacción de cada PTR sobre los elementos de la torre izquierda (la derecha es simétrica), combinación G + Q.')
    vs = [v for v in ('base', 'relleno', 'relleno y entrepano', st) if v in rep]
    filas = [['PTR / elemento de la torre'] + [f'{ETQ[v]} (kN)' for v in vs]]
    for ptr in ('frente', 'fondo'):
        for el in ('lateral exterior', 'lateral aire', 'trasero 15 mm'):
            vals = [rep[v][f'{ptr}|torre izq'].get(el, 0.0) / 1e3 for v in vs]
            if any(vals):
                filas.append([f'PTR {ptr}: {el}'] + [f1(x) for x in vals])
    H += [tabla(filas, [5.0] + [3.1] * len(vs))]

    H += [p(f'6.2 {NOM_PTR}', 'h2'),
          p(f'Sección compacta en los tres calibres (b/t = {cap["b_t"]:.1f} en cal. 16, λ<sub>p</sub> = {cap["lp_f"]:.1f}). '
            'Resistencias de diseño AISC 360-16 (F7, G4 y J10) con espesor de diseño 0.93 t; como no se conoce el radio '
            'de esquina se usan b = h = B - 3t y k = 1.5t. La revisión de paredes compara la reacción del lateral exterior '
            'con la resistencia de extremo y la del lateral aire con la interior. Como el reparto de cargas entre el tubo y '
            'la melamina depende de la rigidez, la flexión se revisa con la rigidez instantánea y con la final, '
            'E/(1 + ψ<sub>2</sub>k<sub>def</sub>), según EN 1995-1-1 2.3.2.2; la tabla da la que gobierna.'),
          p(f'Comprobación manual con la carga que los maleteros apoyan en el PTR frontal ({mA["W"] / 1e3:.2f} kN en '
            f'1.2G + 1.6Q y {mS["W"] / 1e3:.2f} kN en G + Q), repartida a lo largo del tubo. Como viga continua sobre los '
            f'cuatro laterales con apoyos firmes: M<sub>u</sub> = {mA["M_continua"] / 1e6:.2f} kN·m y flecha de servicio '
            f'de {mS["flecha_continua"]:.1f} mm en el tramo central. Como viga simple de 2865 mm, si el lateral aire no '
            f'apoyara: M<sub>u</sub> = WL/8 = {mA["M_manual"] / 1e6:.2f} kN·m y 5WL³/384EI = {mS["flecha_manual"]:.0f} mm. '
            f'El modelo da {mA["M_fe"] / 1e6:.2f} kN·m con rigidez instantánea: menos que la viga continua porque los '
            'maleteros, más rígidos que el tubo y fijados a él, toman parte de la carga. En el proyecto la flecha del modelo '
            f'({mS["flecha_fe"]:.1f} mm respecto a los laterales exteriores) es mucho mayor que la de la viga continua porque '
            'el lateral aire cede: es un apoyo flexible.')]
    H += fig('fig04_ptr_diagramas.png', 16.5, 'Figura 4. Momento y cortante últimos (1.2G + 1.6Q, rigidez instantánea) '
             'y desplazamiento en servicio (G + Q) a lo largo de cada PTR.')
    filas = [['Variante', 'Perfil', 'φM<sub>n</sub> (kN·m)', 'M<sub>u</sub>/φM<sub>n</sub> (rigidez)',
              'V<sub>u</sub>/φV<sub>n</sub>', 'Flecha G+Q (mm)', 'Flecha largo plazo (mm)', 'Relación (tramo)']]
    est = []
    for var in ('base', '30x30 cal. 18', '30x30 cal. 14', st, 'relleno', rst, 'relleno y entrepano', e18,
                'relleno y entrepano pijas', 'relleno y entrepano pijas a 75 mm', 'relleno y entrepano cal. 18 pijas', REC,
                'PTR 3x3 pulg'):
        if var not in V['ptr'] or var not in fl:
            continue
        c = V['ptr'][var]['capacidad']
        f = V['ptr'][var]['filas'][0]
        d = fl[var]['frente']
        filas.append([ETQ[var], c['perfil'].replace('30x30', f'{B:.0f}x{B:.0f}'), f1(c['phiMn'] / 1e6),
                      f'{f1(f["u_M"])} ({f["rigidez"]})', f1(max(g['u_V'] for g in V['ptr'][var]['filas'])),
                      f1(d['inst'], 1), f1(d['fin'], 1), f'L/{d["L_sobre_fin"]:.0f} ({d["tramo"]})'])
        est.append(estado(max(f['u_M'], d['fin'] / d['lim'])))
    H += [tabla(filas, [4.2, 2.1, 1.5, 2.3, 1.4, 1.6, 1.9, 2.5], est)]
    H += [p('Flecha del PTR frontal respecto a dos cuerdas: entre laterales exteriores (L = 2865 mm, límite 9.6 mm) y '
            'entre laterales aire (tramo central, L = 1655 mm, límite 5.5 mm); se informa la que gobierna. El PTR de '
            '3" x 3" se incluye solo como comparación con la revisión anterior.')]

    H += [p('6.3 Deformaciones', 'h2')]
    filas = [['Elemento', 'Variante', 'Instantánea G+Q (mm)', 'Largo plazo (mm)', 'Límite (mm)', 'Relación']]
    est = []
    for var in ('base', 'relleno', 'relleno y entrepano', REC):
        if var not in fl:
            continue
        for ptr in ('frente', 'fondo'):
            for tramo, d in fl[var][ptr]['tramos'].items():
                filas.append([f'PTR {ptr}, tramo {tramo} (L = {d["L"]:.0f} mm)', ETQ[var], f1(d['inst']), f1(d['fin']),
                              f'{d["lim"]:.1f} (L/300)', f'L/{d["L_sobre_fin"]:.0f}'])
                est.append(estado(d['fin'] / d['lim']))
    for var in ('base', 'relleno'):
        for d in V['flechas_repisas'].get(var, []):
            filas.append([f'{legible(d["tablero"])} (L = {d["L"]:.0f})', ETQ[var], f1(d['inst']), f1(d['fin']),
                          f'{d["lim"]:.1f} (L/200)', f'L/{d["L"] / d["fin"]:.0f}'])
            est.append(estado(d['u'], atn=0.85))
    H += [tabla(filas, [5.6, 3.4, 2.3, 2.1, 2.1, 1.7], est)]
    rep_r = max(d['u'] for d in V['flechas_repisas']['relleno'])
    rep_b = next(d for d in V['flechas_repisas']['base'] if d['tablero'].startswith('PTRSOP024'))
    rep_e = next(d for d in V['flechas_repisas']['relleno'] if d['tablero'].startswith('PTRSOP024'))
    H += [p(f'Desplome hacia el frente en la parte alta de los maleteros, sin anclaje al muro: '
            f'{f1(des["base"]["uy_max"], 1)} mm instantáneo en el proyecto y {f1(des["relleno"]["uy_max"], 1)} mm con '
            f'relleno; con la fluencia llega a {f1(des["base"]["uy_fin"], 1)} y {f1(des["relleno"]["uy_fin"], 1)} mm. '
            'Proviene de que el frente baja más que el fondo y gira los maleteros; el anclaje superior al muro lo '
            'restringe, así que es necesario también en servicio. '
            f'En el proyecto la flecha diferida del entrepaño (tope) ({f1(rep_b["fin"], 1)} mm, '
            f'L/{rep_b["L"] / rep_b["fin"]:.0f}) es más del doble que con relleno ({f1(rep_e["fin"], 1)} mm): la '
            'diferencia es la carga que le cuelga el lateral aire. Con relleno '
            f'las repisas cumplen resistencia, pero su flecha diferida con 1.2 kN/m² sostenidos excede L/200 (hasta '
            f'{rep_r:.1f} veces el límite). En el piso de maletero, que trabaja de frente a fondo entre los dos PTR, eso '
            'se corrige con un apoyo intermedio a media profundidad o con un tablero más grueso; en los entrepaños de '
            'torre, con un refuerzo frontal.')]
    H += fig('fig02_deformada.png', 13.0, 'Figura 5. Deformada del proyecto en servicio, amplificada 40 veces.')
    H += fig('fig02b_deformada_relleno.png', 13.0, 'Figura 6. Deformada con relleno bajo el lateral aire, misma escala de amplificación.')

    H += [p('6.4 Esfuerzos en tableros', 'h2'),
          p('Índice de esfuerzo = esfuerzo de membrana / resistencia + esfuerzo de flexión / f<sub>m,d</sub>, por '
            'dirección y en cortante. Se informa el valor promediado en un radio de 75 mm (representativo) y el pico '
            'puntual, que aparece en esquinas de líneas de unión donde el modelo concentra fuerzas en un nodo.')]
    filas = [['Tablero', 'Variante y combinación', 'Pico puntual', 'Índice promediado']]
    est = []
    for clave in ('base|ELU-T1 1.35G+1.5Q', f'{st}|ELU-T1 1.35G+1.5Q', 'relleno|ELU-T1 1.35G+1.5Q',
                  'relleno y entrepano|ELU-T1 1.35G+1.5Q'):
        if clave not in V['tableros']:
            continue
        var, comb = clave.split('|')
        for t in V['tableros'][clave]['filas'][:3]:
            filas.append([legible(t['tablero']), f'{ETQ[var]}, {comb.split(" ", 1)[1]}', f1(t['u_pico']), f1(t['u'])])
            est.append(estado(t['u']))
    H += [tabla(filas, [5.0, 6.4, 2.6, 3.0], est)]
    H += [p(f'El máximo del proyecto está en el tablero trasero de la torre junto al canto inferior del lateral aire '
            f'(índice {f1(tb["base"]["u"])} promediado, {f1(tb["base"]["u_pico"])} puntual): ahí entra en el trasero la carga '
            'que cuelga del lateral aire. Con el relleno esa concentración desaparece.')]

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
    for var in ('base', 'relleno', 'relleno y entrepano'):
        for f in V['uniones'].get(var, {}).get('filas', [])[:4]:
            filas.append([f'{ETQ[var]}: {legible(f["union"])}', f'{f["L"]:.0f}', f'{f["T"]:.0f}', f'{f["V"]:.0f}',
                          f'{f["n_req"]}', f'{f["n_tip"]}', f'{min(f["s_local"], 999):.0f}'])
            est.append(estado(f['u'], atn=0.85))
    H += [tabla(filas, [6.2, 1.2, 1.6, 1.6, 2.1, 2.0, 2.4], est)]

    H += [p('6.6 Tornillos entre maleteros y fijación del PTR', 'h2'),
          p('El modelo supone cuatro tornillos de unión por cada costado común entre maleteros contiguos, cerca de las '
            'esquinas. Como unen cara con cara dos costados de 15 mm, deben ser tornillos pasantes de unión de módulos '
            '(M6 con casquillo o tuerca), no confirmat. Solo la tracción carga al tornillo; en compresión los costados se '
            'apoyan entre sí. La interacción se calcula tornillo por tornillo con 1.35G + 1.5Q y, a falta de datos del '
            f'fabricante, con las capacidades adoptadas para el confirmat (corte {V["uniones"]["base"]["conector"]["Fv_d"]:.0f} N, '
            f'tracción {V["uniones"]["base"]["conector"]["Fax_d"]:.0f} N), que son conservadoras para un tornillo pasante.')]
    filas = [['Variante', 'Tracción máx. (N)', 'Cortante máx. (N)', 'Tornillo que gobierna: T / V (N)', 'Relación']]
    est = []
    for var in ('base', st, 'relleno', rst, 'relleno y entrepano', e18, REC):
        t_ = tm.get(var)
        if t_:
            filas.append([ETQ[var], f'{t_["axial"]:.0f}', f'{t_["corte"]:.0f}',
                          f'{t_["axial_gob"]:.0f} / {t_["corte_gob"]:.0f}', f1(t_['u'])])
            est.append(estado(t_['u']))
    H += [tabla(filas, [6.0, 2.4, 2.4, 3.6, 1.8], est)]
    H += [p(f'Sin esos tornillos el proyecto empeora (flecha L/{fl[st]["frente"]["L_sobre_fin"]:.0f}, tablero trasero '
            f'{f1(tb[st]["u"])}, uniones al {un[st]:.0%}). Con relleno la flecha y las uniones siguen cumpliendo sin ellos '
            f'(L/{fl[rst]["frente"]["L_sobre_fin"]:.0f}, uniones al {un[rst]:.0%}), pero el apoyo del lateral aire sube de '
            f'{ap["relleno"]:.2f} a {ap[rst]:.3f}. Conviene colocarlos: bajan la flecha y la compresión en ese canto.')]
    # fijacion PTR-maletero
    pj = [v for v in ('relleno y entrepano pijas', 'relleno y entrepano cal. 18 pijas') if v in fl]
    H += [p('El contacto entre el PTR y los tableros solo transmite compresión en vertical; en horizontal el modelo base '
            'supone una fijación rígida, que hace trabajar juntos al tubo y a los maleteros. Para ver cuánto pesa esa '
            'hipótesis se repitió la solución con una fijación realista: pijas a cada 150 mm, de 1500 N/mm cada una, en '
            'torres y maleteros, y también a cada 75 mm.')]
    filas = [['Variante', 'Fijación', 'M<sub>u</sub>/φM<sub>n</sub>', 'Flecha largo plazo', 'Tableros', 'Uniones',
              'Tornillos entre maleteros', 'Pija más cargada (N)']]
    est = []
    for var, v_, nom in (('relleno y entrepano', 'relleno y entrepano', 'rígida'),
                         ('relleno y entrepano', 'relleno y entrepano pijas', 'pijas a 150 mm'),
                         ('relleno y entrepano', 'relleno y entrepano pijas a 75 mm', 'pijas a 75 mm'),
                         (e18, e18, 'rígida'), (e18, 'relleno y entrepano cal. 18 pijas', 'pijas a 150 mm'),
                         ('Relleno + entrepaño, cal. 14', REC, 'pijas a 150 mm')):
        if v_ not in fl or v_ not in V['ptr']:
            continue
        fj = fij.get(v_)
        fp_ = fl[v_]['frente']
        filas.append([ETQ.get(var, var), nom, f1(V['ptr'][v_]['filas'][0]['u_M']), f'L/{fp_["L_sobre_fin"]:.0f}',
                      f1(tb[v_]['u']), f1(un[v_]), f1(tm[v_]['u']) if tm.get(v_) else '-',
                      f'{fj[0]["por_pija"]:.0f}' if fj else '-'])
        est.append(estado(max(V['ptr'][v_]['filas'][0]['u_M'], fp_['fin'] / fp_['lim'], tb[v_]['u'], un[v_],
                              tm[v_]['u'] if tm.get(v_) else 0, fj[0]['u'] if fj else 0)))
    if pj:
        H += [tabla(filas, [3.8, 2.3, 1.6, 2.1, 1.6, 1.5, 2.1, 2.3], est)]
        fr = fij['relleno y entrepano']
        H += [p('Con fijación rígida cada tramo de 150 mm de tubo tendría que transmitir hasta '
                f'{fr[0]["por_pija"]:.0f} N en horizontal, más de lo que da una pija en melamina '
                f'({fr[0]["Fv_d"]:.0f} N de diseño, valor adoptado igual al del confirmat): la fijación rígida no es '
                'alcanzable con pijas y las variantes con pijas son las representativas. Con ellas la fuerza por pija es '
                f'aceptable ({fij["relleno y entrepano pijas"][0]["por_pija"]:.0f} N con cal. 16 y '
                f'{fij[REC][0]["por_pija"]:.0f} N con cal. 14), pero la flecha del tramo central crece: con cal. 16 queda al '
                'límite y con cal. 18 no cumple. Con cal. 14 todo cumple, y por eso es la solución recomendada.')]

    H += [p('6.7 Apoyo del PTR sobre cantos de tablero', 'h2'),
          p('El PTR descansa sobre el canto de 15 mm de los tableros. Se usan las fuerzas de contacto nodo por nodo de '
            '1.35G + 1.5Q y se comparan con f<sub>c,d</sub> = '
            f'{V["apoyo_tableros"]["base"][0]["fc_d"]:.2f} MPa. En los laterales bajo el PTR frontal el área es 15 mm por el '
            f'solape de {B:.0f} mm con el tubo. Bajo el PTR trasero el tubo se arquea sobre la torre y apoya casi todo en la '
            'esquina del lateral aire con el tablero trasero; ahí se revisa la esquina en conjunto: el lateral aire en '
            '15 x 15 mm (la otra mitad de la huella cae sobre el trasero) más el trasero en 30 mm de largo. La última '
            'columna da la relación con un suplemento de canto: un tablero de 15 mm encolado y atornillado a la cara '
            'interior del lateral aire, a ras de su canto superior, que duplica el ancho de apoyo.')]
    filas = [['Apoyo', 'Variante', 'Reacción (kN)', 'Área (mm²)', 'σ (MPa)', 'σ/f<sub>c,d</sub>', 'Con suplemento']]
    est = []
    for var in ('base', 'relleno', rst, REC):
        for f in V['apoyo_tableros'].get(var, []):
            if f['R'] < 50:
                continue
            filas.append([f['apoyo'], ETQ[var], f1(f['R'] / 1e3), f'{f["area"]:.0f}', f1(f['sigma']), f1(f['u']),
                          f1(f['u_suplemento'])])
            est.append(estado(f['u']))
    H += [tabla(filas, [4.6, 3.6, 1.7, 1.6, 1.4, 1.5, 1.8], est)]
    esq = {v: next((f for f in V['apoyo_tableros'][v] if 'esquina' in f['apoyo']), None) for v in ('base', 'relleno')}
    ap_sup = max(f['u_suplemento'] for v in ('relleno', rst, e18, REC) for f in V['apoyo_tableros'].get(v, []))
    H += [p(f'Con relleno el canto del lateral aire queda al {ap["relleno"]:.0%} de la resistencia de diseño y sin '
            f'tornillos entre maleteros al {ap[rst]:.1%}. En la esquina trasera el trasero recibe '
            f'{esq["relleno"]["R_trasero_esquina"] / 1e3:.2f} de sus {esq["relleno"]["R_trasero_total"] / 1e3:.2f} kN dentro '
            f'de 30 mm del lateral aire. Con el suplemento de canto la relación más alta baja a {ap_sup:.2f}. El suplemento '
            'entrega la mitad de la reacción al lateral aire por cortante: tres confirmat más cola dan '
            f'{3 * V["uniones"]["base"]["conector"]["Fv_d"] / 1e3:.2f} kN solo con los tornillos, más que la mitad de la '
            'reacción del lateral aire en cualquier variante.')]

    H += [p('6.8 Estabilidad de laterales', 'h2')]
    if pandeo:
        from figuras import southwell
        H += [p('Se repitió el análisis con no linealidad geométrica (cascarones ASDShellQ4 corrotacionales y PTR '
                'corrotacional). La combinación se incrementa por un factor λ con una pequeña perturbación lateral en '
                'el canto libre de cada lateral. Se mide el abombamiento de los laterales respecto al plano de sus '
                'esquinas.')]
        filas = [['Caso', 'Abombamiento a λ = 1 (mm)', 'Pieza que gobierna', 'Factor de carga límite λ',
                  'Pendiente final / inicial', 'λ<sub>cr</sub> de Southwell (referencia)']]
        est = []
        for d in pandeo:
            c1 = min(d['curva'], key=lambda k: abs(k['lam'] - 1.0)) if d['curva'] else None
            lc = southwell(d['curva'])
            lu = d['lambda_ultimo']
            txt = texto_lambda(d)
            ab1 = c1['abombamiento_lateral'] if c1 else None
            ac = aceleracion(d)
            filas.append([d['variante'].replace('gamma_M', 'γM'), f1(ab1) if c1 else '-',
                          legible(c1['pieza']) if c1 else '-', txt, f'{ac:.1f}' if ac else '-',
                          f'{lc:.1f}' if lc else '-'])
            u_ab = (ab1 / 2.9) if (ab1 is not None and 'largo' in d['variante']) else 0.0
            est.append('mal' if (lu < 1.5 or u_ab > 1.0) else ('atn' if lu < 3.0 else 'ok'))
        H += [tabla(filas, [4.2, 2.3, 2.7, 3.4, 2.0, 2.9], est)]
        H += [p('El factor de carga límite es el intervalo entre el último paso convergido y el menor incremento que ya no '
                'converge (antes de detenerse se reintenta con pasos de 1/4 y 1/16 y con otros algoritmos). Cada corrida '
                'tiene un tope de 50 minutos de cálculo; las marcadas con ">" se detuvieron por ese tope o al llegar a '
                'λ = 4 y el valor es una cota inferior. La pendiente final / inicial compara cómo crece el abombamiento del '
                'tablero vertical que gobierna al final y al principio de la corrida: cerca de 1 el comportamiento es lineal '
                'y muy por encima de 1 la rigidez se está perdiendo. Con pendiente cercana a 1, una corrida que deja de '
                'converger no muestra pandeo y se marca como detención numérica. La recta de Southwell se da solo como '
                'referencia. Criterios: con λ de 3 o más se considera holgado, entre 1.5 y 3 al límite y por debajo de 1.5 '
                'no cumple; además, el abombamiento con la carga sostenida no debe pasar de L/300 del tramo libre (2.9 mm), '
                'para que el lateral no se vea pandeado con el tiempo.')]
        d0 = _caso_pandeo(V, 'base', True)
        lat0 = next((f['u'] for f in V['tableros']['base|ELU-T1 1.35G+1.5Q']['filas']
                     if f['tablero'].startswith('ESPCL-LD')), None)
        if d0 and d0['curva'] and lat0 is not None:
            H += [p(f'En el proyecto la corrida a corto plazo llega a λ = {_lam(d0["lambda_ultimo"])}, pero eso no indica una '
                    f'reserva real: el lateral exterior ya se abomba {mm(abomb("base", True))} a λ = 1 y '
                    f'{d0["curva"][-1]["abombamiento_lateral"]:.0f} mm al final de la corrida. No hay un pandeo súbito sino '
                    'una flexión fuera del plano que crece con la carga, y el tablero se agota antes por resistencia (índice '
                    f'{f1(lat0)} del lateral exterior en el análisis lineal, sección 6.4) y por la deformación diferida.')]
        H += fig('fig06_pandeo.png', 16.0, 'Figura 7. Factor de carga contra abombamiento máximo de laterales. Línea '
                 'discontinua: 2.9 mm; las curvas que salen de la escala se indican con su último punto.')
        H += fig('fig07_modo_pandeo.png', 9.5, 'Figura 8. Abombamiento del lateral exterior izquierdo en el último paso '
                 'convergido del proyecto a corto plazo: se concentra en el canto frontal libre.')
    else:
        H += [p('(Análisis no lineal geométrico no disponible en esta corrida.)')]

    H += [p('6.9 Volteo y anclaje al muro', 'h2'),
          p(f'Con G + ψ<sub>2</sub>Q, barra incluida, el centro de masa queda a {vol["z_cm"]:.0f} mm de altura y '
            f'{vol["y_cm"]:.0f} mm detrás de la cara frontal del zócalo; vacío, a {vac["z_cm"]:.0f} mm y {vac["brazo"]:.0f} mm. '
            f'Sin anclaje, la aceleración horizontal que inicia el volteo es {vac["c_limite"]:.2f} g con el mueble vacío y '
            f'{vol["casos"]["cargado"]["c_limite"]:.2f} g cargado. Con H = {C["c_sismico"]}(G + ψ<sub>2</sub>Q) = '
            f'{vol["H"] / 1e3:.2f} kN el factor de seguridad sin anclaje sería {vol["FS"]:.2f}. Fuerzas en anclajes del '
            'modelo con taquetes en la parte alta trasera:')]
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
        f'<b>Con el {NOM_PTR} el mueble, tal como está diseñado, no cumple</b>: la flecha del conjunto, las uniones '
        'y el tablero trasero de las torres quedan fuera de criterio, y los laterales exteriores se pandean con la '
        'carga sostenida. El calibre del tubo no cambia esa conclusión, porque lo que falla es el apoyo del tubo en el '
        'lateral aire.',
        '<b>Colocar un relleno de melamina de 15 mm (585 x 205 mm) bajo cada lateral aire</b>, entre la cubierta de '
        'cajones y el amarre inferior, confirmado a la cubierta, al trasero y a los amarres. Así el lateral aire '
        'apoya en compresión directa hasta el piso. Alternativa equivalente: un lateral interior de una pieza de '
        '585 x 1455 mm.',
        f'<b>Usar tubo de {B:.0f} x {B:.0f} mm cal. 14</b> (1.9 mm). Con relleno, entrepaño y pijas cumple resistencia y '
        f'flecha (L/{fl[REC]["frente"]["L_sobre_fin"]:.0f}); el cal. 16 queda al límite de la flecha del tramo central '
        f'(L/{fl["relleno y entrepano pijas"]["frente"]["L_sobre_fin"]:.0f} con pijas a 150 mm y '
        f'L/{fl["relleno y entrepano pijas a 75 mm"]["frente"]["L_sobre_fin"]:.0f} a 75 mm) y el cal. 18 no cumple.',
        '<b>Agregar un entrepaño fijo intermedio</b> (590 x 585 x 15 mm, a unos 1120 mm del piso) en el compartimento '
        'superior de cada torre, confirmado a los dos laterales y al trasero con separación máxima de 150 mm. Arriostra '
        'el canto frontal de los laterales, que controla la estabilidad. Si se prefiere no perder el espacio, la '
        'alternativa es un poste metálico (PTR de 1" o ángulo de 1 1/2") en cada esquina frontal de la torre, desde el '
        'piso hasta el PTR.',
        '<b>Colocar un suplemento de canto en cada lateral aire</b>: una pieza de melamina de 15 mm de unos 585 x 100 mm, '
        'encolada y con tres confirmat a la cara interior del lateral aire, a ras de su canto superior, para que el tubo '
        'apoye en 30 mm de ancho en lugar de 15 mm.',
        '<b>Atornillar los maleteros entre sí</b> con cuatro tornillos pasantes de unión de módulos (M6 con casquillo) '
        'por costado común, cerca de las esquinas, y <b>fijar el PTR</b> a las torres y a los maleteros con pijas a '
        f'cada 150 mm como máximo (la más cargada recibe {fij[REC][0]["por_pija"]:.0f} N en el estado último, '
        f'{fij[REC][0]["u"]:.0%} de su capacidad adoptada).',
        '<b>Anclar al muro</b>: dos taquetes en la parte alta trasera de cada torre y dos por maletero, con capacidad '
        'de diseño en tracción no menor que las fuerzas de la sección 6.9. El anclaje también es necesario para '
        'limitar el desplome en servicio.',
        f'<b>Si no se coloca el relleno</b>, no basta con atornillar más: las uniones del tablero trasero necesitarían '
        f'confirmat a cada {s_rec} mm o menos y aun así la flecha y el pandeo de laterales no cumplen.',
        '<b>Repisas</b>: con contenidos pesados permanentes conviene un apoyo intermedio a media profundidad bajo el '
        'piso de cada maletero y un refuerzo frontal en los entrepaños de torre, para limitar la flecha diferida.',
    ])
    H += [p('8. Supuestos que conviene confirmar', 'h1')]
    H += lista([
        f'Calibre del tubo de {B:.0f} x {B:.0f} mm: se usó cal. 16 (1.52 mm) como base y se revisaron cal. 18 y cal. 14. '
        'Grado del acero: se adoptó F<sub>y</sub> = 250 MPa.',
        f'Posición de los PTR (a paño frontal y trasero, longitud completa de 2880 mm) y que los maleteros se elevan '
        f'{B:.0f} mm sobre las torres. La altura total pasa de 2440 a {2440 + B:.0f} mm. El archivo incluye un elemento de '
        'referencia de 2480 mm de altura detrás del mueble que podría ser el muro o el plafón del nicho: la holgura '
        f'quedaría en unos {2480 - 2440 - B:.0f} mm.',
        'Tipo y capacidad de los tornillos de unión entre maleteros y de las pijas del PTR: se usaron las capacidades '
        'adoptadas del confirmat.',
        'Calidad del tablero y del conector: los valores de resistencia son adoptados para melamina de partículas '
        'de uso interior y deben confirmarse con el proveedor.',
        'Existencia de la barra de colgar en el hueco central: se incluyó en todas las combinaciones, del lado '
        'conservador para resistencia y anclaje.',
        'Coeficiente horizontal para anclaje (0.5); debe ajustarse al sitio con la normativa local aplicable.',
    ])
    H += [p('9. Reproducibilidad', 'h1'),
          p('Todo el cálculo está en el repositorio: <i>herramientas/skp_lector.py</i> extrae la geometría del .skp, '
            '<i>modelo/modelo_fe.py</i> arma el modelo, <i>modelo/ejecutar.py</i> corre variantes y combinaciones, '
            '<i>modelo/verificaciones.py</i> hace las revisiones, <i>modelo/pandeo.py</i> el análisis no lineal y '
            '<i>modelo/figuras.py</i> y <i>modelo/memoria.py</i> generan figuras y este documento. El perfil se define '
            'en <i>modelo/parametros.py</i>. Resultados numéricos completos en <i>resultados/resultados.json</i> y '
            '<i>resultados/verificaciones.json</i>.')]

    doc = SimpleDocTemplate(SALIDA, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.8 * cm,
                            bottomMargin=1.8 * cm, title=f'Memoria de cálculo: closet con PTR {B:.0f}x{B:.0f} mm',
                            author='Cálculo estructural con modelo FE')
    doc.build(H, onFirstPage=pie_pagina, onLaterPages=pie_pagina)
    print(SALIDA)


if __name__ == '__main__':
    main()
