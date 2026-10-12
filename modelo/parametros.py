"""Parametros de materiales, cargas y criterios adoptados para el calculo.

Unidades: N, mm, MPa (N/mm2) salvo indicacion.
"""
import math

GRAV = 9.81  # m/s2, para pasar kg a N

# Tablero de particulas melaminico 15 mm (calidad interior tipo EN 312 P2).
# P2 no es grado estructural; se adoptan valores reducidos a partir de EN 12369-1
# (P4, 13-20 mm) escalados al minimo de P2 de EN 312 (fm >= 11 MPa, Em >= 1600 MPa).
TABLERO = dict(
    espesor=15.0,
    densidad=680.0,          # kg/m3
    E=2000.0,                # MPa, modulo medio (flexion y plano)
    nu=0.25,
    fm_k=10.0,               # MPa, flexion
    ft_k=6.5,                # MPa, traccion en el plano
    fc_k=8.5,                # MPa, compresion en el plano (canto)
    fv_k=4.8,                # MPa, cortante de panel
    kmod_permanente=0.30,    # EN 1995-1-1 tabla 3.1, tablero P4/P5, clase de servicio 1
    kmod_largo=0.45,
    kmod_corto=0.85,
    kdef=2.25,               # EN 1995-1-1 tabla 3.2, P4/P5 clase de servicio 1
    gamma_M=1.3,
    psi2_almacen=0.8,        # EN 1990 categoria E (almacenamiento)
    recargo_herrajes=1.05,   # cubrecanto, tornilleria y herrajes menores
)

# Acero del PTR (perfil tubular cuadrado). Se adopta Fy = 250 MPa por no conocer el
# grado; un ASTM A500 Gr. B (Fy = 317 MPa) da resistencias mayores.
ACERO = dict(E=200000.0, G=77200.0, Fy=250.0, Fu=400.0, densidad=7850.0)

# PTR 3"x3" (76.2 mm). Calibres comerciales en Mexico (espesor de pared, mm).
PTR_LADO = 76.2
PTR_CALIBRES = {'cal. 14': 1.897, 'cal. 12': 2.657, 'cal. 11': 3.038, '3/16"': 4.763}
PTR_CALIBRE_BASE = 'cal. 14'

# Posicion de los PTR: a paño frontal y a paño trasero del mueble, longitud total
# 2880 mm, apoyados sobre las torres; los maleteros se elevan 76.2 mm.
PTR_X = (4800.0, 7680.0)
PTR_Y_FRENTE = (-105.2, -105.2 + PTR_LADO)
PTR_Y_FONDO = (494.8 - PTR_LADO, 494.8)
Z_TOPE_TORRES = 1570.0

# Cargas variables adoptadas (uso de almacenamiento domestico).
CARGAS = dict(
    q_maletero=1.5e-3,       # N/mm2 = 1.5 kN/m2 (150 kg/m2) sobre el piso de cada maletero
    q_repisa_torre=1.5e-3,   # N/mm2 sobre cubierta de cajones y entrepaño de la torre
    q_cajon_kg=25.0,         # kg de contenido por cajon
    q_barra=0.40,            # N/mm = 0.40 kN/m, barra de colgar en el hueco central (supuesta)
    z_barra=1450.0,          # altura supuesta de la barra, mm
    c_sismico=0.5,           # coeficiente horizontal adoptado para anclaje al muro (ajustar al sitio)
)

# Conector tipico de carcasa en melamina: tornillo confirmat 7 x 50 mm.
# Valores caracteristicos adoptados (verificar con datos del fabricante).
CONFIRMAT = dict(Fv_k=1000.0, Fax_k=800.0)  # N

# Rigidez de uniones entre tableros (tornillos a ~150 mm, Kser ~ 1500 N/mm c/u).
K_UNION = 10.0       # N/mm por mm de linea de union (tornillo: corte y traccion)
K_APOYO = 150.0      # N/mm por mm: canto de tablero apoyado en cara (compresion directa)
K_CONTACTO = 1.0e4   # N/mm por nodo, apoyo directo tablero-PTR

# Tamano maximo de elemento de malla
H_MALLA = 75.0


def resistencia_diseno(fk, kmod):
    return kmod * fk / TABLERO['gamma_M']


def peso_tablero_N_mm2():
    """Peso propio por unidad de area del tablero, N/mm2."""
    t = TABLERO
    return t['densidad'] * GRAV * t['espesor'] * 1e-9 * t['recargo_herrajes']


assert math.isclose(PTR_LADO, 3 * 25.4)
