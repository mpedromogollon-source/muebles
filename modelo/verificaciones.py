"""Verificaciones de diseno a partir de los resultados del modelo FE.

    python modelo/verificaciones.py      (requiere resultados/resultados.pkl)
"""
import json
import math
import os
import pickle
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402
from perfiles import ptr_cuadrado  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(RAIZ, 'resultados')
L_PTR_EXT = 7672.7 - 4807.5          # claro entre laterales exteriores
L_PTR_INT = 7067.7 - 5412.4          # claro entre laterales aire
LIM_PTR = 300                        # L/300
LIM_REPISA = 200                     # L/200 largo plazo
VARS = ('base', 'relleno', 'relleno y entrepano')
VARS_PERFIL = ('30x30 cal. 18', '30x30 cal. 14', 'PTR 3x3 pulg')
VARS_EXTRA = ('sin tornillos entre maleteros', 'relleno sin tornillos entre maleteros', 'relleno y entrepano cal. 18')
VARS_PIJAS = ('relleno y entrepano pijas', 'relleno y entrepano cal. 18 pijas', 'relleno y entrepano cal. 14 pijas',
              'relleno y entrepano pijas a 75 mm', 'relleno y entrepano kser a 150 mm', 'relleno y entrepano kser a 75 mm',
              'relleno y entrepano cal. 14 kser a 150 mm', 'relleno y entrepano cal. 14 kser a 75 mm')


# ------------------------------------------------------------------ PTR, AISC 360-16 LRFD
def resistencia_ptr(perfil):
    """Resistencias AISC 360-16 con espesor de diseno (B4.2).

    El radio de esquina real no se conoce, asi que se usan los valores que AISC prescribe para
    ese caso: ancho plano b = h = B - 3t (B4.1b) y k = 1.5t. Las propiedades geometricas se
    integran con radio exterior 2t.
    """
    E, Fy = P.ACERO['E'], P.ACERO['Fy']
    B, t = P.perfil_diseno(perfil)
    t_nom = P.PERFILES[perfil][1]
    s = ptr_cuadrado(B, t)
    b = B - 3 * t                     # ancho plano de calculo (AISC B4.1b)
    lam = b / t
    lp_f, lr_f = 1.12 * math.sqrt(E / Fy), 1.40 * math.sqrt(E / Fy)
    lp_w = 2.42 * math.sqrt(E / Fy)
    Mp = Fy * s['Z']
    if lam <= lp_f:
        clase, Mn = 'compacto', Mp
    elif lam <= lr_f:
        clase = 'no compacto'
        Mn = min(Mp, Mp - (Mp - Fy * s['S']) * (3.57 * lam * math.sqrt(Fy / E) - 4.0))   # F7-2
    else:
        clase = 'esbelto'
        be = min(b, 1.92 * t * math.sqrt(E / Fy) * (1 - 0.38 / lam * math.sqrt(E / Fy)))   # F7-4
        # modulo efectivo: se descuenta el ancho no efectivo del patin comprimido
        A, I = s['A'], s['I']
        dA = (b - be) * t
        yc = (B - t) / 2
        ybar = -dA * yc / (A - dA)
        Ie = I + A * ybar ** 2 - dA * (yc - ybar) ** 2
        Se = Ie / (B / 2 + abs(ybar))
        Mn = Fy * Se                                                                       # F7-3
    h = B - 3 * t
    kv = 5.0
    if h / t <= 1.10 * math.sqrt(kv * E / Fy):                                              # G2-9
        Cv2 = 1.0
    elif h / t <= 1.37 * math.sqrt(kv * E / Fy):                                            # G2-10
        Cv2 = 1.10 * math.sqrt(kv * E / Fy) / (h / t)
    else:                                                                                    # G2-11
        Cv2 = 1.51 * kv * E / ((h / t) ** 2 * Fy)
    Vn = 0.6 * Fy * (2 * h * t) * Cv2                                                       # G4
    k = 1.5 * t
    lb = P.TABLERO['espesor']
    Rn_fluencia_ext = 2 * Fy * t * (2.5 * k + lb)                                          # J10-3
    Rn_fluencia_int = 2 * Fy * t * (5 * k + lb)                                            # J10-2
    if lb / B <= 0.2:
        Rn_aplast_ext = 2 * 0.40 * t ** 2 * (1 + 3 * (lb / B)) * math.sqrt(E * Fy)          # J10-5a
    else:
        Rn_aplast_ext = 2 * 0.40 * t ** 2 * (1 + (4 * lb / B - 0.2)) * math.sqrt(E * Fy)    # J10-5b
    Rn_aplast_int = 2 * 0.80 * t ** 2 * (1 + 3 * (lb / B)) * math.sqrt(E * Fy)              # J10-4
    return dict(perfil=perfil, B=B, t=t, t_nom=t_nom, A=s['A'], I=s['I'], S=s['S'], Z=s['Z'],
                masa=ptr_cuadrado(B, t_nom)['masa_kg_m'],
                b_t=lam, lp_f=lp_f, lr_f=lr_f, h_t=h / t, lp_w=lp_w, clase=clase,
                phiMn=0.9 * Mn, phiVn=0.9 * Vn,
                phiRn_ext=min(1.0 * Rn_fluencia_ext, 0.75 * Rn_aplast_ext),
                criterio_bh='b = h = B - 3t y k = 1.5t (radio de esquina no conocido, AISC B4.1b y J10)',
                phiRn_int=min(1.0 * Rn_fluencia_int, 0.75 * Rn_aplast_int))


