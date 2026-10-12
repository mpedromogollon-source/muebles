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
    return dict(perfil=perfil, B=B, t=t, t_nom=t_nom, A=s['A'], I=s['I'], S=s['S'], Z=s['Z'], masa=s['masa_kg_m'],
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
    cap = resistencia_ptr(res[variante]['perfil'])
    combos = res[variante]['combos']
    filas = []
    for c in ('ELU-A1 1.2G+1.6Q', 'ELU-A2 1.4G'):
        if c not in combos:
            continue
        r = combos[c]
        Mu, Vu = max_ptr(r)
        Rext = max(v.get('lateral exterior', 0.0) for v in r['apoyos_ptr'].values())
        Rint = max(v.get('lateral aire', 0.0) for v in r['apoyos_ptr'].values())
        filas.append(dict(combo=c, Mu=Mu, Vu=Vu, Ru_ext=Rext, Ru_int=Rint, u_M=Mu / cap['phiMn'],
                          u_V=Vu / cap['phiVn'], u_R=max(Rext / cap['phiRn_ext'], Rint / cap['phiRn_int'])))
    return cap, filas


def flecha_largo_plazo(res, base, lp, clave):
    """u_fin = u(E_fin; G+psi2 Q) + [u(E; G+Q) - u(E; G+psi2 Q)]."""
    a = res[lp]['combos']['ELS G+0.8Q']
    b = res[base]['combos']['ELS G+Q']
    c = res[base]['combos']['ELS G+0.8Q']
    return clave(a) + clave(b) - clave(c)


def flechas_ptr(res, base, lp):
    out = {}
    for ptr in ('frente', 'fondo'):
        f = lambda r: -r['ptr_flecha_rel'][ptr][0]  # noqa: E731
        inst = f(res[base]['combos']['ELS G+Q'])
        fin = flecha_largo_plazo(res, base, lp, f)
        out[ptr] = dict(inst=inst, fin=fin, L=L_PTR_EXT, lim=L_PTR_EXT / LIM_PTR,
                        L_sobre_inst=L_PTR_EXT / max(inst, 1e-9), L_sobre_fin=L_PTR_EXT / max(fin, 1e-9))
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


def apoyo_tableros(res, variante, combo='ELU-T1 1.35G+1.5Q'):
    """Compresion de canto bajo el PTR con el ancho real de contacto (solape en y)."""
    T = P.TABLERO
    fc_d = T['kmod_largo'] * T['fc_k'] / T['gamma_M']
    r = res[variante]['combos'][combo]
    huellas = P.huellas_ptr(res[variante]['B'])
    rangos = _rango_y_piezas()
    out = []
    for clave, v in sorted(r['apoyos_ptr'].items()):
        if 'der' in clave:
            continue
        ptr = clave.split('|')[0]
        y0, y1 = huellas[ptr]
        for elem, R in v.items():
            if elem == 'travesano superior':
                continue
            if elem == 'trasero 15 mm':
                ancho, largo = T['espesor'], 605.0
            else:
                a, b = rangos[elem]
                ancho, largo = min(b, y1) - max(a, y0), T['espesor']
            area = ancho * largo
            out.append(dict(apoyo=f'{clave.replace("|", ", ")}: {elem}', R=R, ancho=ancho, sigma=R / area, fc_d=fc_d,
                            u=R / area / fc_d))
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
def centro_masa():
    """Centro de masa de G + psi2 Q (mm), con piezas del SKP y cargas adoptadas."""
    datos = json.load(open(os.path.join(RAIZ, 'datos', 'piezas_closet.json'), encoding='utf-8'))
    w = P.peso_tablero_N_mm2()
    psi2 = P.TABLERO['psi2_almacen']
    W = []
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
    return float(cm[1]), float(cm[2])


def volteo(res):
    r = res['sismo con anclajes']['combos']['SISMO G+0.8Q+H']
    W = r['reac_base'][2]
    H = P.CARGAS['c_sismico'] * W
    anclas = [dict(xyz=r['anclas_xyz'][n], F=abs(f[1])) for n, f in r['anclas'].items()]
    # sin anclaje: momento de volteo respecto al canto frontal del zocalo (y = -47.7)
    y_cm, z_cm = centro_masa()
    y_cm = y_cm - (-47.7)
    M_volteo = H * z_cm
    M_estab = W * y_cm
    return dict(W=W, H=H, y_cm=y_cm, z_cm=z_cm, M_volteo=M_volteo, M_estab=M_estab, FS=M_estab / M_volteo,
                c_limite=y_cm / z_cm, anclas=anclas, R_base_h=r['reac_base'][1])


def comprobacion_manual(res, perfil=P.PERFIL_BASE):
    """PTR frontal como viga simple de 2865 mm con la carga de maleteros repartida (cota superior)."""
    s = ptr_cuadrado(*P.perfil_diseno(perfil))
    out = {}
    for c in ('ELS G+Q', 'ELU-A1 1.2G+1.6Q'):
        r = res['base']['combos'][c]
        W = sum(v for k, v in r['contactos'].items() if k.startswith('frente|maletero'))
        L = L_PTR_EXT
        M = W * L / 8
        d = 5 * W * L ** 3 / (384 * P.ACERO['E'] * s['I'])
        Mfe = max(abs(x) for x in r['ptr']['frente']['M'])
        dfe = -r['ptr_flecha_rel']['frente'][0]
        out[c] = dict(W=W, M_manual=M, M_fe=Mfe, flecha_manual=d, flecha_fe=dfe)
    return out


def verificar_tornillos(res, variante, combo='ELU-T1 1.35G+1.5Q'):
    """Tornillos de union entre maleteros contiguos (4 por costado comun)."""
    r = res[variante]['combos'].get(combo)
    if not r or not r['tornillos_maleteros']['n']:
        return None
    T = P.TABLERO
    kmod = T['kmod_largo']
    Fv_d = kmod * P.CONFIRMAT['Fv_k'] / T['gamma_M']
    Fax_d = kmod * P.CONFIRMAT['Fax_k'] / T['gamma_M']
    tm = r['tornillos_maleteros']
    return dict(n=tm['n'], axial=tm['axial_max'], corte=tm['corte_max'], Fv_d=Fv_d, Fax_d=Fax_d,
                u=math.hypot(tm['axial_max'] / Fax_d, tm['corte_max'] / Fv_d))


def main():
    with open(os.path.join(RES, 'resultados.pkl'), 'rb') as f:
        res = pickle.load(f)
    hay = lambda vs: tuple(v for v in vs if v in res)  # noqa: E731
    completas = hay(VARS + VARS_EXTRA)             # variantes con todas las combinaciones
    con_lp = hay(VARS + VARS_PERFIL + VARS_EXTRA)
    V = {}
    V['perfil_base'] = P.PERFIL_BASE
    V['manual'] = comprobacion_manual(res)
    V['ptr'] = {}
    for var in hay(VARS + VARS_PERFIL + VARS_EXTRA + ('uniones rigidas',)):
        cap, filas = verificar_ptr(res, var)
        V['ptr'][var] = dict(capacidad=cap, filas=filas)
    V['flechas_ptr'] = {v: flechas_ptr(res, v, v + ' largo plazo') for v in con_lp if v + ' largo plazo' in res}
    for var in hay(('uniones rigidas',)):
        r = res[var]['combos']['ELS G+Q']
        V['flechas_ptr'][var] = {k: dict(inst=-r['ptr_flecha_rel'][k][0], L=L_PTR_EXT) for k in r['ptr']}
    V['flechas_repisas'] = {v: flechas_repisas(res, v, v + ' largo plazo') for v in completas
                            if v + ' largo plazo' in res}
    V['apoyo_tableros'] = {v: apoyo_tableros(res, v) for v in completas}
    V['uniones'] = {}
    for v in completas:
        filas, cd = verificar_uniones(res, v)
        V['uniones'][v] = dict(filas=filas, conector=cd)
    V['tornillos'] = {v: verificar_tornillos(res, v) for v in completas}
    V['tableros'] = {}
    for v in completas:
        for c in ('ELU-T1 1.35G+1.5Q', 'ELU-T2 1.35G'):
            tb, f = resumen_tableros(res, v, c)
            V['tableros'][f'{v}|{c}'] = dict(filas=tb, f=f)
    V['volteo'] = volteo(res)
    V['reparto_apoyos'] = {}
    for v in hay(VARS + VARS_PERFIL + VARS_EXTRA + ('uniones rigidas',)):
        V['reparto_apoyos'][v] = res[v]['combos']['ELS G+Q']['apoyos_ptr']
    V['desplome'] = {}
    for v in completas:
        r = res[v]['combos']['ELS G+Q']
        if 'desplome_maleteros' in r:
            V['desplome'][v] = dict(uy_max=r['desplome_maleteros'])
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
