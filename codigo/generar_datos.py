"""Genera transacciones sintéticas reproducibles, sin datos personales."""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'datos'
CIUDADES = ['Bogotá', 'Medellín', 'Cali', 'Barranquilla', 'Bucaramanga', 'Pereira']
PRODUCTOS = ['Portátil', 'Audífonos', 'Teclado', 'Mouse', 'Monitor', 'Impresora', 'Tablet', 'Cámara']
PRECIOS = [2500000, 120000, 85000, 55000, 850000, 650000, 1100000, 430000]


def main():
    DATA.mkdir(exist_ok=True)
    rng = random.Random(20260818)
    sizes = (10000, 100000, 500000)
    files = {n: (DATA / f'ventas_{n}.csv').open('w', newline='', encoding='utf-8') for n in sizes}
    writers = {n: csv.writer(files[n]) for n in sizes}
    try:
        for writer in writers.values():
            writer.writerow(['id_venta', 'fecha', 'ciudad', 'producto', 'cantidad', 'precio_unitario'])
        for i in range(1, 500001):
            idx = rng.randrange(len(PRODUCTOS))
            row = [
                i,
                (date(2025, 1, 1) + timedelta(days=rng.randrange(365))).isoformat(),
                rng.choice(CIUDADES),
                PRODUCTOS[idx],
                rng.randint(1, 8),
                PRECIOS[idx],
            ]
            for n in sizes:
                if i <= n:
                    writers[n].writerow(row)
    finally:
        for file in files.values():
            file.close()
    print('CSV generados correctamente: ventas_10000.csv, ventas_100000.csv y ventas_500000.csv')
    print(f'Datos guardados en: {DATA}')


if __name__ == '__main__':
    main()