def max_ptr(r):
    Mu = max(max(np.abs(d['M'])) for d in r['ptr'].values())
    Vu = max(max(np.abs(d['V'])) for d in r['ptr'].values())
    return Mu, Vu


def verificar_ptr(res, variante):
    """Filas por combinacion, con la rigidez instantanea y, si existe, con la final (EN 1995 2.3.2.2).
    La primera fila es la que gobierna la flexion."""
    cap = resistencia_ptr(res[variante]['perfil'])
    filas = []
    for var, rig in ((variante, 'instantánea'), (variante + ' rigidez final', 'final')):
        if var not in res:
            continue
        combos = res[var]['combos']
        for c in ('ELU-A1 1.2G+1.6Q', 'ELU-A2 1.4G'):
            if c not in combos:
                continue
            r = combos[c]
            Mu, Vu = max_ptr(r)
            Rext = max(v.get('lateral exterior', 0.0) for v in r['apoyos_ptr'].values())
            Rint = max(v.get('lateral aire', 0.0) for v in r['apoyos_ptr'].values())
            # flexion con axial, AISC H1-1: el tubo esta fijado a los tableros a cada 150 mm o menos, asi que su
            # esbeltez a compresion es despreciable y Pc = 0.9 Fy A en traccion y en compresion
            Nu = max((max(np.abs(d['N'])) for d in r['ptr'].values() if 'N' in d), default=0.0)
            Pc = 0.9 * P.ACERO['Fy'] * cap['A']
            pr = Nu / Pc
            u_H1 = pr + 8 / 9 * Mu / cap['phiMn'] if pr >= 0.2 else pr / 2 + Mu / cap['phiMn']
            filas.append(dict(combo=c, rigidez=rig, Mu=Mu, Vu=Vu, Nu=Nu, Ru_ext=Rext, Ru_int=Rint,
                              u_M=Mu / cap['phiMn'], u_H1=u_H1,
                              u_V=Vu / cap['phiVn'], u_R=max(Rext / cap['phiRn_ext'], Rint / cap['phiRn_int'])))
    filas.sort(key=lambda f: -f['u_H1'])
    return cap, filas


def flecha_largo_plazo(res, base, lp, clave):
    """u_fin = u(E_fin; G+psi2 Q) + [u(E; G+Q) - u(E; G+psi2 Q)]."""
    a = res[lp]['combos']['ELS G+0.8Q']
    b = res[base]['combos']['ELS G+Q']
    c = res[base]['combos']['ELS G+0.8Q']
    return clave(a) + clave(b) - clave(c)


