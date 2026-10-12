"""Figuras para la memoria de calculo.

    python modelo/figuras.py
"""
import json
import os
import pickle
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyArrowPatch, Rectangle  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(RAIZ, 'resultados')
FIG = os.path.join(RES, 'figuras')

# paleta de referencia (modo claro)
SUP = '#fcfcfb'
TXT = '#0b0b0b'
TXT2 = '#52514e'
REJ = '#e4e3df'
S1, S2, S3, S4 = '#2a78d6', '#eb6834', '#1baf7a', '#eda100'
SEQ = LinearSegmentedColormap.from_list('azul', ['#cde2fb', '#86b6ef', '#3987e5', '#1c5cab', '#0d366b'])

plt.rcParams.update({
    'figure.facecolor': SUP, 'axes.facecolor': SUP, 'savefig.facecolor': SUP,
    'axes.edgecolor': REJ, 'axes.labelcolor': TXT2, 'xtick.color': TXT2, 'ytick.color': TXT2,
    'axes.grid': True, 'grid.color': REJ, 'grid.linewidth': 0.6, 'grid.linestyle': '-',
    'font.size': 9, 'axes.titlesize': 10, 'axes.titlecolor': TXT, 'axes.titleweight': 'bold',
    'legend.frameon': False, 'lines.linewidth': 2.0, 'axes.spines.top': False, 'axes.spines.right': False,
})


def guardar(fig, nombre):
    os.makedirs(FIG, exist_ok=True)
    ruta = os.path.join(FIG, nombre)
    fig.savefig(ruta, dpi=200, bbox_inches='tight')
    plt.close(fig)
    return ruta


def _ejes_3d(ax, lim):
    ax.set_box_aspect([lim[0][1] - lim[0][0], lim[1][1] - lim[1][0], lim[2][1] - lim[2][0]])
    for k, f in enumerate((ax.set_xlim, ax.set_ylim, ax.set_zlim)):
        f(*lim[k])
    ax.set_axis_off()
    ax.view_init(elev=18, azim=-58)


def fig_modelo(campo):
    fig = plt.figure(figsize=(9, 6.2))
    ax = fig.add_subplot(111, projection='3d')
    colores = {'torre': '#b7d3f6', 'maletero': '#e4e3df'}
    for p in campo['paneles']:
        tipo = 'torre' if p['grupo'].startswith('torre') else 'maletero'
        col = S3 if p['nombre'].startswith('relleno') else colores[tipo]
        if p['nombre'].startswith('lateral aire'):
            col = '#86b6ef'
        polys = [np.array(q) for q in p['quads']]
        pc = Poly3DCollection(polys, facecolor=col, edgecolor='#9c9b96', linewidths=0.08, alpha=0.55)
        ax.add_collection3d(pc)
    for k, d in campo['ptr'].items():
        xyz = np.array(d['xyz'])
        ax.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color=S2, lw=3.2, solid_capstyle='butt')
    _ejes_3d(ax, [(4750, 7730), (-150, 550), (0, 2560)])
    ax.text(6240, -160, 1500, 'PTR 3"x3" frontal', color=TXT, fontsize=8, ha='center')
    ax.text(4800, 500, 2650, 'maleteros (3 x 960 mm)', color=TXT2, fontsize=8)
    ax.text(4700, -150, 300, 'torre izq.', color=TXT2, fontsize=8)
    ax.text(7500, -150, 300, 'torre der.', color=TXT2, fontsize=8)
    ax.set_title('Modelo de elementos finitos: 57 tableros (cascarones) y 2 PTR (vigas)', loc='left')
    return guardar(fig, 'fig01_modelo_3d.png')


def fig_deformada(campo, escala=40.0, titulo='', nombre='fig02_deformada.png'):
    fig = plt.figure(figsize=(9, 6.2))
    ax = fig.add_subplot(111, projection='3d')
    polys, vals = [], []
    for p in campo['paneles']:
        for q, u in zip(p['quads'], p['disp']):
            q, u = np.array(q), np.array(u)
            polys.append(q + escala * u)
            vals.append(np.linalg.norm(u, axis=1).mean())
    vals = np.array(vals)
    vmax = np.percentile(vals, 99.5)
    pc = Poly3DCollection(polys, facecolor=SEQ(np.clip(vals / vmax, 0, 1)), edgecolor='none', alpha=0.9)
    ax.add_collection3d(pc)
    for k, d in campo['ptr'].items():
        xyz = np.array(d['xyz']) + escala * np.array(d['disp'])
        ax.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color=S2, lw=2.6)
    _ejes_3d(ax, [(4750, 7730), (-150, 550), (-50, 2560)])
    sm = plt.cm.ScalarMappable(cmap=SEQ, norm=plt.Normalize(0, vmax))
    cb = fig.colorbar(sm, ax=ax, shrink=0.55, pad=0.02)
    cb.set_label('desplazamiento total (mm)', color=TXT2)
    cb.outline.set_visible(False)
    ax.set_title(f'{titulo} (deformada amplificada x{escala:.0f})', loc='left')
    return guardar(fig, nombre)


