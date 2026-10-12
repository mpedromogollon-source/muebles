"""Propiedades geometricas de PTR cuadrado con esquinas redondeadas."""
import math

import numpy as np


def ptr_cuadrado(B, t, r_ext=None, paso=None):
    """Propiedades de un tubo cuadrado de lado B y pared t (mm).

    El radio exterior de esquina se toma 2t (AISC usa 1.5t a 2t). A, I, Z se
    integran numericamente sobre una reticula; J y Cw por formulas de pared delgada.
    """
    r_ext = 2.0 * t if r_ext is None else r_ext
    paso = t / 40 if paso is None else paso          # el espesor queda en un numero entero de celdas
    r_int = max(r_ext - t, 0.0)
    n = int(round(B / paso))
    c = (np.arange(n) + 0.5) * paso - B / 2
    X, Y = np.meshgrid(c, c)

    def dentro(X, Y, a, r):
        ax, ay = np.abs(X), np.abs(Y)
        en_caja = (ax <= a) & (ay <= a)
        esquina = (ax > a - r) & (ay > a - r)
        dist = np.hypot(ax - (a - r), ay - (a - r))
        return en_caja & ~(esquina & (dist > r))

    acero = dentro(X, Y, B / 2, r_ext) & ~dentro(X, Y, B / 2 - t, r_int)
    dA = paso * paso
    A = acero.sum() * dA
    I = (Y[acero] ** 2).sum() * dA
    S = I / (B / 2)
    Z = 2 * (np.abs(Y[acero & (Y > 0)])).sum() * dA
    rm = r_ext - t / 2
    Am = (B - t) ** 2 - (4 - math.pi) * rm ** 2
    p = 4 * (B - t) - (8 - 2 * math.pi) * rm
    J = 4 * Am ** 2 * t / p
    return dict(B=B, t=t, r_ext=r_ext, A=A, I=I, S=S, Z=Z, J=J, r=math.sqrt(I / A),
                masa_kg_m=A * 1e-6 * 7850.0)


if __name__ == '__main__':
    from parametros import PERFILES, perfil_diseno
    for nom in PERFILES:
        B, t = perfil_diseno(nom)
        p = ptr_cuadrado(B, t)
        print(f"{nom:14s} t={t:5.3f}  A={p['A']/100:6.2f} cm2  I={p['I']/1e4:6.1f} cm4  "
              f"S={p['S']/1e3:5.2f} cm3  Z={p['Z']/1e3:5.2f} cm3  J={p['J']/1e4:6.1f} cm4  "
              f"{p['masa_kg_m']:.2f} kg/m")
