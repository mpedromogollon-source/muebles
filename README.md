# Cálculo estructural: closet con maleteros sobre PTR 3"x3"

Modelo tridimensional de elementos finitos del closet de `datos/origen/closet_pedido_mx.skp`
con la modificación de dos PTR 3"x3" bajo los maleteros, apoyados en las torres.

La memoria de cálculo completa está en
[`resultados/memoria_calculo_closet_PTR.pdf`](resultados/memoria_calculo_closet_PTR.pdf).

## Contenido

| Ruta | Qué hace |
|---|---|
| `datos/origen/` | Archivo SketchUp y diagrama de corte originales |
| `herramientas/skp_lector.py` | Lee el formato binario de SketchUp 2021+ y exporta las piezas visibles con sus medidas reales |
| `datos/piezas_closet.json` | Piezas del conjunto armado (coinciden con las 89 del diagrama de corte) |
| `modelo/parametros.py` | Materiales, cargas, rigideces y criterios adoptados |
| `modelo/perfiles.py` | Propiedades del PTR cuadrado por calibre |
| `modelo/modelo_fe.py` | Modelo OpenSeesPy: tableros como cascarones, PTR como vigas, uniones y contactos |
| `modelo/analisis.py` | Combinaciones de carga y posproceso |
| `modelo/ejecutar.py` | Corre todas las variantes y guarda `resultados/resultados.json` |
| `modelo/verificaciones.py` | Revisiones AISC 360-16 (PTR) y EN 1995 (tablero, uniones), volteo y anclaje |
| `modelo/pandeo.py` | Análisis con no linealidad geométrica (estabilidad) |
| `modelo/figuras.py`, `modelo/memoria.py` | Figuras y memoria en PDF |

## Cómo reproducir

```bash
pip install openseespy numpy matplotlib reportlab pillow
python herramientas/skp_lector.py datos/origen/closet_pedido_mx.skp --xmin 4700 --xmax 7800 \
    --salida datos/piezas_closet.json
python modelo/ejecutar.py          # ~2 min con 4 núcleos
python modelo/pandeo.py            # análisis no lineal, tarda bastante más
python modelo/verificaciones.py
python modelo/figuras.py
python modelo/memoria.py
```

`resultados/resultados.pkl` (campos de desplazamiento para figuras) no se versiona; lo
genera `ejecutar.py`.

## Resultado en breve

* El PTR 3"x3" cal. 14 trabaja al 22 % de su resistencia a flexión y su flecha a largo
  plazo es L/560: es suficiente.
* El lateral interior de cada torre ("lateral aire") no llega al piso: hay un hueco de
  205 mm bajo él. Por eso casi no toma carga y el PTR frontal trabaja entre los laterales
  exteriores (2.87 m) con la reacción concentrada en su esquina superior frontal.
* Lo que gobierna es la estabilidad del canto frontal libre de los laterales: en el
  proyecto, bajo carga sostenida con fluencia, el análisis no lineal deja de converger
  entre λ = 1.0 y 1.5 y el lateral exterior se abomba 22 mm.
* Solución recomendada: relleno de 15 mm (585 x 205 mm) bajo cada lateral aire más un
  entrepaño fijo intermedio a 1120 mm en cada torre. Con eso el abombamiento baja a
  0.6 mm, el análisis llega a λ > 3.9 y se cumplen las verificaciones de resistencia y
  estabilidad.
* El mueble debe anclarse al muro (se voltea sin anclaje con 0.21 g de aceleración horizontal).