def flechas_ptr(res, base, lp):
    """Flecha de cada PTR respecto a dos cuerdas: entre laterales exteriores (L = 2865 mm) y entre laterales
    aire (tramo central, L = 1655 mm). Las claves de primer nivel son las del tramo que gobierna."""
    out = {}
    for ptr in ('frente', 'fondo'):
        tramos = {}
        for tramo, clave, L in (('exterior', 'ptr_flecha_rel', L_PTR_EXT), ('central', 'ptr_flecha_rel_central', L_PTR_INT)):
            f = lambda r: -r[clave][ptr][0]  # noqa: E731
            inst = f(res[base]['combos']['ELS G+Q'])
            fin = flecha_largo_plazo(res, base, lp, f)
            tramos[tramo] = dict(tramo=tramo, inst=inst, fin=fin, L=L, lim=L / LIM_PTR,
                                 L_sobre_inst=L / max(inst, 1e-9), L_sobre_fin=L / max(fin, 1e-9))
        gob = max(tramos.values(), key=lambda d: d['fin'] / d['lim'])
        out[ptr] = dict(gob, tramos=tramos)
    return out


def flechas_repisas(res, base, lp):
    def tabla(r):
        return {d['tablero']: (-d['flecha'], d['claro']) for d in r['flechas_tableros']}
    a = tabla(res[lp]['combos']['ELS G+0.8Q'])
    b = tabla(res[base]['combos']['ELS G+Q'])
    c = tabla(res[base]['combos']['ELS G+0.8Q'])
    out = []
    for k in b:
        if 'der' in k or 'maletero 3' in k or 'maletero 1' in k:
            continue                 # simetria: se reporta una torre y el maletero central + extremo
        fin = a[k][0] + b[k][0] - c[k][0]
        L = b[k][1]
        out.append(dict(tablero=k, inst=b[k][0], fin=fin, L=L, lim=L / LIM_REPISA, u=fin / (L / LIM_REPISA)))
    return out


# ------------------------------------------------------------------ apoyo PTR sobre tableros
def _rango_y_piezas():
    """Rango en y de los cantos que reciben al PTR, tomado de la geometria del SKP."""
    datos = json.load(open(os.path.join(RAIZ, 'datos', 'piezas_closet.json'), encoding='utf-8'))
    rangos = {}
    for clave, pref in (('lateral exterior', 'ESPCL-LD'), ('lateral aire', 'lateral aire')):
        pz = next(p for p in datos['piezas'] if p['nombre'].startswith(pref))
        rangos[clave] = (pz['min'][1], pz['max'][1])
    return rangos


X_LATERAL_AIRE_IZQ = 5412.4          # plano medio del lateral aire de la torre izquierda
LARGO_ESQUINA = 30.0                 # largo de canto del trasero que se asigna al apoyo en la esquina


