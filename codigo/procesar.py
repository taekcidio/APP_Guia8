"""Comparación reproducible de ejecución secuencial y paralela local.

IMPORTANTE: este programa usa procesos independientes EN UN ÚNICO EQUIPO.
No corresponde a un clúster distribuido entre diferentes máquinas.
Además, al terminar genera automáticamente las gráficas en PNG.
"""
import argparse
import csv
import json
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'datos'
RESULTS = ROOT / 'resultados'
GRAPHS = ROOT / 'graficas'


def cargar_csv(path):
    with path.open('r', newline='', encoding='utf-8') as stream:
        return [
            (
                row['fecha'][:7],
                row['ciudad'],
                row['producto'],
                int(row['cantidad']),
                int(row['precio_unitario']),
            )
            for row in csv.DictReader(stream)
        ]


def procesar_particion(rows):
    city, prod, month = defaultdict(int), defaultdict(int), defaultdict(int)
    for fecha, ciudad, producto, cantidad, precio in rows:
        subtotal = cantidad * precio
        city[ciudad] += subtotal
        prod[producto] += cantidad
        month[fecha] += subtotal
    return dict(city), dict(prod), dict(month)


def consolidar(parciales):
    totals = [defaultdict(int), defaultdict(int), defaultdict(int)]
    for parcial in parciales:
        for target, source in zip(totals, parcial):
            for key, amount in source.items():
                target[key] += amount
    return [dict(group) for group in totals]


def particionar(rows, n):
    size = (len(rows) + n - 1) // n
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def comparar_archivo(csv_path, workers):
    start = time.perf_counter()
    rows = cargar_csv(csv_path)
    original = procesar_particion(rows)
    ts = time.perf_counter() - start

    start = time.perf_counter()
    rows_par = cargar_csv(csv_path)
    parts = particionar(rows_par, workers)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        partials = list(pool.map(procesar_particion, parts))
    merged = consolidar(partials)
    tp = time.perf_counter() - start

    assert list(original) == merged, 'La consolidación paralela difiere del cálculo secuencial'
    by_city, by_product, by_month = merged
    top_five = sorted(by_product.items(), key=lambda x: (-x[1], x[0]))[:5]
    return {
        'archivo': csv_path.name,
        'registros': len(rows),
        'procesos': len(parts),
        'tiempo_secuencial_s': round(ts, 5),
        'tiempo_paralelo_s': round(tp, 5),
        'aceleracion': round(ts / tp, 4) if tp else None,
        'verificacion': 'COINCIDEN',
        'ingresos_por_ciudad': dict(sorted(by_city.items())),
        'top_5_productos_por_unidades': dict(top_five),
        'ingresos_por_mes': dict(sorted(by_month.items())),
        'ingresos_totales': sum(by_city.values()),
        'unidades_totales': sum(by_product.values()),
    }


