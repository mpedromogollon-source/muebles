"""Casos de carga, combinaciones y posproceso del modelo FE."""
import math
from collections import defaultdict

import numpy as np

import parametros as P
from modelo_fe import Modelo

CASOS = ['G', 'Q_maleteros', 'Q_torres', 'Q_barra']
Q_TODAS = ('Q_maleteros', 'Q_torres', 'Q_barra')


def fac(g, q, casos_q=Q_TODAS):
    d = {'G': g}
    d.update({c: q for c in casos_q})
    return d


COMBOS = {
    'ELU-A1 1.2G+1.6Q': fac(1.2, 1.6),
    'ELU-A2 1.4G': fac(1.4, 0.0),
    'ELU-T1 1.35G+1.5Q': fac(1.35, 1.5),
    'ELU-T2 1.35G': fac(1.35, 0.0),
    'ELS G+Q': fac(1.0, 1.0),
    'ELS G+0.8Q': fac(1.0, P.TABLERO['psi2_almacen']),
    'G': fac(1.0, 0.0),
    'SISMO G+0.8Q+H': dict(fac(1.0, P.TABLERO['psi2_almacen'], ('Q_maleteros', 'Q_torres')), H_sismo=1.0),
}
KMOD = {'ELU-T1 1.35G+1.5Q': P.TABLERO['kmod_largo'], 'ELU-T2 1.35G': P.TABLERO['kmod_permanente']}


def resolver_casos(m, casos=CASOS):
    return {c: m.resolver(m.cargas_caso(c)) for c in casos}


def combinar(Rc, factores):
    out = None
    for caso, f in factores.items():
        if f == 0 or caso not in Rc:
            continue
        R = Rc[caso]
        if out is None:
            out = dict(desp={n: f * v for n, v in R['desp'].items()},
                       uniones=[(e, f * v) for e, v in R['uniones']],
                       contactos=[(e, f * v) for e, v in R['contactos']],
                       ptr={k: [f * v for v in vs] for k, vs in R['ptr'].items()},
                       shell={e: f * v for e, v in R['shell'].items()},
                       reac_base=f * R['reac_base'],
                       anclas={n: f * v for n, v in R['anclas'].items()})
        else:
            for n, v in R['desp'].items():
                out['desp'][n] = out['desp'][n] + f * v
            out['uniones'] = [(e, a + f * b) for (e, a), (_, b) in zip(out['uniones'], R['uniones'])]
            out['contactos'] = [(e, a + f * b) for (e, a), (_, b) in zip(out['contactos'], R['contactos'])]
            for k in out['ptr']:
                out['ptr'][k] = [a + f * b for a, b in zip(out['ptr'][k], R['ptr'][k])]
            for e in out['shell']:
                out['shell'][e] = out['shell'][e] + f * R['shell'][e]
            out['reac_base'] = out['reac_base'] + f * R['reac_base']
            for n in out['anclas']:
                out['anclas'][n] = out['anclas'][n] + f * R['anclas'][n]
    return out


# ---------------------------------------------------------------- PTR
def ptr_diagramas(m, R):
    """x, momento (N mm, positivo = tension en fibra inferior), cortante (N), flecha (mm)."""
    out = {}
    for nombre, els in m.ptr_elems.items():
        lf = np.array(R['ptr'][nombre])          # [N, Vy, Vz, T, My, Mz] x 2 extremos
        xs = m.ptr_x
        M = np.zeros(len(xs))
        V = np.zeros(len(xs))
        M[:-1] = lf[:, 4]
        M[-1] = -lf[-1, 10]
        V[:-1] = lf[:, 2]
        V[-1] = -lf[-1, 8]
        uz = np.array([R['desp'][n][2] for n in m.ptr_nodos[nombre]])
        out[nombre] = dict(x=xs, M=M, V=V, uz=uz)
    # convencion: momento positivo en el centro del claro
    for d in out.values():
        i = int(np.argmin(abs(d['x'] - 6240)))
        if d['M'][i] < 0:
            d['M'] = -d['M']
    return out


def flecha_relativa(d, x_apoyos):
    """Flecha maxima medida respecto a la cuerda entre dos apoyos."""
    xa, xb = x_apoyos
    ua, ub = np.interp([xa, xb], d['x'], d['uz'])
    sel = (d['x'] >= xa) & (d['x'] <= xb)
    cuerda = ua + (ub - ua) * (d['x'][sel] - xa) / (xb - xa)
    rel = d['uz'][sel] - cuerda
    i = int(np.argmin(rel))
    return float(rel[i]), float(d['x'][sel][i])