def apoyo_tableros(res, variante, combo='ELU-T1 1.35G+1.5Q'):
    """Compresion de canto bajo el PTR (torre izquierda). La reaccion de cada tablero es la suma de sus fuerzas
    de contacto por nodo y se reparte uniforme en el area de contacto.

    Laterales: 15 mm por el solape en y con la huella del tubo.
    PTR trasero: el tubo se arquea sobre la torre y apoya casi todo en la esquina del lateral aire con el
    trasero, asi que se revisa la esquina en conjunto (lateral aire, 15 x 15 mm, y trasero en 30 mm de largo).
    Con suplemento de canto (tablero de 15 mm atornillado a la cara del lateral aire que da al hueco central, a ras
    de su canto superior) el ancho en x del lateral aire pasa de 15 a 30 mm. La parte de la reaccion que toma el
    suplemento pasa al lateral aire por tornillos pasantes M6, que se cuentan por extremo.
    """
    T = P.TABLERO
    e = T['espesor']
    fc_d = T['kmod_largo'] * T['fc_k'] / T['gamma_M']
    r = res[variante]['combos'][combo]
    huellas = P.huellas_ptr(res[variante]['B'])
    rangos = _rango_y_piezas()
    nodos = [c for c in r['contactos_nodo'] if c['grupo'] == 'torre izq']
    out = []
    Fv_M6 = T['kmod_largo'] * P.johansen_tablero_tablero(6.0, e, e, 400.0) / T['gamma_M']

    def fila(apoyo, R, area, area_sup, R_sup=0.0):
        out.append(dict(apoyo=apoyo, R=R, area=area, sigma=R / area, fc_d=fc_d, u=R / area / fc_d,
                        u_suplemento=R / area_sup / fc_d, R_suplemento=R_sup,
                        n_M6=math.ceil(R_sup / Fv_M6) if R_sup > 0 else 0, Fv_M6=Fv_M6))

    for ptr in ('frente', 'fondo'):
        y0, y1 = huellas[ptr]
        Rp = {}
        for c in nodos:
            if c['ptr'] != ptr:
                continue
            k = ('lateral exterior' if c['tablero'].startswith('ESPCL-LD') else
                 'lateral aire' if c['tablero'].startswith('lateral aire') else
                 'trasero 15 mm' if c['tablero'].startswith('fondo') else 'otro')
            Rp.setdefault(k, []).append(c)
        for k in ('lateral exterior', 'lateral aire'):
            R = sum(c['F'][2] for c in Rp.get(k, []))
            if R <= 0:
                continue
            a, b = rangos[k]
            solape = min(b, y1) - max(a, y0)
            sup = 2 if k == 'lateral aire' else 1
            if ptr == 'fondo' and k == 'lateral aire':
                continue                       # se revisa en la esquina
            fila(f'{ptr}: {k}', R, e * solape, sup * e * solape, R / 2 if sup == 2 else 0.0)
        tr = Rp.get('trasero 15 mm', [])
        if ptr == 'fondo' and (tr or Rp.get('lateral aire')):
            R_la = sum(c['F'][2] for c in Rp.get('lateral aire', []))
            R_tr_esq = sum(c['F'][2] for c in tr if abs(c['x'] - X_LATERAL_AIRE_IZQ) <= LARGO_ESQUINA)
            R_tr_tot = sum(c['F'][2] for c in tr)
            a, b = rangos['lateral aire']
            solape = min(b, y1) - max(a, y0)
            area = e * solape + e * LARGO_ESQUINA
            fila('fondo: esquina lateral aire y trasero', R_la + R_tr_esq, area, area + e * solape,
                 (R_la + R_tr_esq) * e * solape / (area + e * solape))
            out[-1].update(R_lateral_aire=R_la, R_trasero_esquina=R_tr_esq, R_trasero_total=R_tr_tot)
            resto = R_tr_tot - R_tr_esq
            if resto > 0:
                fila('fondo: trasero 15 mm fuera de la esquina', resto, e * (605.0 - 2 * LARGO_ESQUINA),
                     e * (605.0 - 2 * LARGO_ESQUINA))
    return out


# ------------------------------------------------------------------ uniones
def n_tipico(L, s=200.0, borde=50.0):
    return max(2, math.ceil((L - 2 * borde) / s) + 1)


def verificar_uniones(res, variante, combo='ELU-T1 1.35G+1.5Q', n=12):
    r = res[variante]['combos'][combo]
    cd = r['conector_diseno']
    filas = []
    for u in r['uniones']:
        if 'der' in u['grupo'] or u['grupo'] in ('maletero 3',):
            continue
        dem = 1.25 * math.hypot(u['traccion'] / cd['Fax_d'], u['cortante'] / cd['Fv_d'])
        n_req = max(2, math.ceil(dem))
        nt = n_tipico(u['L'])
        filas.append(dict(union=f"{u['canto']} contra {u['cara']}", L=u['L'], T=u['traccion'], V=u['cortante'],
                          C=u['compresion'], dem=dem, n_req=n_req, n_tip=nt, u=dem / nt, s_local=u['s_max'],
                          cumple=n_req <= nt))
    filas.sort(key=lambda d: -d['u'])
    return filas[:n], cd


def resumen_tableros(res, variante, combo, n=8):
    r = res[variante]['combos'][combo]
    vistos, out = set(), []
    for t in r['tableros']:
        nom = t['tablero'].split(' (')[0]
        if nom in vistos:
            continue
        vistos.add(nom)
        out.append(t)
        if len(out) >= n:
            break
    return out, r['resistencias_diseno']