def fig_ptr(res):
    fig, axs = plt.subplots(3, 2, figsize=(9.5, 7.6), sharex=True)
    var = [('base', 'proyecto (lateral aire sin apoyo)', S1), ('relleno', 'con relleno bajo lateral aire', S2)]
    for j, ptr in enumerate(('frente', 'fondo')):
        for v, etq, col in var:
            r = res[v]['combos']['ELU-A1 1.2G+1.6Q']['ptr'][ptr]
            x = (np.array(r['x']) - 4800) / 1000
            axs[0, j].plot(x, np.array(r['M']) / 1e6, color=col, label=etq)
            axs[1, j].plot(x, np.array(r['V']) / 1e3, color=col, label=etq)
            rs = res[v]['combos']['ELS G+Q']['ptr'][ptr]
            axs[2, j].plot(x, np.array(rs['uz']), color=col, label=etq)
        axs[0, j].set_title(f'PTR {ptr}', loc='left')
        for i in range(3):
            for xa in (0.0075, 0.6124, 2.2677, 2.8727):
                axs[i, j].axvline(xa, color=TXT2, lw=0.6)
            axs[i, j].axhline(0, color=TXT2, lw=0.6)
        axs[2, j].set_xlabel('posición a lo largo del PTR (m)')
    axs[0, 0].set_ylabel('momento Mu (kN·m)\n1.2G + 1.6Q')
    axs[1, 0].set_ylabel('cortante Vu (kN)\n1.2G + 1.6Q')
    axs[2, 0].set_ylabel('desplazamiento vertical (mm)\nG + Q')
    axs[0, 0].legend(loc='upper right', fontsize=8)
    fig.text(0.01, 0.005, 'Líneas verticales: laterales exterior y aire de cada torre.', color=TXT2, fontsize=8)
    fig.tight_layout()
    return guardar(fig, 'fig04_ptr_diagramas.png')


def fig_reparto(res):
    elems = ['lateral exterior', 'lateral aire', 'trasero 15 mm', 'travesano superior']
    var = [('base', 'proyecto'), ('uniones rigidas', 'uniones 10x mas rigidas'), ('relleno', 'con relleno')]
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.4), sharey=True)
    for j, ptr in enumerate(('frente', 'fondo')):
        w = 0.26
        for i, (v, etq) in enumerate(var):
            d = res[v]['combos']['ELS G+Q']['apoyos_ptr'][f'{ptr}|torre izq']
            vals = [d.get(e, 0.0) / 1e3 for e in elems]
            xs = np.arange(len(elems)) + (i - 1) * (w + 0.02)
            axs[j].bar(xs, vals, width=w, color=[S1, S3, S2][i], label=etq)
        axs[j].set_xticks(np.arange(len(elems)))
        axs[j].set_xticklabels([e.replace('travesano', 'travesaño') for e in elems], fontsize=8)
        axs[j].set_title(f'PTR {ptr}: reacción en la torre izquierda (G + Q)', loc='left')
        axs[j].grid(axis='x', visible=False)
    axs[0].set_ylabel('reacción (kN)')
    axs[1].legend(loc='upper right', fontsize=8)
    fig.tight_layout()
    return guardar(fig, 'fig05_reparto_apoyos.png')