# ---------------------------------------------------------------- contactos
def contactos_resumen(m, R):
    """Fuerza vertical por PTR y por tablero de apoyo (compresion positiva, N)."""
    por_tablero = defaultdict(float)
    por_punto = defaultdict(float)
    for (e, n, it, nombre, x), (_, f) in zip(m.contactos, R['contactos']):
        t = m.tableros[it]
        fz = f[2]   # el orden de nodos del contacto da compresion positiva
        lado = 'maletero' if t.grupo.startswith('maletero') else 'torre'
        por_tablero[(nombre, lado, t.grupo, t.nombre)] += fz
        xy = (nombre, lado, round(m.coord[n][0], 1), round(m.coord[n][1], 1))
        por_punto[xy] += fz
    return por_tablero, por_punto


def apoyos_ptr(m, R):
    """Reaccion de cada torre sobre cada PTR agrupada por elemento de la torre (N)."""
    pt, _ = contactos_resumen(m, R)
    out = defaultdict(dict)
    for (ptr, lado, grupo, nombre), f in pt.items():
        if lado == 'torre':
            clave = 'lateral exterior' if nombre.startswith('ESPCL-LD') else (
                'lateral aire' if nombre.startswith('lateral aire') else (
                    'trasero 15 mm' if nombre.startswith('fondo') else 'travesano superior'))
            out[(ptr, grupo)][clave] = out[(ptr, grupo)].get(clave, 0.0) + f
    return out


# ---------------------------------------------------------------- uniones
def _rol(p, q):
    """True si p atraviesa el plano medio de q (p es la pieza 'de cara')."""
    k = q.a
    return p.lo0[k] < q.c - 1.0 and p.hi0[k] > q.c + 1.0


def uniones_resumen(m, R, kmod):
    """Demanda en cada linea de union y separacion maxima de confirmat.

    El confirmat atraviesa la pieza 'de cara' y entra en el canto de la otra.
    La componente normal se separa en compresion (apoyo directo de canto, sin
    demanda en el conector) y traccion (extraccion del conector).
    """
    Fv_d = kmod * P.CONFIRMAT['Fv_k'] / P.TABLERO['gamma_M']
    Fax_d = kmod * P.CONFIRMAT['Fax_k'] / P.TABLERO['gamma_M']
    t_tab = P.TABLERO['espesor']
    lineas = defaultdict(lambda: dict(L=0.0, traccion=0.0, cortante=0.0, compresion=0.0, q_t=0.0, q_v=0.0,
                                      sigma_apoyo=0.0, s_min=1e9))
    for (e, n0, n1, t0, t1, trib), (_, f) in zip(m.uniones, R['uniones']):
        p, q = m.tableros[t0], m.tableros[t1]
        if p.a == q.a or trib <= 0:
            continue
        ic, ie = (t0, t1) if _rol(p, q) else (t1, t0)
        C, E = m.tableros[ic], m.tableros[ie]
        eje = C.a
        s = math.copysign(1.0, 0.5 * (E.lo0[eje] + E.hi0[eje]) - C.c)
        # f es la fuerza interna en el nodo i = k (u_i - u_j)
        dsep = s * (f[eje] if ie == t0 else -f[eje])   # > 0: las piezas se separan
        ft_, fc_ = max(dsep, 0.0), max(-dsep, 0.0)
        fv = float(np.linalg.norm([f[k] for k in range(3) if k != eje]))
        d = lineas[(ic, ie)]
        d['L'] += trib
        d['traccion'] += ft_
        d['compresion'] += fc_
        d['cortante'] += fv
        qt, qv = ft_ / trib, fv / trib
        d['q_t'] = max(d['q_t'], qt)
        d['q_v'] = max(d['q_v'], qv)
        d['sigma_apoyo'] = max(d['sigma_apoyo'], fc_ / (trib * t_tab))
        u = math.hypot(qt / Fax_d, qv / Fv_d)
        if u > 0:
            d['s_min'] = min(d['s_min'], 1.0 / u)
    out = []
    for (ic, ie), d in lineas.items():
        C, E = m.tableros[ic], m.tableros[ie]
        s_max = min(d['s_min'], 1e4)
        out.append(dict(cara=f'{C.nombre} ({C.grupo})', canto=f'{E.nombre} ({E.grupo})', grupo=C.grupo,
                        L=d['L'], traccion=d['traccion'], compresion=d['compresion'], cortante=d['cortante'],
                        q_t=d['q_t'], q_v=d['q_v'], sigma_apoyo=d['sigma_apoyo'], s_max=s_max,
                        n_req=max(2, math.ceil(d['L'] / min(s_max, d['L'])))))
    out.sort(key=lambda d: d['s_max'])
    return out, Fv_d, Fax_d