# ------------------------------------------------------------------ volteo y anclaje
def centro_masa(psi2=P.TABLERO['psi2_almacen']):
    """Peso y centro de masa (y, z en mm) de G + psi2 Q, con piezas del SKP y cargas adoptadas."""
    datos = json.load(open(os.path.join(RAIZ, 'datos', 'piezas_closet.json'), encoding='utf-8'))
    w = P.peso_tablero_N_mm2()
    W = []
    if psi2:
        L_barra = 7060.2 - 5419.9
        W.append((psi2 * P.CARGAS['q_barra'] * L_barra, np.array([0.5 * (7060.2 + 5419.9), 187.0, P.CARGAS['z_barra']])))
    for pz in datos['piezas']:
        if pz['nombre'].startswith(('Componente#4', 'Componente#9', 'GP-RSMLC')):
            continue
        lo, hi = np.array(pz['min']), np.array(pz['max'])
        dz = P.LADO_BASE if lo[2] >= P.Z_TOPE_TORRES - 1 else 0.0
        d = np.sort(hi - lo)
        c = 0.5 * (lo + hi) + np.array([0, 0, dz])
        W.append((w * d[1] * d[2], c))
        q = 0.0
        if pz['nombre'] == 'MALEST-MA':
            q = P.CARGAS['q_maletero']
        elif pz['nombre'].startswith(('REPIZA@1#9', 'PTRSOP024-TO')):
            q = P.CARGAS['q_repisa_torre']
        if q:
            W.append((psi2 * q * d[1] * d[2], c))
        if pz['nombre'].startswith('GH-FRENTE'):
            W.append((psi2 * P.CARGAS['q_cajon_kg'] * P.GRAV, c + np.array([0, 290.0, 0])))
    m = sum(a for a, _ in W)
    cm = sum(a * c for a, c in W) / m
    return float(m), float(cm[1]), float(cm[2])


Y_PIVOTE = -55.2     # cara frontal del zocalo


def volteo(res):
    """Volteo sin anclaje (cargado con G + psi2 Q y vacio) y fuerzas en anclajes con G + psi2 Q + H."""
    r = res['sismo con anclajes']['combos']['SISMO G+0.8Q+H']
    W = r['reac_base'][2]
    H = P.CARGAS['c_sismico'] * W
    anclas = [dict(xyz=r['anclas_xyz'][n], F=abs(f[1])) for n, f in r['anclas'].items()]
    casos = {}
    for nombre, psi2 in (('cargado', P.TABLERO['psi2_almacen']), ('vacio', 0.0)):
        Wc, y_cm, z_cm = centro_masa(psi2)
        brazo = y_cm - Y_PIVOTE
        casos[nombre] = dict(W=Wc, y_cm=y_cm, z_cm=z_cm, brazo=brazo, c_limite=brazo / z_cm)
    c = casos['cargado']
    M_volteo = H * c['z_cm']
    M_estab = W * c['brazo']
    return dict(W=W, H=H, y_cm=c['brazo'], z_cm=c['z_cm'], M_volteo=M_volteo, M_estab=M_estab, FS=M_estab / M_volteo,
                c_limite=min(d['c_limite'] for d in casos.values()), casos=casos, anclas=anclas,
                R_base_h=r['reac_base'][1])


APOYOS_X = (4807.5, 5412.4, 7067.7, 7672.7)   # laterales exterior y aire de cada torre


