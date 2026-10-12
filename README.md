# Cálculo estructural: closet con maleteros sobre PTR de 30 x 30 mm

Modelo tridimensional de elementos finitos del closet de `datos/origen/closet_pedido_mx.skp`
con la modificación de dos PTR de 30 x 30 mm (3 x 3 cm) bajo los maleteros, apoyados en las torres.
Revisión 2: la primera versión suponía un PTR de 3" x 3"; esta la sustituye.

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

* El PTR de 30 x 30 mm no puede cargar los maleteros como viga: como viga simple entre las
  torres necesitaría 2.7 veces su resistencia. En el modelo, los tres maleteros atornillados
  entre sí trabajan como una caja rígida y el tubo se deforma con ellos.
* Tal como está diseñado, el mueble no cumple con ningún calibre (18, 16 o 14): la flecha
  del frente queda entre L/112 y L/121 a largo plazo, el tablero trasero de las torres y sus
  uniones se sobrecargan y los laterales exteriores se pandean con la carga sostenida.
* La causa de fondo: el lateral interior de cada torre ("lateral aire") no llega al piso
  (hueco de 205 mm) y cuelga de tornillos al trasero.
* Solución recomendada: relleno de 15 mm (585 x 205 mm) bajo cada lateral aire, entrepaño
  fijo intermedio a 1120 mm en cada torre, solera de acero de 3" x 3/16" bajo el PTR sobre cada torre
  (el canto de 15 mm queda al límite bajo un tubo de 30 mm), maleteros atornillados entre sí
  y anclaje al muro. Con eso el tubo de 30 x 30 mm cumple, incluso en cal. 18.