def fig_esquema():
    """Alzado frontal esquematico con cotas y trayectoria de carga."""
    fig, ax = plt.subplots(figsize=(9.5, 6.4))
    ax.set_aspect('equal')
    ax.axis('off')
    ax.grid(False)
    tab = dict(facecolor='#cde2fb', edgecolor='#52514e', lw=0.7)
    gris = dict(facecolor='#e4e3df', edgecolor='#52514e', lw=0.7)
    x0 = 4800
    for xt, lado in ((4800, 'izq'), (7060, 'der')):
        ext = xt if lado == 'izq' else xt + 605
        aire = xt + 605 if lado == 'izq' else xt
        ax.add_patch(Rectangle((xt - x0, 0), 620, 100, **gris))                        # zocalo
        ax.add_patch(Rectangle((xt - x0, 100), 620, 15, **tab))                        # piso
        ax.add_patch(Rectangle((ext - x0, 115), 15, 1455, **tab))                      # lateral exterior
        ax.add_patch(Rectangle((aire - x0, 115), 15, 335, **tab))                      # panel inferior
        ax.add_patch(Rectangle((xt - x0 + (15 if lado == 'izq' else 0), 450), 605, 15, **tab))   # cubierta
        ax.add_patch(Rectangle((aire - x0, 670), 15, 900, facecolor='#86b6ef', edgecolor='#52514e', lw=0.7))
        ax.add_patch(Rectangle((xt - x0 + 15, 670), 590, 30, **tab))                   # tope + amarres
        ax.add_patch(Rectangle((xt - x0 + 15, 1555), 590, 15, **tab))                  # travesano
        ax.add_patch(Rectangle((aire - x0 - 2, 465), 19, 205, facecolor='none', edgecolor=S2, lw=1.4, hatch='////'))
        for z, t in ((170, 'cajones'), (1100, 'puerta')):
            ax.text(xt - x0 + 310, z, t, ha='center', va='center', fontsize=7, color=TXT2)
    ax.add_patch(Rectangle((0, 1570), 2880, 76.2, facecolor=S2, edgecolor='#52514e', lw=0.7))
    for i in range(3):
        xa = i * 960
        ax.add_patch(Rectangle((xa, 1646.2), 960, 870, facecolor='none', edgecolor='#52514e', lw=0.9))
        ax.add_patch(Rectangle((xa, 1646.2), 15, 870, **gris))
        ax.add_patch(Rectangle((xa + 945, 1646.2), 15, 870, **gris))
        ax.add_patch(Rectangle((xa + 15, 1646.2), 930, 15, **gris))
        ax.add_patch(Rectangle((xa + 15, 2501.2), 930, 15, **gris))
        ax.text(xa + 480, 2080, f'maletero {i + 1}\n960 x 870 x 600', ha='center', va='center', fontsize=8, color=TXT)
        for xs in (xa + 7.5, xa + 952.5):
            ax.add_patch(FancyArrowPatch((xs, 1900), (xs, 1660), arrowstyle='-|>', mutation_scale=8, color=S1, lw=1.0))
    ax.text(1440, 1608, 'PTR 3"x3" (frente y fondo), L = 2880 mm', ha='center', va='center', fontsize=8,
            color=TXT, fontweight='bold')
    # cotas
    def cota_h(xa, xb, z, txt):
        ax.annotate('', (xa, z), (xb, z), arrowprops=dict(arrowstyle='<->', color=TXT2, lw=0.7))
        ax.text(0.5 * (xa + xb), z + 25, txt, ha='center', fontsize=7.5, color=TXT2)
    cota_h(620, 2260, 1300, 'hueco central 1640 mm')
    cota_h(7.5, 2872.5, 2620, 'claro efectivo del PTR frontal en el proyecto: 2865 mm (entre laterales exteriores)')
    cota_h(612.5, 2267.5, 1460, 'claro con relleno: 1655 mm (entre laterales aire)')
    ax.text(700, 560, 'hueco de 205 mm\nsin tablero bajo\nel lateral aire', fontsize=7.5, color=S2, va='center')
    ax.text(2260 - 15, 560, 'hueco de 205 mm', fontsize=7.5, color=S2, va='center', ha='right')
    ax.text(625, 1000, 'lateral aire\n900 mm', fontsize=7, color=TXT, va='center')
    ax.text(-20, 800, 'lateral exterior\n1455 mm', fontsize=7, color=TXT, va='center', ha='right')
    ax.set_xlim(-330, 3000)
    ax.set_ylim(-60, 2700)
    ax.set_title('Alzado frontal esquemático (mm). Maleteros sobre PTR y torres', loc='left')
    return guardar(fig, 'fig03_esquema_alzado.png')


def southwell(curva):
    """Estimacion del factor critico por la recta de Southwell: u/lambda contra u."""
    pts = [(c['lam'], c['abombamiento_lateral']) for c in curva if c['lam'] >= 0.49]
    if len(pts) < 2:
        return None
    lam, u = np.array(pts).T
    pend = np.polyfit(u, u / lam, 1)[0]
    return 1.0 / pend if pend > 0 else None