def viga_continua(w, EI, apoyos=APOYOS_X, x0=4800.0, x1=7680.0, n=576):
    """Viga Euler-Bernoulli con carga uniforme w (N/mm) y apoyos rigidos: (M max, flecha max del tramo central)."""
    x = np.linspace(x0, x1, n + 1)
    for a in apoyos:
        x[np.argmin(abs(x - a))] = a
    K = np.zeros((2 * n + 2, 2 * n + 2))
    F = np.zeros(2 * n + 2)
    for i in range(n):
        L = x[i + 1] - x[i]
        k = EI / L ** 3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                    [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]])
        idx = [2 * i, 2 * i + 1, 2 * i + 2, 2 * i + 3]
        K[np.ix_(idx, idx)] += k
        F[idx] += -w * np.array([L / 2, L * L / 12, L / 2, -L * L / 12])
    fijos = [2 * int(np.argmin(abs(x - a))) for a in apoyos]
    libres = [i for i in range(2 * n + 2) if i not in fijos]
    u = np.zeros(2 * n + 2)
    u[libres] = np.linalg.solve(K[np.ix_(libres, libres)], F[libres])
    v = u[0::2]
    M = []
    for i in range(n):
        L = x[i + 1] - x[i]
        th1, th2 = u[2 * i + 1], u[2 * i + 3]
        M.append(abs(EI / L ** 2 * (-6 * v[i] - 4 * L * th1 + 6 * v[i + 1] - 2 * L * th2)
                     + w * L * L / 12))
        M.append(abs(EI / L ** 2 * (6 * v[i] + 2 * L * th1 - 6 * v[i + 1] + 4 * L * th2) + w * L * L / 12))
    sel = (x >= apoyos[1]) & (x <= apoyos[2])
    return max(M), float(-v[sel].min())


def comprobacion_manual(res, perfil=P.PERFIL_BASE):
    """PTR frontal con la carga que le dan los maleteros, repartida: (a) viga simple de 2865 mm entre laterales
    exteriores, sin apoyo en los laterales aire; (b) viga continua sobre los cuatro laterales con apoyos rigidos."""
    s = ptr_cuadrado(*P.perfil_diseno(perfil))
    EI = P.ACERO['E'] * s['I']
    out = {}
    for c in ('ELS G+Q', 'ELU-A1 1.2G+1.6Q'):
        r = res['base']['combos'][c]
        W = sum(v for k, v in r['contactos'].items() if k.startswith('frente|maletero'))
        L = L_PTR_EXT
        M = W * L / 8
        d = 5 * W * L ** 3 / (384 * EI)
        Mc, dc = viga_continua(W / (P.PTR_X[1] - P.PTR_X[0]), EI)
        Mfe = max(abs(x) for x in r['ptr']['frente']['M'])
        dfe = -r['ptr_flecha_rel']['frente'][0]
        out[c] = dict(W=W, M_manual=M, M_fe=Mfe, flecha_manual=d, flecha_fe=dfe, M_continua=Mc, flecha_continua=dc,
                      flecha_fe_central=-r['ptr_flecha_rel_central']['frente'][0])
    return out


def verificar_tornillos(res, variante, combo='ELU-T1 1.35G+1.5Q'):
    """Tornillos de union entre maleteros contiguos (4 por costado comun)."""
    r = res[variante]['combos'].get(combo)
    if not r or not r['tornillos_maleteros']['n']:
        return None
    T = P.TABLERO
    kmod = T['kmod_largo']
    M6 = P.TORNILLO_M6
    Fv_d = kmod * P.johansen_tablero_tablero(M6['d'], M6['t'], M6['t'], M6['fu']) / T['gamma_M']
    Fax_d = kmod * P.CONFIRMAT['Fax_k'] / T['gamma_M']
    tm = r['tornillos_maleteros']
    # interaccion tornillo por tornillo, solo con la traccion (la compresion pasa por contacto entre costados)
    us = [math.hypot(a / Fax_d, v / Fv_d) for a, v in tm['lista']]
    i = int(np.argmax(us))
    return dict(n=tm['n'], axial=tm['axial_max'], corte=tm['corte_max'], Fv_d=Fv_d, Fax_d=Fax_d,
                axial_gob=tm['lista'][i][0], corte_gob=tm['lista'][i][1], u=us[i])


def capacidad_pija():
    """Fv,d de la pija del PTR: placa de acero delgada (pared del tubo) contra tablero de 15 mm, EN 1995 8.2.3."""
    T, pj = P.TABLERO, P.PIJA
    return T['kmod_largo'] * P.johansen_placa_delgada(pj['d'], pj['t'], pj['fu']) / T['gamma_M']


