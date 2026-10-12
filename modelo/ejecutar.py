"""Corre las variantes del modelo y guarda resultados en resultados/.

    python modelo/ejecutar.py                       todas las variantes
    python modelo/ejecutar.py "sismo con anclajes"  solo las indicadas (se fusionan)
"""
import json
import os
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402
from analisis import (COMBOS, KMOD, apoyos_ptr, contactos_resumen, flecha_relativa,  # noqa: E402
                      flechas_tableros, ptr_diagramas, tableros_resumen, uniones_resumen)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SALIDA = os.path.join(RAIZ, 'resultados')

T = P.TABLERO
LP = dict(E_tablero=T['E'] / (1 + T['kdef']), k_union=P.K_UNION / (1 + T['kdef']))
ELU_ELS = ['ELU-A1 1.2G+1.6Q', 'ELU-A2 1.4G', 'ELU-T1 1.35G+1.5Q', 'ELU-T2 1.35G', 'ELS G+Q', 'ELS G+0.8Q']

VARIANTES = {
    'base': (dict(), ELU_ELS),
    'base largo plazo': (LP, ['ELS G+0.8Q']),
    'relleno': (dict(con_relleno=True), ELU_ELS),
    'relleno largo plazo': (dict(LP, con_relleno=True), ['ELS G+0.8Q']),
    'relleno y entrepano': (dict(con_relleno=True, con_entrepano=True), ELU_ELS),
    'relleno y entrepano largo plazo': (dict(LP, con_relleno=True, con_entrepano=True), ['ELS G+0.8Q']),
    'uniones rigidas': (dict(k_union=10 * P.K_UNION), ['ELU-A1 1.2G+1.6Q', 'ELS G+Q']),
    'PTR cal. 11': (dict(calibre='cal. 11'), ['ELU-A1 1.2G+1.6Q', 'ELS G+Q']),
    'sismo con anclajes': (dict(anclajes_muro=True), ['SISMO G+0.8Q+H']),
}
X_APOYOS_EXT = (4807.5, 7672.7)


def correr(nombre):
    from modelo_fe import Modelo, resumen_malla
    kw, combos = VARIANTES[nombre]
    t0 = time.time()
    m = Modelo(**kw)
    out = dict(variante=nombre, kw=kw, malla=resumen_malla(m), combos={})
    for c in combos:
        R = m.resolver(m.cargas_combinadas(COMBOS[c]))
        r = dict(iteraciones=m.iteraciones, reac_base=R['reac_base'].tolist(),
                 anclas={int(n): v.tolist() for n, v in R['anclas'].items()},
                 anclas_xyz={int(n): m.coord[n].tolist() for n in R['anclas']})
        D = ptr_diagramas(m, R)
        r['ptr'] = {k: {kk: vv.tolist() for kk, vv in d.items()} for k, d in D.items()}
        r['ptr_flecha_rel'] = {k: flecha_relativa(d, X_APOYOS_EXT) for k, d in D.items()}
        r['apoyos_ptr'] = {f'{k[0]}|{k[1]}': v for k, v in apoyos_ptr(m, R).items()}
        pt, pp = contactos_resumen(m, R)
        r['contactos'] = {'|'.join(k): v for k, v in pt.items()}
        r['contacto_max_punto'] = {}
        for (ptr, lado, x, y), f in pp.items():
            clave = f'{ptr}|{lado}'
            r['contacto_max_punto'][clave] = max(r['contacto_max_punto'].get(clave, 0.0), f)
        r['flechas_tableros'] = flechas_tableros(m, R)
        if c.startswith('ELU-T') or c.startswith('SISMO'):
            kmod = KMOD.get(c, T['kmod_corto'])
            U, Fv, Fa = uniones_resumen(m, R, kmod)
            r['uniones'] = [dict(u) for u in U]
            r['conector_diseno'] = dict(Fv_d=Fv, Fax_d=Fa, kmod=kmod)
            tb, f = tableros_resumen(m, R, kmod)
            r['tableros'] = tb
            r['resistencias_diseno'] = f
        if nombre in ('base', 'relleno', 'relleno y entrepano') and c in ('ELS G+Q', 'ELU-T1 1.35G+1.5Q'):
            r['campo'] = campo_desplazamientos(m, R)
        out['combos'][c] = r
    out['tiempo_s'] = time.time() - t0
    return out


def campo_desplazamientos(m, R):
    """Geometria y desplazamientos de los cascarones para figuras."""
    import openseespy.opensees as ops
    paneles = []
    for tb in m.tableros:
        quads = [[m.coord[n].tolist() for n in ops.eleNodes(e)] for e in tb.elems]
        disp = [[R['desp'][n].tolist() for n in ops.eleNodes(e)] for e in tb.elems]
        paneles.append(dict(nombre=tb.nombre, grupo=tb.grupo, quads=quads, disp=disp))
    ptr = {k: dict(xyz=[m.coord[n].tolist() for n in ns], disp=[R['desp'][n].tolist() for n in ns])
           for k, ns in m.ptr_nodos.items()}
    return dict(paneles=paneles, ptr=ptr)


def a_json(o):
    if isinstance(o, dict):
        return {str(k): a_json(v) for k, v in o.items() if k != 'campo'}
    if isinstance(o, (list, tuple)):
        return [a_json(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def main():
    os.makedirs(SALIDA, exist_ok=True)
    t0 = time.time()
    nombres = sys.argv[1:] or list(VARIANTES)
    with ProcessPoolExecutor(max_workers=4) as ex:
        res = dict(zip(nombres, ex.map(correr, nombres)))
    previo = os.path.join(SALIDA, 'resultados.pkl')
    if sys.argv[1:] and os.path.exists(previo):
        with open(previo, 'rb') as f:
            todo = pickle.load(f)
        todo.update(res)
        res = {k: todo[k] for k in VARIANTES if k in todo}
    for k, v in res.items():
        print(f'{k:22s} {v["tiempo_s"]:6.1f} s  {v["malla"]}')
    with open(os.path.join(SALIDA, 'resultados.pkl'), 'wb') as f:
        pickle.dump(res, f)
    with open(os.path.join(SALIDA, 'resultados.json'), 'w', encoding='utf-8') as f:
        json.dump(a_json(res), f, indent=1, ensure_ascii=False)
    print(f'total {time.time() - t0:.0f} s')


if __name__ == '__main__':
    main()
