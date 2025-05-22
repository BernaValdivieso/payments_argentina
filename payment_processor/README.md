# Payment Processor

Aplicación web para procesar archivos Excel de remuneración, que calcula automáticamente el tipo de pago basado en los costos de piezas y horas.

## Características

- Procesamiento de archivos Excel (.xlsx, .xls)
- Cálculo automático del tipo de pago (Piezas/Horas)
- Actualización automática del costo total
- Formato de moneda para columnas de costo
- Filtros automáticos en todas las columnas
- Ajuste automático del ancho de las columnas

## Requisitos

- Python 3.8+
- Flask
- pandas
- openpyxl
- gunicorn

## Instalación

1. Clonar el repositorio:
```bash
git clone https://github.com/BernaValdivieso/payments_argentina.git
cd payments_argentina
```

2. Crear y activar un entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Uso

1. Iniciar la aplicación:
```bash
python run.py
```

2. Abrir el navegador en `http://localhost:5000`

3. Subir un archivo Excel con la hoja '9. Remuneracion' que contenga las columnas:
   - Costo Piezas
   - Costo Horas ($)
   - Costo Total ($)

4. El sistema procesará el archivo y devolverá una versión actualizada con:
   - El costo total actualizado (valor más alto entre piezas y horas)
   - Una nueva columna 'Tipo de Pago' indicando si es por piezas o por horas
   - Filtros automáticos en todas las columnas

## Despliegue

La aplicación está configurada para ser desplegada en Render. Para desplegarla:

1. Crear una cuenta en Render
2. Conectar el repositorio de GitHub
3. Configurar el servicio web con:
   - Python como runtime
   - Comando de inicio: `gunicorn run:app`
   - Variables de entorno necesarias

## Licencia

MIT 