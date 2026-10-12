"""Modelo 3D de elementos finitos del closet con dos PTR 3x3 bajo los maleteros.

Idealizacion
  * Cada tablero de 15 mm es un cascaron ShellMITC4 en su plano medio (ASDShellQ4
    corrotacional para el analisis de estabilidad).
  * Los cantos de tableros que llegan a otro tablero se ajustan al plano medio de
    este (modelo de planos medios). Cada tablero tiene nodos propios y las uniones
    son resortes zeroLength en traslacion, sin momento (bisagra lineal): rigidez de
    tornilleria en corte y traccion, y de apoyo directo cuando un canto se comprime
    contra una cara.
  * Tableros paralelos atornillados cara a cara (entrepanos sobre amarres, maleteros
    contiguos) se unen con resortes twoNodeLink.
  * Los PTR son vigas elasticas 3D en su eje centroidal (z = 1570 + 38.1 mm).
  * Contacto PTR-tablero: brazo rigido desde la viga y resorte solo a compresion en
    vertical (el mueble descansa sobre el PTR); en horizontal, resorte de fijacion.
  * Base del zocalo articulada en el piso.
  * Puertas, cajones y correderas no se modelan como rigidez: se aplican como carga
    en el tablero que los soporta.
"""
import json
import math
import os
from collections import defaultdict

import numpy as np
import openseespy.opensees as ops

import parametros as P
from perfiles import ptr_cuadrado

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)

# Clasificacion de piezas exportadas del SKP
ESTRUCTURALES = ('ESPCL-', 'fondo 15mm', 'lateral aire', 'REPIZA@1', 'PTRSOP', 'ZOCALO-', 'MALEST-')
EXCLUIDAS = ('Componente#4', 'Componente#9')   # muro de referencia y pieza fuera del despiece