def fijacion_ptr(res, variante, combo='ELU-T1 1.35G+1.5Q', s_pija=150.0):
    """Fuerza horizontal PTR-tablero por maletero o torre y PTR, y fuerza por pija si se reparte a cada s_pija."""
    r = res[variante]['combos'].get(combo)
    if not r or 'contactos_nodo' not in r:
        return None
    grupos = {}
    for c in r['contactos_nodo']:
        grupos.setdefault((c['ptr'], c['grupo']), []).append(c)
    Fv_d = capacidad_pija()
    filas = []
    for (ptr, g), cs in sorted(grupos.items()):
        fh = [math.hypot(c['F'][0], c['F'][1]) for c in cs]
        largo = 960.0 if g.startswith('maletero') else 620.0
        n_pijas = largo / s_pija
        filas.append(dict(ptr=ptr, grupo=g, suma=sum(fh), neto_x=abs(sum(c['F'][0] for c in cs)),
                          por_pija=max(fh) * len(cs) / n_pijas, Fv_d=Fv_d,
                          u=max(fh) * len(cs) / n_pijas / Fv_d))
    filas.sort(key=lambda f: -f['u'])
    return filas


def envolvente(fn, res, v, **kw):
    """fn con la rigidez instantanea y, si existe la variante, con la final; gobierna la de mayor relacion."""
    def umax(x):
        if not x:
            return -1.0
        return x['u'] if isinstance(x, dict) else max(f['u'] for f in x)
    cands = []
    for var, rig in ((v, 'instantánea'), (v + ' rigidez final', 'final')):
        if var in res and 'ELU-T1 1.35G+1.5Q' in res[var]['combos']:
            x = fn(res, var, **kw)
            if x:
                cands.append((umax(x), rig, x))
    if not cands:
        return None
    u, rig, x = max(cands, key=lambda c: c[0])
    if isinstance(x, dict):
        return dict(x, rigidez=rig)
    return [dict(f, rigidez=rig) for f in x]