def fig_pandeo(pandeo):
    fig, axs = plt.subplots(1, 2, figsize=(9.5, 3.6), sharey=True)
    cols = {'proyecto': S1, 'con relleno': S2, 'relleno y entrepaño': S3}
    for d in pandeo:
        var = d['variante'].split(',')[0]
        ax = axs[0] if 'ELU' in d['variante'] else axs[1]
        c = d['curva']
        x = [0.0] + [k['abombamiento_lateral'] for k in c]
        y = [0.0] + [k['lam'] for k in c]
        ax.plot(x, y, color=cols[var], marker='o', ms=3.5, label=var)
        if not d['convergio_hasta_max']:
            txt = 'corrida detenida' if d.get('nota') else 'sin convergencia\na mayor λ'
            ax.annotate(txt, (x[-1], y[-1]), textcoords='offset points', xytext=(5, -4), fontsize=7, color=TXT2)
    for ax, t in zip(axs, ('Corto plazo: 1.35G + 1.5Q, E/γM', 'Largo plazo: G + 0.8Q, E/(1 + kdef)')):
        ax.axhline(1.0, color=TXT2, lw=0.8)
        ax.set_title(t, loc='left')
        ax.set_xlabel('abombamiento máximo de laterales (mm)')
        ax.set_xlim(left=0)
    axs[0].set_ylabel('factor de carga λ')
    axs[0].legend(fontsize=8, loc='lower right')
    fig.tight_layout()
    return guardar(fig, 'fig06_pandeo.png')


def fig_modo(pandeo):
    """Mapa del abombamiento del lateral exterior izquierdo en el ultimo paso del proyecto (corto plazo)."""
    d = next((k for k in pandeo if k['variante'].startswith('proyecto') and 'ELU' in k['variante']
              and k.get('campo_final')), None)
    if d is None:
        return None
    c = d['campo_final'].get('ESPCL-LD-02|torre izq')
    X, U = np.array(c['xyz']), np.array(c['u'])
    y, z, ux = X[:, 1], X[:, 2], U[:, 0]
    # quitar el movimiento de cuerpo rigido: plano por las esquinas
    esq = [np.argmin((y - yy) ** 2 + (z - zz) ** 2) for yy in (y.min(), y.max()) for zz in (z.min(), z.max())]
    A = np.c_[np.ones(len(y)), y, z]
    coef = np.linalg.lstsq(A[esq], ux[esq], rcond=None)[0]
    w = np.abs(ux - A @ coef)
    fig, ax = plt.subplots(figsize=(5.2, 6.2))
    ax.grid(False)
    tc = ax.tricontourf(y, z, w, levels=12, cmap=SEQ)
    for zz, t in ((692.5, 'entrepaño'), (457.5, 'cubierta de cajones'), (1562.5, 'travesaño superior')):
        ax.axhline(zz, color=TXT2, lw=0.7)
        ax.text(y.max() + 8, zz, t, fontsize=7.5, color=TXT2, va='center')
    ax.annotate('canto frontal\nsin arriostrar', (y.min(), 1120), xytext=(y.min() + 140, 1250), fontsize=8,
                color=TXT, arrowprops=dict(arrowstyle='->', color=TXT, lw=0.8))
    ax.set_aspect('equal')
    ax.set_xlabel('fondo, y (mm)  [frente a la izquierda]')
    ax.set_ylabel('altura, z (mm)')
    cb = fig.colorbar(tc, ax=ax, shrink=0.7, pad=0.36)
    cb.set_label('abombamiento fuera del plano (mm)', color=TXT2)
    cb.outline.set_visible(False)
    ax.set_title(f'Lateral exterior, proyecto, λ = {d["lambda_ultimo"]:.1f}', loc='left')
    return guardar(fig, 'fig07_modo_pandeo.png')


def main():
    with open(os.path.join(RES, 'resultados.pkl'), 'rb') as f:
        res = pickle.load(f)
    rutas = [fig_modelo(res['base']['combos']['ELS G+Q']['campo']),
             fig_deformada(res['base']['combos']['ELS G+Q']['campo'], titulo='Proyecto, servicio G + Q'),
             fig_deformada(res['relleno']['combos']['ELS G+Q']['campo'], titulo='Con relleno, servicio G + Q',
                           nombre='fig02b_deformada_relleno.png'),
             fig_esquema(), fig_ptr(res), fig_reparto(res)]
    pj = os.path.join(RES, 'pandeo.json')
    if os.path.exists(pj):
        pdat = json.load(open(pj))
        rutas += [fig_pandeo(pdat), fig_modo(pdat)]
    for r in rutas:
        print(r)


if __name__ == '__main__':
    main()
