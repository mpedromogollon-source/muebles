"""Lector minimo de archivos SketchUp 2021+ (.skp) para extraer piezas de mueble.

El .skp de SketchUp 2021 en adelante es un encabezado UTF-16 seguido de un ZIP.
Dentro del ZIP, model.dat es un arbol binario TLV: etiqueta (uint16), longitud
(uint32) y contenido. Este lector reconoce solo lo necesario para despiece:

  0x157c  definicion de componente  (0x157e nombre, 0x1388 entidades)
  0x1388  entidades                 (0x1389 vertices, 0x138c instancias)
  0x1964  instancia                 (0x1966 transformacion, 0x1967 ref. definicion)
  0x07d0  atributos de entidad      (0x05dc/0x05de id, 0x07d3 banderas, bit 0 = oculto)

La transformacion son 13 doubles: matriz 3x3 por filas, traslacion y escala
homogenea. Las unidades internas son pulgadas.

Uso:
    python herramientas/skp_lector.py datos/origen/closet_pedido_mx.skp \
        --xmin 4700 --xmax 7800 --salida datos/piezas_closet.json
"""
import argparse
import json
import struct
import zipfile

import numpy as np

PULG = 25.4


def _secuencia(d, a, b):
    """Lista de (etiqueta, inicio, longitud) si [a, b) es una secuencia TLV exacta."""
    out, p = [], a
    while p < b:
        if p + 6 > b:
            return None
        tag, n = struct.unpack_from('<HI', d, p)
        if p + 6 + n > b:
            return None
        out.append((tag, p + 6, n))
        p += 6 + n
    return out


def _arbol(d, a, b, prof=0):
    nodos = []
    for tag, s, n in _secuencia(d, a, b):
        hijos = None
        if n >= 6 and prof < 60 and _secuencia(d, s, s + n):
            hijos = _arbol(d, s, s + n, prof + 1)
        nodos.append((tag, s, n, hijos))
    return nodos


class ModeloSKP:
    def __init__(self, ruta):
        with zipfile.ZipFile(ruta) as z:
            self.d = z.read('model.dat')
        self.raiz = _arbol(self.d, 0, len(self.d))
        self.defs = {}
        for c in self._buscar(self.raiz[0], 0x157c):
            ent = self._hijo(c, 0x1388)
            verts = []
            bloque_v = self._hijo(ent, 0x1389)
            if bloque_v:
                for v in self._hijos(bloque_v, 0x09c4):
                    verts.append(struct.unpack('<3d', self._dato(self._hijo(v, 0x09c5))))
            bloque_i = self._hijo(ent, 0x138c)
            self.defs[self._id(ent)] = dict(
                nombre=self._dato(self._hijo(c, 0x157e)).decode('latin1'),
                verts=np.array(verts) if verts else None,
                insts=self._hijos(bloque_i, 0x1964) if bloque_i else [])
        modelo = next(n for n in self.raiz[0][3] if n[0] == 0x01f6)
        self.insts_raiz = self._hijos(self._hijo(self._hijo(modelo, 0x1388), 0x138c), 0x1964)

    # utilidades del arbol
    def _hijo(self, n, tag):
        return next((c for c in (n[3] or []) if c[0] == tag), None)

    def _hijos(self, n, tag):
        return [c for c in (n[3] or []) if c[0] == tag]

    def _dato(self, n):
        return self.d[n[1]:n[1] + n[2]]

    def _buscar(self, n, tag, acc=None):
        acc = [] if acc is None else acc
        if n[0] == tag:
            acc.append(n)
        for c in n[3] or []:
            self._buscar(c, tag, acc)
        return acc

    def _id(self, n):
        a = self._hijo(self._hijo(self._hijo(n, 0x07d0), 0x05dc), 0x05de)
        return int.from_bytes(self._dato(a), 'little')

    def oculta(self, inst):
        banderas = self._hijo(self._hijo(inst, 0x07d0), 0x07d3)
        return bool(self._dato(banderas)[0] & 1)

    def transformacion(self, inst):
        t = struct.unpack('<13d', self._dato(self._hijo(inst, 0x1966)))
        m = np.eye(4)
        m[:3, :3] = np.array(t[:9]).reshape(3, 3)
        m[:3, 3] = t[9:12]
        if t[12] not in (0.0, 1.0):
            m[:3, :] /= t[12]
        return m

    def definicion(self, inst):
        return int.from_bytes(self._dato(self._hijo(inst, 0x1967)), 'little')

    def piezas(self, inst, m=None, ruta=''):
        """Recorre una instancia y devuelve las piezas (geometria propia) visibles en mm."""
        m = self.transformacion(inst) if m is None else m
        did = self.definicion(inst)
        dfn = self.defs[did]
        ruta = f'{ruta}/{dfn["nombre"]}' if ruta else dfn['nombre']
        out = []
        if dfn['verts'] is not None:
            v = np.c_[dfn['verts'], np.ones(len(dfn['verts']))]
            w = (m @ v.T).T[:, :3] * PULG
            out.append(dict(nombre=dfn['nombre'], ruta=ruta,
                            min=w.min(0).round(1).tolist(), max=w.max(0).round(1).tolist(),
                            n_vertices=len(v)))
        for hijo in dfn['insts']:
            if not self.oculta(hijo):
                out += self.piezas(hijo, m @ self.transformacion(hijo), ruta)
        return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('skp')
    ap.add_argument('--xmin', type=float, default=-1e9, help='filtro de conjunto, mm')
    ap.add_argument('--xmax', type=float, default=1e9)
    ap.add_argument('--salida', required=True)
    a = ap.parse_args()
    mod = ModeloSKP(a.skp)
    piezas = []
    for inst in mod.insts_raiz:
        if mod.oculta(inst):
            continue
        pz = mod.piezas(inst)
        if not pz:
            continue
        x0 = min(p['min'][0] for p in pz)
        x1 = max(p['max'][0] for p in pz)
        if x0 >= a.xmin and x1 <= a.xmax:
            piezas += pz
    for p in piezas:
        p['dim'] = [round(b - c, 1) for b, c in zip(p['max'], p['min'])]
    with open(a.salida, 'w', encoding='utf-8') as f:
        json.dump(dict(fuente=a.skp, unidades='mm', piezas=piezas), f, indent=1, ensure_ascii=False)
    print(f'{len(piezas)} piezas exportadas a {a.salida}')


if __name__ == '__main__':
    main()
