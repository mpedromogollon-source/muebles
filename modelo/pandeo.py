"""Estabilidad de las torres: analisis con no linealidad geometrica.

Se usan cascarones ASDShellQ4 corrotacionales y PTR corrotacional. La combinacion de diseno se
incrementa por un factor lambda hasta perder convergencia (tras reintentar con pasos
de 1/4 y 1/16 y con otros algoritmos) o hasta lambda_max, con
una pequena perturbacion lateral (0.5 % de la carga vertical que baja por cada
lateral) para disparar el modo de pandeo fuera del plano.

    python modelo/pandeo.py          todos los casos
    python modelo/pandeo.py 4 5      solo los casos indicados (se fusionan con los existentes)
"""
import json
import os
import sys

import numpy as np
import openseespy.opensees as ops

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import parametros as P  # noqa: E402
from analisis import COMBOS  # noqa: E402
from modelo_fe import Modelo  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def barrido(nombre, kw, combo, lam_max=4.0, dlam=0.5, parcial=None):
    m = Modelo(no_lineal_geom=True, **kw)
    F = m.cargas_combinadas(COMBOS[combo])
    # perturbacion: fuerza en x a media altura del canto frontal de cada lateral y lateral aire
    for t in m.tableros:
        if t.nombre.startswith(('ESPCL-LD', 'lateral aire')):
            ns = [n for n in t.nodos.values() if abs(m.coord[n][1] - t.lo[1]) < 0.5]
            zm = 0.5 * (t.lo[2] + t.hi[2]) if t.nombre.startswith('lateral aire') else 1127.5
            n = min(ns, key=lambda n: abs(m.coord[n][2] - zm))
            F[n] = F[n] + np.array([0.005 * 1500.0, 0.0, 0.0])
    ops.wipeAnalysis()
    ops.timeSeries('Linear', 1)
    ops.pattern('Plain', 1, 1)
    for n, v in F.items():
        ops.load(n, float(v[0]), float(v[1]), float(v[2]), 0.0, 0.0, 0.0)
    ops.constraints('Transformation')
    ops.numberer('RCM')
    ops.system('UmfPack')
    ops.test('NormDispIncr', 1e-5, 40)
    ops.algorithm('Newton')
    ops.integrator('LoadControl', dlam)
    ops.analysis('Static')
    laterales = [t for t in m.tableros if t.nombre.startswith(('ESPCL-LD', 'lateral aire'))]
    traseros = [t for t in m.tableros if t.nombre.startswith('fondo')]
    techos = [n for t in m.tableros if t.nombre == 'MALEST-MR' for n in t.nodos.values()]

    def abombamiento(t, comp):
        """Desplazamiento fuera del plano respecto al plano que pasa por las esquinas del tablero."""
        ns = list(t.nodos.values())
        X = np.array([m.coord[n] for n in ns])
        u = np.array([ops.nodeDisp(n)[comp] for n in ns])
        b, c = t.ejes_plano()
        A = np.c_[np.ones(len(ns)), X[:, b], X[:, c]]
        esq = [t.nodos[(i, j)] for i in (0, len(t.gb) - 1) for j in (0, len(t.gc) - 1)]
        idx = [ns.index(n) for n in esq]
        coef = np.linalg.lstsq(A[idx], u[idx], rcond=None)[0]
        r = u - A @ coef
        k = int(np.argmax(abs(r)))
        return abs(r[k]), X[k]

    curva = []
    lam = 0.0
    import time
    t0 = time.time()
    nota = None
    while lam < lam_max - 1e-9:
        if time.time() - t0 > T_MAX_CASO:
            nota = 'detenido por tiempo de calculo sin perdida de estabilidad'
            break
        for div, alg, iters in INTENTOS:
            ops.integrator('LoadControl', dlam / div)
            ops.algorithm(alg)
            ops.test('NormDispIncr', 1e-5, iters)
            if ops.analyze(1) == 0:
                lam += dlam / div
                break
        else:
            break
        ab = max((abombamiento(t, 0) + (t.nombre, t.grupo) for t in laterales), key=lambda r: r[0])
        abg = max((abombamiento(t, t.a) + (t.nombre, t.grupo) for t in m.tableros if t.a != 2), key=lambda r: r[0])
        abt = max(abombamiento(t, 1)[0] for t in traseros)
        uy = max(abs(ops.nodeDisp(n)[1]) for n in techos)
        uz = min(ops.nodeDisp(n)[2] for n in m.ptr_nodos['frente'])
        curva.append(dict(lam=round(lam, 3), abombamiento_lateral=ab[0], donde=ab[1].round(0).tolist(),
                          pieza=f'{ab[2]} ({ab[3]})', abombamiento_trasero=abt, desplome=uy, flecha_ptr=uz,
                          abombamiento_global=abg[0], pieza_global=f'{abg[2]} ({abg[3]})'))
        print(f'  {nombre}: lambda={lam:.2f}  abombamiento lateral={ab[0]:.2f} mm en {ab[2]} {ab[1].round(0)}  '
              f'trasero={abt:.2f}  desplome={uy:.2f}  flecha PTR={uz:.2f} mm  global={abg[0]:.2f} en {abg[2]} ({abg[3]})',
              flush=True)
        if parcial:
            with open(parcial, 'w') as f:
                json.dump(dict(variante=nombre, combo=combo, curva=curva, lambda_ultimo=lam,
                               convergio_hasta_max=False, campo_final=None), f)
    campo = {t.nombre + '|' + t.grupo: dict(xyz=[m.coord[n].tolist() for n in t.nodos.values()],
                                            u=[ops.nodeDisp(n)[:3] for n in t.nodos.values()])
             for t in m.tableros if t.grupo.startswith('torre')}
    out = dict(variante=nombre, combo=combo, curva=curva, lambda_ultimo=lam, paso_falla=dlam / INTENTOS[-1][0],
               convergio_hasta_max=lam >= lam_max - 1e-9, campo_final=campo)
    if nota:
        out['nota'] = nota
    return out