def main():
    with open(os.path.join(RES, 'resultados.pkl'), 'rb') as f:
        res = pickle.load(f)
    hay = lambda vs: tuple(v for v in vs if v in res)  # noqa: E731
    completas = hay(VARS + VARS_EXTRA + VARS_PIJAS)   # variantes con todas las combinaciones
    con_lp = hay(VARS + VARS_PERFIL + VARS_EXTRA + VARS_PIJAS)
    V = {}
    V['perfil_base'] = P.PERFIL_BASE
    V['manual'] = comprobacion_manual(res)
    V['ptr'] = {}
    for var in hay(VARS + VARS_PERFIL + VARS_EXTRA + VARS_PIJAS + ('uniones rigidas',)):
        cap, filas = verificar_ptr(res, var)
        V['ptr'][var] = dict(capacidad=cap, filas=filas)
    V['flechas_ptr'] = {v: flechas_ptr(res, v, v + ' largo plazo') for v in con_lp if v + ' largo plazo' in res}
    for var in hay(('uniones rigidas',)):
        r = res[var]['combos']['ELS G+Q']
        V['flechas_ptr'][var] = {k: dict(inst=-r['ptr_flecha_rel'][k][0], L=L_PTR_EXT) for k in r['ptr']}
    V['flechas_repisas'] = {v: flechas_repisas(res, v, v + ' largo plazo') for v in completas
                            if v + ' largo plazo' in res}
    V['apoyo_tableros'] = {v: envolvente(apoyo_tableros, res, v) for v in completas}
    V['uniones'] = {}
    for v in completas:
        cands = [(x, rig) for x, rig in ((v, 'instantánea'), (v + ' rigidez final', 'final'))
                 if x in res and 'ELU-T1 1.35G+1.5Q' in res[x]['combos']]
        mejor = None
        for x, rig in cands:
            filas, cd = verificar_uniones(res, x)
            if mejor is None or max(f['u'] for f in filas) > max(f['u'] for f in mejor['filas']):
                mejor = dict(filas=filas, conector=cd, rigidez=rig)
        V['uniones'][v] = mejor
    V['tornillos'] = {v: envolvente(verificar_tornillos, res, v) for v in completas}
    V['fijacion'] = {v: envolvente(fijacion_ptr, res, v, s_pija=75.0 if '75 mm' in v else 150.0)
                     for v in hay(VARS + VARS_EXTRA + VARS_PIJAS)}
    V['capacidades'] = dict(pija_Fv_d=capacidad_pija(),
                            M6_Fv_d=P.TABLERO['kmod_largo'] * P.johansen_tablero_tablero(6.0, 15.0, 15.0, 400.0)
                            / P.TABLERO['gamma_M'],
                            pija_Kser=P.PIJA['Kser'])
    V['tableros'] = {}
    for v in completas:
        for c in ('ELU-T1 1.35G+1.5Q', 'ELU-T2 1.35G'):
            mejor = None
            for x, rig in ((v, 'instantánea'), (v + ' rigidez final', 'final')):
                if x not in res or c not in res[x]['combos']:
                    continue
                tb, f = resumen_tableros(res, x, c)
                if mejor is None or tb[0]['u'] > mejor['filas'][0]['u']:
                    mejor = dict(filas=tb, f=f, rigidez=rig)
            V['tableros'][f'{v}|{c}'] = mejor
    V['volteo'] = volteo(res)
    V['reparto_apoyos'] = {}
    for v in hay(VARS + VARS_PERFIL + VARS_EXTRA + ('uniones rigidas',)):
        V['reparto_apoyos'][v] = res[v]['combos']['ELS G+Q']['apoyos_ptr']
    V['desplome'] = {}
    for v in completas:
        r = res[v]['combos']['ELS G+Q']
        if 'desplome_maleteros' in r:
            V['desplome'][v] = dict(uy_max=r['desplome_maleteros'])
            if v + ' largo plazo' in res:
                V['desplome'][v]['uy_fin'] = flecha_largo_plazo(res, v, v + ' largo plazo',
                                                                lambda r: r['desplome_maleteros'])
        elif 'campo' in r:
            uy = [abs(u[1]) for p in r['campo']['paneles'] if p['grupo'].startswith('maletero')
                  for q in p['disp'] for u in q]
            V['desplome'][v] = dict(uy_max=max(uy))
    V['peso'] = dict(G=res['base']['combos']['ELU-A2 1.4G']['reac_base'][2] / 1.4,
                     G_Q=res['base']['combos']['ELS G+Q']['reac_base'][2])
    pandeo = os.path.join(RES, 'pandeo.json')
    if os.path.exists(pandeo):
        V['pandeo'] = [{k: v for k, v in d.items() if k != 'campo_final'} for d in json.load(open(pandeo))]
    else:
        import glob
        partes = sorted(glob.glob(os.path.join(RES, 'pandeo_parcial_*.json')))
        if partes:
            V['pandeo'] = [dict(json.load(open(f)), parcial=True) for f in partes]
    with open(os.path.join(RES, 'verificaciones.json'), 'w', encoding='utf-8') as f:
        json.dump(V, f, indent=1, ensure_ascii=False, default=float)
    return V


if __name__ == '__main__':
    V = main()
    for var, d in V['ptr'].items():
        c = d['capacidad']
        print(f"PTR {var}: {c['perfil']} {c['clase']} b/t={c['b_t']:.1f} phiMn={c['phiMn']/1e6:.2f} kN m "
              f"phiVn={c['phiVn']/1e3:.1f} kN phiRn_ext={c['phiRn_ext']/1e3:.1f} kN")
        for f in d['filas']:
            print(f"   {f['combo']}: Mu={f['Mu']/1e6:.3f} u={f['u_M']:.2f}  Vu={f['Vu']:.0f} u={f['u_V']:.2f}  "
                  f"Ru={f['Ru_ext']:.0f} u={f['u_R']:.2f}")
    print(json.dumps(V['flechas_ptr'], indent=1, default=float)[:1500])
    for v, fs in V['flechas_repisas'].items():
        for f in fs:
            print(v, f)
    for v, fs in V['apoyo_tableros'].items():
        for f in fs:
            print(v, f)
    for v, d in V['uniones'].items():
        print(v, d['conector'])
        for f in d['filas']:
            print('  ', {k: (round(x, 1) if isinstance(x, float) else x) for k, x in f.items()})
    for k, d in V['tableros'].items():
        print(k, [(t['tablero'], round(t['u'], 2), round(t['u_pico'], 2)) for t in d['filas']])
    print(V['volteo'])
    print(V['peso'])