def grupo_de(pz):
    """Torre izquierda / derecha o maletero 1, 2, 3 segun posicion."""
    x0, x1 = pz['min'][0], pz['max'][0]
    xc = 0.5 * (x0 + x1)
    if pz['min'][2] >= P.Z_TOPE_TORRES - 1:
        return 'maletero %d' % (1 + int((xc - 4800) // 960))
    return 'torre izq' if xc < 6240 else 'torre der'


class Tablero:
    def __init__(self, nombre, lo, hi, grupo, ruta=''):
        self.nombre, self.grupo, self.ruta = nombre, grupo, ruta
        self.lo0, self.hi0 = np.array(lo, float), np.array(hi, float)
        dim = self.hi0 - self.lo0
        self.a = int(np.argmin(dim))                 # eje del espesor
        self.t = float(dim[self.a])
        self.c = 0.5 * (self.lo0[self.a] + self.hi0[self.a])
        self.lo, self.hi = self.lo0.copy(), self.hi0.copy()
        self.lo[self.a] = self.hi[self.a] = self.c
        self.nodos = {}                              # (i, j) -> tag
        self.elems = []

    def ejes_plano(self):
        return [k for k in range(3) if k != self.a]

    def __repr__(self):
        return f'{self.nombre} ({self.grupo})'


def cargar_piezas(con_relleno=False, con_entrepano=False):
    datos = json.load(open(os.path.join(RAIZ, 'datos', 'piezas_closet.json'), encoding='utf-8'))
    tableros, extras = [], []
    dz = P.PTR_LADO
    for pz in datos['piezas']:
        if pz['nombre'].startswith(EXCLUIDAS):
            continue
        lo, hi = list(pz['min']), list(pz['max'])
        grupo = grupo_de(pz)
        if grupo.startswith('maletero'):
            lo[2] += dz
            hi[2] += dz
        if pz['nombre'].startswith(ESTRUCTURALES):
            tableros.append(Tablero(pz['nombre'], lo, hi, grupo, pz['ruta']))
        else:
            extras.append(dict(pz, min=lo, max=hi, grupo=grupo))
    if con_relleno:
        # Propuesta: tablero de 15 mm que cierra el hueco de 205 mm bajo el lateral aire
        for t in [t for t in tableros if t.nombre.startswith('lateral aire')]:
            lo = t.lo0.copy(); hi = t.hi0.copy()
            lo[2], hi[2] = 465.0, 670.0
            tableros.append(Tablero('relleno bajo lateral aire', lo, hi, t.grupo, 'propuesta'))
    if con_entrepano:
        # Propuesta: entrepano fijo intermedio que arriostra el canto frontal de ambos laterales
        for t in [t for t in tableros if t.nombre.startswith('PTRSOP024-TO')]:
            lo = t.lo0.copy(); hi = t.hi0.copy()
            lo[2], hi[2] = 1120.0, 1135.0
            tableros.append(Tablero('entrepano fijo intermedio', lo, hi, t.grupo, 'propuesta'))
    return tableros, extras


def _solape(p, q, k):
    return min(p.hi0[k], q.hi0[k]) - max(p.lo0[k], q.lo0[k])


def ajustar_planos_medios(tableros):
    """Lleva cada canto al plano medio del tablero perpendicular que toca.

    Tipo 1: el canto de p apoya en la cara de q (solape positivo en el espesor de p).
    Tipo 2: p cubre el canto de q (union en L a paño). Se prefiere el tipo 1.
    """
    for p in tableros:
        for b in p.ejes_plano():
            tercero = 3 - p.a - b
            for lado in ('lo', 'hi'):
                e = getattr(p, lado + '0')[b]
                mejor, puntaje = None, 1e9
                for q in tableros:
                    if q is p or q.a != b:
                        continue
                    d = abs(e - q.c)
                    if d > q.t / 2 + 1.1:
                        continue
                    if any(_solape(p, q, k) < -1.0 for k in range(3)) or _solape(p, q, tercero) < 1.0:
                        continue
                    tipo1 = _solape(p, q, p.a) >= 1.0
                    s = d + (0.0 if tipo1 else 1.0)
                    if s < puntaje:
                        mejor, puntaje = q, s
                if mejor is not None:
                    getattr(p, lado)[b] = mejor.c


def malla_global(tableros, extras_y=(), h=P.H_MALLA):
    G = []
    for k in range(3):
        v = []
        for t in tableros:
            if t.a == k:
                v.append(t.c)
            else:
                v += [t.lo[k], t.hi[k]]
        if k == 0:
            v += list(P.PTR_X)
        if k == 1:
            v += list(extras_y)
        v = np.sort(np.array(v))
        cl = [[v[0]]]
        for x in v[1:]:
            (cl[-1].append(x) if x - cl[-1][-1] < 2.0 else cl.append([x]))
        rep = [float(np.mean(c)) for c in cl]
        fino = [rep[0]]
        for x in rep[1:]:
            n = max(1, int(math.ceil((x - fino[-1]) / h - 1e-9)))
            fino += list(np.linspace(fino[-1], x, n + 1)[1:])
        G.append(np.array(fino))
    # reasignar cotas de tableros al representante de la reticula
    for t in tableros:
        for k in range(3):
            if t.a == k:
                t.c = float(G[k][np.argmin(abs(G[k] - t.c))])
                t.lo[k] = t.hi[k] = t.c
            else:
                t.lo[k] = float(G[k][np.argmin(abs(G[k] - t.lo[k]))])
                t.hi[k] = float(G[k][np.argmin(abs(G[k] - t.hi[k]))])
    return G


class Modelo:
    def __init__(self, calibre=P.PTR_CALIBRE_BASE, con_relleno=False, E_tablero=P.TABLERO['E'],
                 k_union=P.K_UNION, anclajes_muro=False, unilateral=True, no_lineal_geom=False,
                 con_entrepano=False):
        self.calibre = calibre
        self.ptr = ptr_cuadrado(P.PTR_LADO, P.PTR_CALIBRES[calibre])
        self.con_relleno = con_relleno
        self.E = E_tablero
        self.k_union = k_union
        self.anclajes_muro = anclajes_muro
        self.unilateral = unilateral
        self.no_lineal_geom = no_lineal_geom
        self.tipo_shell = 'ASDShellQ4' if no_lineal_geom else 'ShellMITC4'
        self.tableros, self.extras = cargar_piezas(con_relleno, con_entrepano)
        ajustar_planos_medios(self.tableros)
        yp = [P.PTR_Y_FRENTE[0], sum(P.PTR_Y_FRENTE) / 2, P.PTR_Y_FRENTE[1],
              P.PTR_Y_FONDO[0], sum(P.PTR_Y_FONDO) / 2]
        self.G = malla_global(self.tableros, extras_y=yp)
        self.construir()

    # ------------------------------------------------------------------ malla
    def construir(self):
        ops.wipe()
        ops.model('basic', '-ndm', 3, '-ndf', 6)
        self.coord = {}
        self.nodo_tablero = {}
        tag = 1
        ops.section('ElasticMembranePlateSection', 1, self.E, P.TABLERO['nu'], P.TABLERO['espesor'], 0.0)
        etag = 1
        self.elem_tablero = {}
        self.elem_area = {}
        for it, t in enumerate(self.tableros):
            b, c = t.ejes_plano()
            gb = self.G[b][(self.G[b] >= t.lo[b] - 1e-6) & (self.G[b] <= t.hi[b] + 1e-6)]
            gc = self.G[c][(self.G[c] >= t.lo[c] - 1e-6) & (self.G[c] <= t.hi[c] + 1e-6)]
            t.gb, t.gc = gb, gc
            for i, u in enumerate(gb):
                for j, v in enumerate(gc):
                    xyz = [0.0, 0.0, 0.0]
                    xyz[t.a], xyz[b], xyz[c] = t.c, u, v
                    ops.node(tag, *xyz)
                    self.coord[tag] = np.array(xyz)
                    self.nodo_tablero[tag] = it
                    t.nodos[(i, j)] = tag
                    tag += 1
            for i in range(len(gb) - 1):
                for j in range(len(gc) - 1):
                    n = [t.nodos[(i, j)], t.nodos[(i + 1, j)], t.nodos[(i + 1, j + 1)], t.nodos[(i, j + 1)]]
                    if self.no_lineal_geom:
                        ops.element('ASDShellQ4', etag, *n, 1, '-corotational')
                    else:
                        ops.element(self.tipo_shell, etag, *n, 1)
                    t.elems.append(etag)
                    self.elem_tablero[etag] = it
                    self.elem_area[etag] = (gb[i + 1] - gb[i]) * (gc[j + 1] - gc[j])
                    etag += 1
        self.n_shell = etag - 1
        self.tag_libre = tag
        self.etag_libre = etag
        ops.uniaxialMaterial('Elastic', 1, 1.0)   # material base, se escala por elemento
        self.matag = 2
        self._uniones()
        self._uniones_cara()
        self._ptr()
        self._apoyos()

    def _nuevo_material(self, k):
        ops.uniaxialMaterial('Elastic', self.matag, k)
        self.matag += 1
        return self.matag - 1

    def _uniones(self):
        """Resortes entre nodos coincidentes de tableros distintos."""
        grupos = defaultdict(list)
        for n, xyz in self.coord.items():
            grupos[tuple(np.round(xyz, 1))].append(n)
        self.uniones = []          # (elem, nodo_i, nodo_j, tablero_i, tablero_j, trib)
        self.grupos = grupos
        for key, ns in grupos.items():
            ts = [self.nodo_tablero[n] for n in ns]
            if len(set(ts)) < 2:
                continue
            # nodo central: el tablero que en la geometria real contiene el punto (pieza de cara)
            xyz = np.array(key)
            orden = sorted(range(len(ns)), key=lambda i: not self._contiene(self.tableros[ts[i]], xyz))
            ns = [ns[i] for i in orden]
            ts = [ts[i] for i in orden]
            n0, t0 = ns[0], ts[0]
            for n1, t1 in zip(ns[1:], ts[1:]):
                trib = self._tributaria(n0, t0, t1)
                k = max(self.k_union * trib, 1.0)
                m = self._nuevo_material(k)
                mats = [m, m, m]
                p, q = self.tableros[t0], self.tableros[t1]
                if p.a != q.a:
                    # direccion normal a la pieza de cara: apoyo directo (rigido) en compresion,
                    # tornillo (flexible) en traccion
                    C, E, i_es_C = (p, q, True) if self._cruza(p, q) else (q, p, False)
                    s = math.copysign(1.0, 0.5 * (E.lo0[C.a] + E.hi0[C.a]) - C.c)
                    sig = s if i_es_C else -s          # compresion cuando sig * (u_j - u_i) < 0
                    kb = max(P.K_APOYO * self.k_union / P.K_UNION * trib, k)
                    if sig > 0:
                        ops.uniaxialMaterial('Elastic', self.matag, k, 0.0, kb)
                    else:
                        ops.uniaxialMaterial('Elastic', self.matag, kb, 0.0, k)
                    mats[C.a] = self.matag
                    self.matag += 1
                e = self.etag_libre
                ops.element('zeroLength', e, n0, n1, '-mat', *mats, '-dir', 1, 2, 3)
                self.uniones.append((e, n0, n1, t0, t1, trib))
                self.etag_libre += 1

    def _uniones_cara(self):
        """Tableros paralelos atornillados cara a cara (separacion = un espesor).

        Entrepanos sobre amarres y travesanos: resorte en cada par de nodos enfrentados.
        Costados de maleteros contiguos: cuatro tornillos de union cerca de las esquinas.
        """
        self.uniones_cara = []
        k_nodo = self.k_union * P.H_MALLA * 0.8
        k_tornillo = 1500.0
        m_n = self._nuevo_material(k_nodo)
        m_t = self._nuevo_material(k_tornillo)
        for i, p in enumerate(self.tableros):
            for j, q in enumerate(self.tableros):
                if j <= i or p.a != q.a or abs(abs(p.c - q.c) - P.TABLERO['espesor']) > 0.6:
                    continue
                b, c = p.ejes_plano()
                if min(p.hi[b], q.hi[b]) - max(p.lo[b], q.lo[b]) < 1 or \
                        min(p.hi[c], q.hi[c]) - max(p.lo[c], q.lo[c]) < 1:
                    continue
                qn = {(round(self.coord[n][b], 1), round(self.coord[n][c], 1)): n for n in q.nodos.values()}
                pares = [(n, qn[(round(self.coord[n][b], 1), round(self.coord[n][c], 1))])
                         for n in p.nodos.values()
                         if (round(self.coord[n][b], 1), round(self.coord[n][c], 1)) in qn]
                if not pares:
                    continue
                if p.grupo != q.grupo:          # maleteros contiguos: 4 tornillos
                    obj = [(y, z) for y in (-55.0, 437.0) for z in (min(p.hi[2], q.hi[2]) - 100.0,
                                                                     max(p.lo[2], q.lo[2]) + 100.0)]
                    pares = [min(pares, key=lambda pr: (self.coord[pr[0]][1] - y) ** 2 + (self.coord[pr[0]][2] - z) ** 2)
                             for y, z in obj]
                    mat = m_t
                else:
                    mat = m_n
                for n0, n1 in pares:
                    e = self.etag_libre
                    ops.element('twoNodeLink', e, n0, n1, '-mat', mat, mat, mat, '-dir', 1, 2, 3)
                    self.uniones_cara.append((e, n0, n1, i, j))
                    self.etag_libre += 1

    @staticmethod
    def _cruza(p, q):
        """True si p atraviesa el plano medio de q (p es la pieza de cara)."""
        k = q.a
        return p.lo0[k] < q.c - 1.0 and p.hi0[k] > q.c + 1.0

    @staticmethod
    def _contiene(t, xyz, tol=0.5):
        return bool(np.all(xyz >= t.lo0 - tol) and np.all(xyz <= t.hi0 + tol))

    def _tributaria(self, n, ti, tj):
        p, q = self.tableros[ti], self.tableros[tj]
        ejes = [k for k in range(3) if k not in (p.a, q.a)]
        ov = {k: min(p.hi[k], q.hi[k]) - max(p.lo[k], q.lo[k]) for k in ejes}
        k = max(ov, key=ov.get)
        if ov[k] <= 0:
            return 0.0
        s = self.coord[n][k]
        lo, hi = max(p.lo[k], q.lo[k]), min(p.hi[k], q.hi[k])
        g = self.G[k]
        i = np.argmin(abs(g - s))
        prev = g[i - 1] if i > 0 else s
        nxt = g[i + 1] if i < len(g) - 1 else s
        return 0.5 * (min(nxt, hi) - s) + 0.5 * (s - max(prev, lo))

    def _ptr(self):
        pr = self.ptr
        Ac = P.ACERO
        ops.geomTransf('Corotational' if self.no_lineal_geom else 'Linear', 1, 0.0, 0.0, 1.0)
        zc = P.Z_TOPE_TORRES + P.PTR_LADO / 2
        gx = self.G[0][(self.G[0] >= P.PTR_X[0] - 1e-6) & (self.G[0] <= P.PTR_X[1] + 1e-6)]
        self.ptr_nodos = {}
        self.ptr_elems = {}
        self.ptr_x = gx
        for nombre, (y0, y1) in (('frente', P.PTR_Y_FRENTE), ('fondo', P.PTR_Y_FONDO)):
            yc = 0.5 * (y0 + y1)
            nod = []
            for x in gx:
                ops.node(self.tag_libre, x, yc, zc)
                self.coord[self.tag_libre] = np.array([x, yc, zc])
                nod.append(self.tag_libre)
                self.tag_libre += 1
            el = []
            for a, b in zip(nod[:-1], nod[1:]):
                ops.element('elasticBeamColumn', self.etag_libre, a, b, pr['A'], Ac['E'], Ac['G'],
                            pr['J'], pr['I'], pr['I'], 1)
                el.append(self.etag_libre)
                self.etag_libre += 1
            self.ptr_nodos[nombre] = nod
            self.ptr_elems[nombre] = el
        # contactos
        self.contactos = []        # (elem, nodo_tablero, tablero, ptr, x)
        mk = self._nuevo_material(P.K_CONTACTO)       # horizontal: tornillo / friccion
        if self.unilateral:
            ops.uniaxialMaterial('ENT', self.matag, P.K_CONTACTO)  # vertical: solo compresion
            mz = self.matag
            self.matag += 1
        else:
            mz = mk
        z_torre = self._nivel_contacto('torre')
        z_mal = self._nivel_contacto('maletero')
        for nombre, (y0, y1) in (('frente', P.PTR_Y_FRENTE), ('fondo', P.PTR_Y_FONDO)):
            yc = 0.5 * (y0 + y1)
            ya_unidos = set()
            # primero cantos de tableros verticales, despues tableros horizontales
            # en nodos coincidentes se prefiere la pieza que realmente ocupa el punto
            cand = sorted((n for n in self.coord if n in self.nodo_tablero),
                          key=lambda n: (self.tableros[self.nodo_tablero[n]].a == 2,
                                         not self._contiene(self.tableros[self.nodo_tablero[n]], self.coord[n])))
            for n in cand:
                xyz = self.coord[n]
                t = self.tableros[self.nodo_tablero[n]]
                nivel = z_mal if t.grupo.startswith('maletero') else z_torre
                if abs(xyz[2] - nivel) > 0.5 or not (y0 - 1 <= xyz[1] <= y1 + 1):
                    continue
                if not (P.PTR_X[0] - 1 <= xyz[0] <= P.PTR_X[1] + 1):
                    continue
                # tablero horizontal: apoyo lineal sobre el eje del PTR (sin empotramiento)
                if t.a == 2 and abs(xyz[1] - yc) > 0.5:
                    continue
                clave = (t.grupo.startswith('maletero'),) + tuple(np.round(xyz, 1))
                if clave in ya_unidos:
                    continue
                ya_unidos.add(clave)
                i = int(np.argmin(abs(self.ptr_x - xyz[0])))
                master = self.ptr_nodos[nombre][i]
                aux = self.tag_libre
                ops.node(aux, *xyz)
                self.tag_libre += 1
                ops.rigidLink('beam', master, aux)
                # orden de nodos tal que la compresion sea deformacion negativa
                i_, j_ = (aux, n) if t.grupo.startswith('maletero') else (n, aux)
                ops.element('zeroLength', self.etag_libre, i_, j_, '-mat', mk, mk, mz, '-dir', 1, 2, 3)
                self.contactos.append((self.etag_libre, n, self.nodo_tablero[n], nombre, xyz[0]))
                self.etag_libre += 1

    def _nivel_contacto(self, tipo):
        if tipo == 'torre':
            zs = [t.hi[2] for t in self.tableros if t.grupo.startswith('torre') and t.a != 2]
            return max(zs)
        zs = [t.lo[2] for t in self.tableros if t.grupo.startswith('maletero') and t.a != 2]
        return min(zs)

    def _apoyos(self):
        self.base = [n for n, xyz in self.coord.items() if n in self.nodo_tablero and abs(xyz[2]) < 0.5]
        for n in self.base:
            ops.fix(n, 1, 1, 1, 0, 0, 0)
        self.anclas = []
        if self.anclajes_muro:
            # taquetes al muro: 2 por torre (lateral exterior, parte alta) y 2 por maletero
            for t in self.tableros:
                es_lat = t.nombre.startswith('ESPCL-LD') or t.nombre.startswith('MALEST-RI') or t.nombre.startswith('MALEST-RD')
                if not es_lat:
                    continue
                cand = [n for n in t.nodos.values()]
                ymax = max(self.coord[n][1] for n in cand)
                zmax = max(self.coord[n][2] for n in cand)
                # taquete junto al costado: extremo exterior de la tira trasera o lateral de la torre
                xs = t.lo[0] if t.nombre.startswith('MALEST-RI') else t.hi[0]
                obj = np.array([xs if t.a == 1 else t.c, ymax, zmax - 100])
                n = min(cand, key=lambda n: np.linalg.norm(self.coord[n] - obj))
                ops.fix(n, 0, 1, 0, 0, 0, 0)
                self.anclas.append(n)

    # ------------------------------------------------------------------ cargas
    def cargas_caso(self, caso):
        """Diccionario nodo -> [Fx, Fy, Fz] (N) para el caso indicado."""
        F = defaultdict(lambda: np.zeros(3))
        C = P.CARGAS
        if caso == 'G':
            w = P.peso_tablero_N_mm2()
            for e, it in self.elem_tablero.items():
                for n in ops.eleNodes(e):
                    F[n][2] -= w * self.elem_area[e] / 4
            wp = self.ptr['A'] * P.ACERO['densidad'] * 1e-9 * P.GRAV
            for nombre, nod in self.ptr_nodos.items():
                xs = self.ptr_x
                for i, n in enumerate(nod):
                    lt = 0.5 * ((xs[i + 1] - xs[i]) if i < len(xs) - 1 else 0) + \
                         0.5 * ((xs[i] - xs[i - 1]) if i > 0 else 0)
                    F[n][2] -= wp * lt
            for ex in self.extras:
                self._carga_extra(F, ex)
        elif caso == 'Q_maleteros':
            for t in self.tableros:
                if t.nombre == 'MALEST-MA':
                    self._presion(F, t, C['q_maletero'])
        elif caso == 'Q_torres':
            for t in self.tableros:
                if t.nombre.startswith(('REPIZA@1#9', 'PTRSOP024-TO')):
                    self._presion(F, t, C['q_repisa_torre'])
            for ex in self.extras:
                if ex['nombre'].startswith('GH-FRENTE'):
                    self._carga_cajon(F, ex, C['q_cajon_kg'] * P.GRAV)
        elif caso == 'Q_barra':
            L = 7060.2 - 5419.9
            R = C['q_barra'] * L / 2
            for t in self.tableros:
                if t.nombre.startswith('lateral aire'):
                    self._puntual(F, t, np.array([t.c, 187.0, C['z_barra']]), R)
        elif caso == 'H_sismo':
            # fuerza horizontal c * (G + psi2 Q) hacia el frente (-y), aplicada donde esta la masa
            psi2 = P.TABLERO['psi2_almacen']
            for k, v in self.cargas_combinadas({'G': 1.0, 'Q_maleteros': psi2, 'Q_torres': psi2}).items():
                F[k][1] += C['c_sismico'] * v[2]
        return F

    def cargas_combinadas(self, factores):
        F = defaultdict(lambda: np.zeros(3))
        for caso, f in factores.items():
            for n, v in self.cargas_caso(caso).items():
                F[n] += f * v
        return F

    def _presion(self, F, t, q):
        for e in t.elems:
            for n in ops.eleNodes(e):
                F[n][2] -= q * self.elem_area[e] / 4

    def _puntual(self, F, t, xyz, W):
        ns = list(t.nodos.values())
        d = np.array([np.linalg.norm(self.coord[n] - xyz) for n in ns])
        idx = np.argsort(d)[:4]
        for i in idx:
            F[ns[i]][2] -= W / 4

    def _linea(self, F, t, sel, W, comp=2):
        ns = [n for n in t.nodos.values() if sel(self.coord[n])]
        if not ns:
            raise RuntimeError(f'sin nodos para carga en {t}')
        for n in ns:
            F[n][comp] -= W / len(ns)

    def _carga_extra(self, F, ex):
        """Peso de puertas, cajones y correderas sobre el tablero que los soporta."""
        lo, hi = np.array(ex['min']), np.array(ex['max'])
        dim = hi - lo
        nombre = ex['nombre']
        if nombre.startswith('GP-RSMLC'):
            W = 1.0 * P.GRAV           # corredera metalica ~1 kg
        else:
            area = np.prod(np.sort(dim)[1:])
            W = area * P.peso_tablero_N_mm2()
        if nombre.startswith('PUNRM'):
            # puerta: se cuelga del lateral de la bisagra (frente del tablero)
            xc = 0.5 * (lo[0] + hi[0])
            if ex['grupo'].startswith('torre'):
                cand = [t for t in self.tableros if t.nombre.startswith('lateral aire') and t.grupo == ex['grupo']]
            else:
                # bisagras en el costado mas cercano a uno de los cantos verticales de la puerta
                cand = [t for t in self.tableros if t.nombre.startswith(('MALEST-MI', 'MALEST-MD'))]
                cand = [min(cand, key=lambda t: min(abs(t.c - lo[0]), abs(t.c - hi[0])))]
            t = min(cand, key=lambda t: abs(t.c - xc))
            ymin = min(self.coord[n][1] for n in t.nodos.values())
            self._linea(F, t, lambda p: abs(p[1] - ymin) < 0.5 and lo[2] - 40 <= p[2] <= hi[2] + 40, W)
        elif nombre.startswith(('GH-', 'GP-')):
            self._carga_cajon(F, ex, W, por_pieza=True)

    def _carga_cajon(self, F, ex, W, por_pieza=False):
        """Reparte el peso del cajon en las dos correderas: lateral exterior y panel inferior."""
        lo, hi = np.array(ex['min']), np.array(ex['max'])
        zc = 0.5 * (lo[2] + hi[2])
        # altura de corredera: la del cajon correspondiente (125-165 o 301-341)
        zs = 145.0 if zc < 275 else 321.5
        tor = ex['grupo']
        lados = [t for t in self.tableros if t.grupo == tor and t.nombre.startswith(('ESPCL-LD', 'REPIZA@1#8'))]
        for t in lados:
            zz = sorted(set(round(self.coord[n][2], 1) for n in t.nodos.values()), key=lambda z: abs(z - zs))[0]
            self._linea(F, t, lambda p: abs(p[2] - zz) < 0.5 and p[1] < 470, W / 2)

    # ------------------------------------------------------------------ analisis
    def resolver(self, F):
        ops.wipeAnalysis()
        ops.remove('loadPattern', 1)
        ops.remove('timeSeries', 1)
        ops.reset()
        ops.timeSeries('Constant', 1)
        ops.pattern('Plain', 1, 1)
        for n, v in F.items():
            ops.load(n, float(v[0]), float(v[1]), float(v[2]), 0.0, 0.0, 0.0)
        ops.constraints('Transformation')
        ops.numberer('RCM')
        ops.system('UmfPack')
        ops.analysis('Static')
        if not self.unilateral:
            ops.algorithm('Linear')
            ops.integrator('LoadControl', 1.0)
            ok = ops.analyze(1)
        else:
            # contacto unilateral: Newton hasta estabilizar el conjunto de apoyos activos
            ops.test('NormDispIncr', 1e-6, 60)
            ops.algorithm('Newton')
            ops.integrator('LoadControl', 1.0)
            ok = ops.analyze(1)
            if ok != 0:
                ops.reset()
                ops.algorithm('KrylovNewton')
                ops.integrator('LoadControl', 0.25)
                ok = ops.analyze(4)
        if ok != 0:
            raise RuntimeError('el analisis no convergio')
        self.iteraciones = ops.testIter()
        ops.reactions()
        return self.extraer()

    def extraer(self):
        R = {}
        R['desp'] = {n: np.array(ops.nodeDisp(n)[:3]) for n in self.coord}
        R['uniones'] = [(e, np.array(ops.eleResponse(e, 'force')[:3])) for e, *_ in self.uniones]
        R['contactos'] = [(e, np.array(ops.eleResponse(e, 'force')[:3])) for e, *_ in self.contactos]
        R['ptr'] = {}
        for nombre, els in self.ptr_elems.items():
            R['ptr'][nombre] = [np.array(ops.eleResponse(e, 'localForce')) for e in els]
        R['shell'] = {}
        for e in range(1, self.n_shell + 1):
            R['shell'][e] = np.array(ops.eleResponse(e, 'stresses')).reshape(4, 8)
        R['reac_base'] = np.sum([ops.nodeReaction(n)[:3] for n in self.base], axis=0)
        R['anclas'] = {n: np.array(ops.nodeReaction(n)[:3]) for n in self.anclas}
        return R


def resumen_malla(m):
    return dict(tableros=len(m.tableros), nodos=len(m.coord), cascarones=m.n_shell,
                uniones=len(m.uniones), uniones_cara=len(m.uniones_cara), contactos=len(m.contactos))


if __name__ == '__main__':
    import time
    t0 = time.time()
    m = Modelo()
    print(resumen_malla(m), f'{time.time()-t0:.1f}s')
    F = m.cargas_caso('G')
    print('Peso G total (N):', sum(v[2] for v in F.values()))
    r = m.resolver(F)
    print('Reaccion base:', r['reac_base'], f'{time.time()-t0:.1f}s')