# ---------------------------------------------------------------- tableros
def _utilizacion(g, t, f):
    """Indice de esfuerzo en un punto: membrana/resistencia + flexion/fm por direccion."""
    N11, N22, N12, M11, M22, M12 = g[:6]
    u = 0.0
    for N, M in ((N11, M11), (N22, M22)):
        sn = N / t
        u = max(u, abs(sn) / (f['ft'] if sn > 0 else f['fc']) + 6 * abs(M) / t ** 2 / f['fm'])
    return max(u, abs(N12 / t) / f['fv'] + 6 * abs(M12) / t ** 2 / f['fm'])


def tableros_resumen(m, R, kmod, radio=75.0):
    """Indice maximo por tablero: pico (punto de Gauss) y promediado en un radio dado.

    Los picos aparecen en esquinas de lineas de union, donde el modelo concentra
    fuerzas en nodos; el valor promediado es el representativo para diseno.
    """
    import openseespy.opensees as ops
    T = P.TABLERO
    t = T['espesor']
    f = {k: kmod * T[k + '_k'] / T['gamma_M'] for k in ('fm', 'ft', 'fc', 'fv')}
    out = []
    for it, tb in enumerate(m.tableros):
        els = tb.elems
        cen = np.array([np.mean([m.coord[n] for n in ops.eleNodes(e)], axis=0) for e in els])
        S = np.array([R['shell'][e] for e in els])                # (ne, 4, 8)
        pico = np.array([max(_utilizacion(g, t, f) for g in s) for s in S])
        Sm = S.mean(axis=1)                                        # promedio por elemento
        area = np.array([m.elem_area[e] for e in els])
        d = np.linalg.norm(cen[:, None, :] - cen[None, :, :], axis=2)
        W = (d <= radio) * area[None, :]
        Sprom = (W @ Sm) / W.sum(axis=1, keepdims=True)
        prom = np.array([_utilizacion(g, t, f) for g in Sprom])
        i, j = int(np.argmax(pico)), int(np.argmax(prom))
        out.append(dict(tablero=f'{tb.nombre} ({tb.grupo})', u_pico=float(pico[i]), u=float(prom[j]),
                        donde=cen[j].round(0).tolist(), elem=int(els[j])))
    out.sort(key=lambda d: -d['u'])
    return out, f


def flechas_tableros(m, R):
    """Flecha relativa de pisos de maletero, cubierta de cajones y entrepano de torres (mm)."""
    out = []
    for tb in m.tableros:
        if tb.a != 2:
            continue
        uz = {tuple(np.round(m.coord[n], 1)): R['desp'][n][2] for n in tb.nodos.values()}
        if tb.nombre == 'MALEST-MA':
            # entre las lineas de apoyo de los dos PTR
            yf, yb = sum(P.PTR_Y_FRENTE) / 2, sum(P.PTR_Y_FONDO) / 2
            best, claro = 0.0, yb - yf
            for x in tb.gb:
                col = {round(k[1], 1): v for k, v in uz.items() if abs(k[0] - x) < 0.1}
                ys = np.array(sorted(col))
                vs = np.array([col[y] for y in ys])
                uf, ub = np.interp([yf, yb], ys, vs)
                sel = (ys > yf) & (ys < yb)
                rel = vs[sel] - (uf + (ub - uf) * (ys[sel] - yf) / (yb - yf))
                if len(rel):
                    best = min(best, rel.min())
        elif tb.nombre.startswith(('REPIZA@1#9', 'PTRSOP024-TO')):
            borde = [v for k, v in uz.items() if abs(k[0] - tb.lo[0]) < 0.1 or abs(k[0] - tb.hi[0]) < 0.1]
            best = min(uz.values()) - float(np.mean(borde))
            claro = tb.hi[0] - tb.lo[0]
        else:
            continue
        out.append(dict(tablero=f'{tb.nombre} ({tb.grupo})', flecha=float(best), claro=float(claro)))
    out.sort(key=lambda d: d['flecha'])
    return out


def correr_variante(**kw):
    m = Modelo(**kw)
    Rc = resolver_casos(m)
    return m, Rc