T_MAX_CASO = 60 * 60      # s por caso; si se alcanza sin divergencia se reporta como cota inferior
# Antes de declarar perdida de convergencia se reintenta el incremento con pasos menores y otros
# algoritmos, para no confundir una dificultad numerica con un limite de estabilidad.
INTENTOS = [(1, 'Newton', 40), (4, 'Newton', 40), (16, 'NewtonLineSearch', 100), (16, 'KrylovNewton', 100)]
T = P.TABLERO
LP = dict(E_tablero=T['E'] / (1 + T['kdef']), k_union=P.K_UNION / (1 + 2 * T['kdef']))   # EN 1995 2.3.2.2(3)
CASOS = [
    ('proyecto, ELU con E/gamma_M', dict(E_tablero=T['E'] / T['gamma_M']), 'ELU-T1 1.35G+1.5Q'),
    ('proyecto, largo plazo E_fin', LP, 'ELS G+0.8Q'),
    ('con relleno, ELU con E/gamma_M', dict(E_tablero=T['E'] / T['gamma_M'], con_relleno=True), 'ELU-T1 1.35G+1.5Q'),
    ('con relleno, largo plazo E_fin', dict(LP, con_relleno=True), 'ELS G+0.8Q'),
    ('relleno y entrepaño, ELU con E/gamma_M', dict(E_tablero=T['E'] / T['gamma_M'], con_relleno=True,
                                                     con_entrepano=True), 'ELU-T1 1.35G+1.5Q'),
    ('relleno y entrepaño, largo plazo E_fin', dict(LP, con_relleno=True, con_entrepano=True), 'ELS G+0.8Q'),
]


def _correr(i):
    return barrido(*CASOS[i], parcial=os.path.join(RAIZ, 'resultados', f'pandeo_parcial_{i}.json'))


def main():
    """Sin argumentos corre todos los casos; con indices, solo esos y los fusiona con lo existente."""
    from concurrent.futures import ProcessPoolExecutor
    idx = [int(a) for a in sys.argv[1:]] or list(range(len(CASOS)))
    with ProcessPoolExecutor(max_workers=4) as ex:
        nuevos = list(ex.map(_correr, idx))
    ruta = os.path.join(RAIZ, 'resultados', 'pandeo.json')
    previos = json.load(open(ruta)) if (sys.argv[1:] and os.path.exists(ruta)) else []
    por_nombre = {d['variante']: d for d in previos}
    por_nombre.update({d['variante']: d for d in nuevos})
    orden = [c[0] for c in CASOS]
    with open(ruta, 'w') as f:
        json.dump([por_nombre[n] for n in orden if n in por_nombre], f)


if __name__ == '__main__':
    main()
