"""Parametros de materiales, cargas y criterios adoptados para el calculo.

Unidades: N, mm, MPa (N/mm2) salvo indicacion.
"""
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

# Perfiles tubulares cuadrados: (lado, espesor de pared) en mm.
# El cliente indica PTR de 3 x 3 cm. El calibre no se conoce: se toma cal. 16 como base
# y se revisan cal. 18 y cal. 14. El 3"x3" se conserva solo como alternativa de comparacion.
PERFILES = {
    '30x30 cal. 18': (30.0, 1.214),
    '30x30 cal. 16': (30.0, 1.519),
    '30x30 cal. 14': (30.0, 1.897),
    '3"x3" cal. 14': (76.2, 1.897),
}
PERFIL_BASE = '30x30 cal. 16'
LADO_BASE = PERFILES[PERFIL_BASE][0]
# AISC 360-16 B4.2: espesor de diseno 0.93 t nominal para tubo soldado (ERW) que no es
# ASTM A1085, como el PTR comercial (A500 / NMX-B-199). Se usa en resistencia y rigidez.
FACTOR_ESPESOR = 0.93


def perfil_diseno(nombre):
    """(lado, espesor de diseno) del perfil indicado."""
    lado, t_nom = PERFILES[nombre]
    return lado, FACTOR_ESPESOR * t_nom

# Posicion de los PTR: a paño frontal y a paño trasero del mueble, longitud total
# 2880 mm, apoyados sobre las torres; los maleteros se elevan el lado del PTR.
PTR_X = (4800.0, 7680.0)
Z_TOPE_TORRES = 1570.0
Y_FRENTE_MUEBLE, Y_FONDO_MUEBLE = -105.2, 494.8


def huellas_ptr(lado):
    """Rango en y de cada PTR (frente y fondo) para un lado dado."""
    return {'frente': (Y_FRENTE_MUEBLE, Y_FRENTE_MUEBLE + lado), 'fondo': (Y_FONDO_MUEBLE - lado, Y_FONDO_MUEBLE)}


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

# Pija de fijacion del PTR (tornillo autorroscante #10, d = 4.8 mm) a traves de la pared del tubo hacia un
# tablero de 15 mm. Rigidez EN 1995-1-1 7.1: Kser = 2 rho_m^1.5 d / 23 (acero contra madera).
PIJA = dict(d=4.8, t=15.0, fu=400.0)
PIJA['Kser'] = 2 * TABLERO['densidad'] ** 1.5 * PIJA['d'] / 23.0
# Tornillo pasante de union de modulos M6 (entre costados de maletero y para el suplemento de canto).
TORNILLO_M6 = dict(d=6.0, t=15.0, fu=400.0)


def fh_tablero(d, t):
    """Resistencia al aplastamiento en tablero de particulas, EN 1995-1-1 ec. 8.22 (MPa)."""
    return 65.0 * d ** -0.7 * t ** 0.1


def johansen_placa_delgada(d, t, fu):
    """Fv,Rk de un conector en cortante simple, placa de acero delgada contra tablero (EN 1995 8.2.3, ec. 8.9)."""
    fh = fh_tablero(d, t)
    My = 0.3 * fu * d ** 2.6
    return min(0.4 * fh * t * d, 1.15 * (2 * My * fh * d) ** 0.5)


def johansen_tablero_tablero(d, t1, t2, fu):
    """Fv,Rk de un perno en cortante simple entre dos tableros iguales (EN 1995 8.2.2, ec. 8.6, sin efecto soga)."""
    f1 = f2 = fh_tablero(d, min(t1, t2))
    b = f2 / f1
    My = 0.3 * fu * d ** 2.6
    r = t2 / t1
    modos = [f1 * t1 * d, f2 * t2 * d,
             f1 * t1 * d / (1 + b) * ((b + 2 * b * b * (1 + r + r * r) + b ** 3 * r * r) ** 0.5 - b * (1 + r)),
             1.05 * f1 * t1 * d / (2 + b) * ((2 * b * (1 + b) + 4 * b * (2 + b) * My / (f1 * d * t1 ** 2)) ** 0.5 - b),
             1.05 * f1 * t2 * d / (1 + 2 * b) * ((2 * b * b * (1 + b) + 4 * b * (1 + 2 * b) * My / (f1 * d * t2 ** 2)) ** 0.5 - b),
             1.15 * (2 * b / (1 + b)) ** 0.5 * (2 * My * f1 * d) ** 0.5]
    return min(modos)


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

