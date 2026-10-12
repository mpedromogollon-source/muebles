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

PTR_ELU_ELS = ['ELU-A1 1.2G+1.6Q', 'ELU-A2 1.4G', 'ELS G+Q', 'ELS G+0.8Q']
K_PIJAS = 1500.0 / 150.0   # N/mm por mm de PTR

VARIANTES = {
    'base': (dict(), ELU_ELS),
    'base largo plazo': (LP, ['ELS G+0.8Q']),
    'relleno': (dict(con_relleno=True), ELU_ELS),
    'relleno largo plazo': (dict(LP, con_relleno=True), ['ELS G+0.8Q']),
    'relleno y entrepano': (dict(con_relleno=True, con_entrepano=True), ELU_ELS),
    'relleno y entrepano largo plazo': (dict(LP, con_relleno=True, con_entrepano=True), ['ELS G+0.8Q']),
    '30x30 cal. 18': (dict(perfil='30x30 cal. 18'), PTR_ELU_ELS),
    '30x30 cal. 18 largo plazo': (dict(LP, perfil='30x30 cal. 18'), ['ELS G+0.8Q']),
    '30x30 cal. 14': (dict(perfil='30x30 cal. 14'), PTR_ELU_ELS),
    '30x30 cal. 14 largo plazo': (dict(LP, perfil='30x30 cal. 14'), ['ELS G+0.8Q']),
    'PTR 3x3 pulg': (dict(perfil='3"x3" cal. 14'), PTR_ELU_ELS),
    'PTR 3x3 pulg largo plazo': (dict(LP, perfil='3"x3" cal. 14'), ['ELS G+0.8Q']),
    'relleno y entrepano cal. 18': (dict(con_relleno=True, con_entrepano=True, perfil='30x30 cal. 18'), ELU_ELS),
    'relleno y entrepano cal. 18 largo plazo': (dict(LP, con_relleno=True, con_entrepano=True, perfil='30x30 cal. 18'),
                                                ['ELS G+0.8Q']),
    'sin tornillos entre maleteros': (dict(tornillos_maleteros=False), ELU_ELS),
    'sin tornillos entre maleteros largo plazo': (dict(LP, tornillos_maleteros=False), ['ELS G+0.8Q']),
    'relleno sin tornillos entre maleteros': (dict(con_relleno=True, tornillos_maleteros=False), ELU_ELS),
    'relleno sin tornillos entre maleteros largo plazo': (dict(LP, con_relleno=True, tornillos_maleteros=False),
                                                          ['ELS G+0.8Q']),
    'uniones rigidas': (dict(k_union=10 * P.K_UNION), ['ELU-A1 1.2G+1.6Q', 'ELS G+Q']),
    # sensibilidad: fijacion PTR-tablero con pijas a cada 150 mm (1500 N/mm c/u) en lugar de fijacion rigida
    'relleno y entrepano pijas': (dict(con_relleno=True, con_entrepano=True, k_fijacion=K_PIJAS), ELU_ELS),
    'relleno y entrepano pijas largo plazo': (dict(LP, con_relleno=True, con_entrepano=True,
                                                   k_fijacion=K_PIJAS / (1 + T['kdef'])), ['ELS G+0.8Q']),
    'relleno y entrepano cal. 18 pijas': (dict(con_relleno=True, con_entrepano=True, perfil='30x30 cal. 18',
                                               k_fijacion=K_PIJAS), ELU_ELS),
    'relleno y entrepano cal. 18 pijas largo plazo': (dict(LP, con_relleno=True, con_entrepano=True,
                                                           perfil='30x30 cal. 18', k_fijacion=K_PIJAS / (1 + T['kdef'])),
                                                      ['ELS G+0.8Q']),
    'sismo con anclajes': (dict(anclajes_muro=True), ['SISMO G+0.8Q+H']),
    'relleno y entrepano cal. 14 pijas': (dict(con_relleno=True, con_entrepano=True, perfil='30x30 cal. 14',
                                               k_fijacion=K_PIJAS), ELU_ELS),
    'relleno y entrepano cal. 14 pijas largo plazo': (dict(LP, con_relleno=True, con_entrepano=True,
                                                           perfil='30x30 cal. 14', k_fijacion=K_PIJAS / (1 + T['kdef'])),
                                                      ['ELS G+0.8Q']),
    'relleno y entrepano pijas a 75 mm': (dict(con_relleno=True, con_entrepano=True, k_fijacion=2 * K_PIJAS), ELU_ELS),
    'relleno y entrepano pijas a 75 mm largo plazo': (dict(LP, con_relleno=True, con_entrepano=True,
                                                           k_fijacion=2 * K_PIJAS / (1 + T['kdef'])), ['ELS G+0.8Q']),
}
# EN 1995-1-1 2.3.2.2(2): cuando el reparto de esfuerzos depende de la rigidez, el estado limite ultimo se revisa
# tambien con valores finales E/(1 + psi2 kdef), con psi2 de la accion variable principal (almacenamiento)
FIN = dict(E_tablero=T['E'] / (1 + T['psi2_almacen'] * T['kdef']),
           k_union=P.K_UNION / (1 + T['psi2_almacen'] * T['kdef']))