def exportar_csv_y_json(resultados):
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / 'resultados_completos.json').write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    with (RESULTS / 'comparativa_tiempos.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'registros', 'procesos', 'tiempo_secuencial_s',
            'tiempo_paralelo_s', 'aceleracion', 'verificacion'
        ])
        for r in resultados:
            writer.writerow([
                r['registros'], r['procesos'], r['tiempo_secuencial_s'],
                r['tiempo_paralelo_s'], r['aceleracion'], r['verificacion']
            ])

    largest = resultados[-1]
    tablas = [
        ('ingresos_ciudad.csv', 'ingresos_por_ciudad', 'ciudad'),
        ('productos_top5.csv', 'top_5_productos_por_unidades', 'producto'),
        ('ingresos_mensuales.csv', 'ingresos_por_mes', 'mes'),
    ]
    for filename, key, x_title in tablas:
        with (RESULTS / filename).open('w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow([x_title, 'valor'])
            w.writerows(largest[key].items())


def formatear_pesos(x, pos):
    if x >= 1_000_000_000:
        return f'{x/1_000_000_000:.1f}B'
    if x >= 1_000_000:
        return f'{x/1_000_000:.0f}M'
    if x >= 1_000:
        return f'{x/1_000:.0f}K'
    return str(int(x))


def generar_graficas(resultados):
    GRAPHS.mkdir(exist_ok=True)
    largest = resultados[-1]
    money_fmt = FuncFormatter(formatear_pesos)

    # 1. Ingresos por ciudad
    ciudades = list(largest['ingresos_por_ciudad'].keys())
    valores_ciudad = list(largest['ingresos_por_ciudad'].values())
    plt.figure(figsize=(10, 6))
    bars = plt.bar(ciudades, valores_ciudad)
    plt.title('Ingresos por ciudad')
    plt.xlabel('Ciudad')
    plt.ylabel('Ingresos')
    plt.gca().yaxis.set_major_formatter(money_fmt)
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(GRAPHS / '01_ingresos_por_ciudad.png', dpi=180, bbox_inches='tight')
    plt.close()

    # 2. Top 5 productos por unidades
    productos = list(largest['top_5_productos_por_unidades'].keys())
    valores_prod = list(largest['top_5_productos_por_unidades'].values())
    plt.figure(figsize=(10, 6))
    plt.bar(productos, valores_prod)
    plt.title('Top 5 productos más vendidos')
    plt.xlabel('Producto')
    plt.ylabel('Unidades vendidas')
    plt.xticks(rotation=20)
    plt.tight_layout()
    plt.savefig(GRAPHS / '02_top5_productos.png', dpi=180, bbox_inches='tight')
    plt.close()

    # 3. Ingresos mensuales
    meses = list(largest['ingresos_por_mes'].keys())
    valores_mes = list(largest['ingresos_por_mes'].values())
    plt.figure(figsize=(11, 6))
    plt.plot(meses, valores_mes, marker='o')
    plt.title('Ingresos mensuales')
    plt.xlabel('Mes')
    plt.ylabel('Ingresos')
    plt.gca().yaxis.set_major_formatter(money_fmt)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(GRAPHS / '03_ingresos_mensuales.png', dpi=180, bbox_inches='tight')
    plt.close()

    # 4. Comparación de tiempos
    etiquetas = [f"{r['registros']:,}".replace(',', '.') for r in resultados]
    tiempos_seq = [r['tiempo_secuencial_s'] for r in resultados]
    tiempos_par = [r['tiempo_paralelo_s'] for r in resultados]
    x = range(len(etiquetas))
    width = 0.35
    plt.figure(figsize=(10, 6))
    plt.bar([i - width/2 for i in x], tiempos_seq, width=width, label='Secuencial')
    plt.bar([i + width/2 for i in x], tiempos_par, width=width, label='Paralelo')
    plt.title('Comparación de tiempos de ejecución')
    plt.xlabel('Cantidad de registros')
    plt.ylabel('Tiempo (segundos)')
    plt.xticks(list(x), etiquetas)
    plt.legend()
    plt.tight_layout()
    plt.savefig(GRAPHS / '04_comparacion_tiempos.png', dpi=180, bbox_inches='tight')
    plt.close()

    # 5. Aceleración
    aceleraciones = [r['aceleracion'] for r in resultados]
    plt.figure(figsize=(10, 6))
    plt.bar(etiquetas, aceleraciones)
    plt.axhline(1, linestyle='--')
    plt.title('Aceleración (Ts/Tp)')
    plt.xlabel('Cantidad de registros')
    plt.ylabel('Aceleración')
    plt.tight_layout()
    plt.savefig(GRAPHS / '05_aceleracion.png', dpi=180, bbox_inches='tight')
    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Guía 8: simulación de procesamiento paralelo local con gráficas')
    parser.add_argument('--procesos', type=int, default=3, help='Cantidad de procesos paralelos a usar')
    args = parser.parse_args()
    if args.procesos < 2:
        parser.error('Se requieren al menos dos procesos')

    resultados = []
    for n in (10000, 100000, 500000):
        path = DATA / f'ventas_{n}.csv'
        if not path.exists():
            parser.error(f'Falta {path.name}. Ejecuta primero generar_datos.py')
        result = comparar_archivo(path, args.procesos)
        resultados.append(result)
        print(
            f"{n:>7,} registros | secuencial={result['tiempo_secuencial_s']:.5f}s | "
            f"paralelo={result['tiempo_paralelo_s']:.5f}s | "
            f"aceleración={result['aceleracion']:.3f} | {result['verificacion']}"
        )

    exportar_csv_y_json(resultados)
    generar_graficas(resultados)
    print(f'Resultados tabulares guardados en: {RESULTS}')
    print(f'Gráficas generadas automáticamente en: {GRAPHS}')


if __name__ == '__main__':
    main()