ELU = ['ELU-A1 1.2G+1.6Q', 'ELU-A2 1.4G', 'ELU-T1 1.35G+1.5Q', 'ELU-T2 1.35G']
for _v in ('base', 'relleno', 'relleno y entrepano', 'relleno y entrepano cal. 18', '30x30 cal. 18', '30x30 cal. 14',
           'sin tornillos entre maleteros', 'relleno sin tornillos entre maleteros', 'relleno y entrepano pijas',
           'relleno y entrepano cal. 14 pijas'):
    _kw = dict(VARIANTES[_v][0], **FIN)
    if 'k_fijacion' in _kw:
        _kw['k_fijacion'] = _kw['k_fijacion'] / (1 + T['psi2_almacen'] * T['kdef'])
    VARIANTES[f'{_v} rigidez final'] = (_kw, ELU)
X_APOYOS_EXT = (4807.5, 7672.7)
X_APOYOS_INT = (5412.4, 7067.7)


def correr(nombre):
    from modelo_fe import Modelo, resumen_malla
    kw, combos = VARIANTES[nombre]
    t0 = time.time()
    m = Modelo(**kw)
    out = dict(variante=nombre, kw=kw, perfil=m.perfil, B=m.B, malla=resumen_malla(m), combos={})
    for c in combos:
        R = m.resolver(m.cargas_combinadas(COMBOS[c]))
        r = dict(iteraciones=m.iteraciones, reac_base=R['reac_base'].tolist(),
                 anclas={int(n): v.tolist() for n, v in R['anclas'].items()},
                 anclas_xyz={int(n): m.coord[n].tolist() for n in R['anclas']})
        D = ptr_diagramas(m, R)
        r['ptr'] = {k: {kk: vv.tolist() for kk, vv in d.items()} for k, d in D.items()}
        r['ptr_flecha_rel'] = {k: flecha_relativa(d, X_APOYOS_EXT) for k, d in D.items()}
        r['ptr_flecha_rel_central'] = {k: flecha_relativa(d, X_APOYOS_INT) for k, d in D.items()}
        r['apoyos_ptr'] = {f'{k[0]}|{k[1]}': v for k, v in apoyos_ptr(m, R).items()}
        pt, pp = contactos_resumen(m, R)
        r['contactos'] = {'|'.join(k): v for k, v in pt.items()}
        r['contacto_max_punto'] = {}
        for (ptr, lado, x, y), f in pp.items():
            clave = f'{ptr}|{lado}'
            r['contacto_max_punto'][clave] = max(r['contacto_max_punto'].get(clave, 0.0), f)
        r['flechas_tableros'] = flechas_tableros(m, R)
        r['desplome_maleteros'] = max(abs(R['desp'][n][1]) for n, it in m.nodo_tablero.items()
                                      if m.tableros[it].grupo.startswith('maletero'))
        # tornillos entre maleteros: solo la traccion carga al tornillo; en compresion los costados se apoyan
        tm = [(max(float(f[0]), 0.0), float(np.hypot(f[1], f[2]))) for f in R['tornillos_maleteros']]
        r['tornillos_maleteros'] = dict(n=len(tm), lista=tm, axial_max=max((a for a, _ in tm), default=0.0),
                                        corte_max=max((v for _, v in tm), default=0.0))
        if c.startswith(('ELU-A1', 'ELU-T1', 'ELS G+Q')):
            r['contactos_nodo'] = [dict(ptr=ptr, tablero=m.tableros[it].nombre, grupo=m.tableros[it].grupo,
                                        x=float(m.coord[n][0]), y=float(m.coord[n][1]), F=f.tolist())
                                   for (e, n, it, ptr, x), (_, f) in zip(m.contactos, R['contactos'])]
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
