# app/routes.py
from datetime import datetime, timedelta  # Asegúrate de importar timedelta
import os
from flask import Blueprint, render_template, request, send_from_directory, current_app, redirect, url_for, session
import pandas as pd
from .models import ExtraJob
from .utils import round_to_nearest, generate_schedule, calculate_weekly_hours

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'clock_ins_file' not in request.files or 'deliveries_file' not in request.files:
        return 'Missing file(s)'
    
    clock_ins_file = request.files['clock_ins_file']
    deliveries_file = request.files['deliveries_file']
    
    if clock_ins_file.filename == '' or deliveries_file.filename == '':
        return 'No selected file(s)'
    
    # Save both files
    clock_ins_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], clock_ins_file.filename)
    deliveries_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], deliveries_file.filename)
    
    clock_ins_file.save(clock_ins_filepath)
    deliveries_file.save(deliveries_filepath)
    
    # Store the deliveries filename in the session for later use
    session['deliveries_filename'] = deliveries_file.filename
    
    return redirect(url_for('main.cost_variables', 
                          filename=clock_ins_file.filename,
                          clock_ins_filename=clock_ins_file.filename,
                          deliveries_filename=deliveries_file.filename))

@main_bp.route('/cost-variables')
def cost_variables():
    filename = request.args.get('filename')
    clock_ins_filename = request.args.get('clock_ins_filename')
    deliveries_filename = request.args.get('deliveries_filename')
    
    if not filename or not clock_ins_filename or not deliveries_filename:
        return redirect(url_for('main.index'))
        
    return render_template('cost_variables.html', 
                         filename=filename,
                         clock_ins_filename=clock_ins_filename,
                         deliveries_filename=deliveries_filename)

@main_bp.route('/download-cost-variables/<filename>')
def download_cost_variables(filename):
    # Read the deliveries file
    deliveries_filename = request.args.get('deliveries_filename')
    if not deliveries_filename:
        return "Deliveries file not found", 404
        
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], deliveries_filename)
    df = pd.read_excel(filepath, sheet_name='DATA')
    
    # Extract unique contractors for the Contractor sheet, filtering out empty values
    contractors_df = df[['Contractor', 'Contractor ID']].drop_duplicates(subset=['Contractor ID'])
    contractors_df = contractors_df[contractors_df['Contractor'].notna() & (contractors_df['Contractor'] != '')]
    contractors_df['Price per Hour'] = ''
    
    # Create the cost variables file with only the Contractor sheet
    cost_vars_filename = f'cost_variables_{filename}'
    cost_vars_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], cost_vars_filename)
    
    # Save to Excel with only Contractor sheet
    with pd.ExcelWriter(cost_vars_filepath, engine='xlsxwriter') as writer:
        # Write Contractor sheet
        contractors_df.to_excel(writer, sheet_name='Contractor', index=False)
        
        # Get the workbook and the sheet
        workbook = writer.book
        contractor_sheet = writer.sheets['Contractor']
        
        # Add bold format for headers
        bold_format = workbook.add_format({'bold': True})
        
        # Format Contractor sheet headers
        for col_num, value in enumerate(contractors_df.columns.values):
            contractor_sheet.write(0, col_num, value, bold_format)
    
    return send_from_directory(current_app.config['PROCESSED_FOLDER'], cost_vars_filename, as_attachment=True)

@main_bp.route('/process/<filename>', methods=['GET', 'POST'])
def process_file(filename):
    if request.method == 'GET':
        return render_template('index.html', 
                             filename=filename,
                             clock_ins_filename=filename)
        
    # POST method handling (existing code)
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_excel(filepath, sheet_name=0)
    df_production = pd.read_excel(filepath, sheet_name='Hours and production per day')

    # Get the deliveries file from session
    deliveries_filename = session.get('deliveries_filename')
    if not deliveries_filename:
        return "Deliveries file not found in session", 404
        
    deliveries_filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], deliveries_filename)
    df_deliveries = pd.read_excel(deliveries_filepath, sheet_name='DATA')
    
    # Get the cost variables file from session
    cost_vars_filename = session.get('cost_vars_filename')
    if not cost_vars_filename:
        return "Cost variables file not found in session", 404
        
    cost_vars_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], cost_vars_filename)
    df_deliveries_price = pd.read_excel(cost_vars_filepath, sheet_name='Deliveries Price')
    
    # Select only the required columns from deliveries
    required_columns = [
        'Harvest name', 'Workspace name', 'Workspace cost center', 'Workspace tags',
        'Space', 'Space cost center', 'Space tags', 'Specie', 'Variety',
        'Registration date', 'Registration time', 'Worker name', 'Worker ID',
        'Contractor', 'Contractor ID', 'Contractor Tags', 'Container', 'No. of containers'
    ]
    
    # Filter the deliveries dataframe to only include required columns
    df_deliveries_filtered = df_deliveries[required_columns]
    
    # Define columns to display in the Excel file
    display_columns = [
        'Harvest name', 'Workspace name', 'Space', 'Specie', 'Variety',
        'Registration date', 'Worker name', 'Worker ID', 'Contractor',
        'Contractor ID', 'Container', 'No. of containers'
    ]
    
    # Create a new dataframe with only the display columns
    df_deliveries_display = df_deliveries_filtered[display_columns]
    
    # Define the grouping columns
    group_columns = [
        'Harvest name', 'Workspace name', 'Space', 'Specie', 'Variety',
        'Registration date', 'Worker name', 'Worker ID', 'Container'
    ]
    
    # Group by the specified columns and sum the number of containers
    df_deliveries_grouped = df_deliveries_display.groupby(group_columns, as_index=False)['No. of containers'].sum()
    
    # Add back the Contractor and Contractor ID columns
    df_deliveries_grouped = df_deliveries_grouped.merge(
        df_deliveries_display[group_columns + ['Contractor', 'Contractor ID']].drop_duplicates(),
        on=group_columns,
        how='left'
    )
    
    # Reorder columns to match the original display order
    df_deliveries_grouped = df_deliveries_grouped[display_columns]

    # Merge with Deliveries Price to get Price per Unit
    df_deliveries_price['Registration date'] = pd.to_datetime(df_deliveries_price['Registration date'])
    df_deliveries_grouped['Registration date'] = pd.to_datetime(df_deliveries_grouped['Registration date'])
    
    # Merge based on matching columns
    merge_columns = ['Workspace name', 'Space', 'Variety', 'Registration date', 'Container']
    df_deliveries_grouped = df_deliveries_grouped.merge(
        df_deliveries_price[merge_columns + ['Price per Unit']],
        on=merge_columns,
        how='left'
    )
    
    # Calculate Total Cost
    df_deliveries_grouped['Total Cost'] = df_deliveries_grouped['No. of containers'] * df_deliveries_grouped['Price per Unit']
    
    # Reorder columns to include the new ones
    final_columns = display_columns + ['Price per Unit', 'Total Cost']
    df_deliveries_grouped = df_deliveries_grouped[final_columns]

    # Validar columnas requeridas
    required_columns = ["Picker name", "Picker ID", "Clock-in date", "Clock-in time", "Clock-out time"]
    required_columns_production = ["Picker name", "Picker ID", "Date"]  # Removemos "# Containers" de las columnas requeridas

    if any(col not in df.columns for col in required_columns):
        return f"Error: The file must contain the columns {', '.join(required_columns)}.", 400
    
    if any(col not in df_production.columns for col in required_columns_production):
        return f"Error: The file must contain the columns {', '.join(required_columns_production)}.", 400

    # Detectar dinámicamente los pares de columnas Container/# Containers
    container_columns = []
    pieces_columns = []
    for col in df_production.columns:
        if col.startswith('Container'):
            container_columns.append(col)
        elif col.startswith('# Containers'):
            pieces_columns.append(col)

    if len(container_columns) != len(pieces_columns):
        return "Error: Each Container column must have a corresponding # Containers column.", 400

    # Crear un diccionario para mapear contenedores con sus columnas de piezas
    container_pieces_map = dict(zip(container_columns, pieces_columns))

    # Crear un diccionario para mantener el último valor de cada contenedor
    last_container_values = {col: "" for col in container_columns}
    # Crear un diccionario para mantener el último día de la semana procesado
    last_week_processed = {col: None for col in container_columns}
    # Crear un diccionario para mantener el primer día de cada semana
    first_day_of_week = {}
    # Crear un diccionario para mantener los tipos de contenedor por trabajador y semana
    worker_week_containers = {}

    round_time = request.form.get("round_time") == "on"
    round_interval = int(request.form.get("round_interval", 15)) if round_time else None

    weekly_hourly_limit = float(request.form.get("weekly_limit", 7.0))

    overtime_rate_multiplier = float(request.form.get("overtime_rate_multiplier", 1.0))

    job_hours = request.form.getlist("job[hour][]")
    job_minutes = request.form.getlist("job[minutes][]")
    job_types = request.form.getlist("job[type][]")
    job_paid = request.form.getlist("job[paid][]")  # Checkboxes

    job_paid_flags = ["1" if str(i) in job_paid else "0" for i in range(len(job_hours))]
    jobs = [ExtraJob(h, m, t, p) for h, m, t, p in zip(job_hours, job_minutes, job_types, job_paid_flags)]
    print("--------")
    print(jobs)

    decimal_places = request.form.get("decimal_places")
    decimal_places = int(decimal_places) if decimal_places and decimal_places.isdigit() else None

    # Listas para detalles
    workers = []
    picker_ids = []
    clock_in_dates = []
    schedules = []
    descriptions = []
    # Diccionario de resumen diario (por cada registro de clock‑in)
    summary_data = {}

    for _, row in df.iterrows():
        name = row["Picker name"]
        picker_id = row["Picker ID"]
        clock_in_date = row["Clock-in date"]
        start_time = row["Clock-in time"]
        end_time = row["Clock-out time"]

        if pd.isna(start_time) or pd.isna(end_time) or pd.isna(clock_in_date):
            continue

        # Convertir los tiempos si son cadenas
        if isinstance(start_time, str):
            start_time = datetime.strptime(start_time, "%H:%M:%S").time()
        if isinstance(end_time, str):
            end_time = datetime.strptime(end_time, "%H:%M:%S").time()
        # Convertir la fecha si es cadena (ajusta el formato si es necesario)
        if isinstance(clock_in_date, str):
            clock_in_date = datetime.strptime(clock_in_date, "%Y-%m-%d").date()

        # Combina la fecha con el tiempo
        start_time_dt = datetime.combine(clock_in_date, start_time)
        end_time_dt = datetime.combine(clock_in_date, end_time)

        if round_time and round_interval:
            start_time_dt = round_to_nearest(start_time_dt, round_interval)
            end_time_dt = round_to_nearest(end_time_dt, round_interval)

        generated_schedule, summary = generate_schedule(str(start_time_dt.time()), str(end_time_dt.time()), jobs)
        
        job_types_set = set()
        for schedule in generated_schedule:
            workers.append(name)
            picker_ids.append(picker_id)
            # Agregar la fecha formateada para el detalle
            clock_in_dates.append(clock_in_date.strftime("%Y-%m-%d"))
            schedules.append(f"{schedule[0]} - {schedule[1]}")
            descriptions.append(schedule[2])
            job_types_set.add(schedule[2])

        total_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
        summary["Total Hours"] = total_hours
        summary["Job Types"] = ", ".join(sorted(job_types_set))

        if decimal_places is not None:
            summary = {key: round(value, decimal_places) if isinstance(value, (int, float)) else value 
                       for key, value in summary.items()}

        summary["Worker Name"] = name
        summary["Picker ID"] = picker_id
        summary["Clock-in date"] = clock_in_date.strftime("%Y-%m-%d")
        key = f"{picker_id}_{summary['Clock-in date']}"
        summary_data[key] = summary

    # Crear DataFrame de detalles
    df_processed = pd.DataFrame({
        "Worker": workers,
        "Picker ID": picker_ids,
        "Clock-in date": clock_in_dates,
        "Schedule": schedules,
        "Description": descriptions
    })

    # Agregar columna para la semana (ISO: lunes a domingo)
    df_processed['Clock-in date'] = pd.to_datetime(df_processed['Clock-in date'])
    df_processed['Semana'] = df_processed['Clock-in date'].dt.isocalendar().week
    # Ordenar por trabajador, semana y fecha
    df_processed = df_processed.sort_values(['Worker', 'Semana', 'Clock-in date'])

    # Crear DataFrame de resumen diario (sin agrupar)
    df_summary = pd.DataFrame.from_dict(summary_data, orient='index').reset_index(drop=True)
    
    # Agregar columna para la semana (ISO: lunes a domingo)
    df_summary['Clock-in date'] = pd.to_datetime(df_summary['Clock-in date'])
    df_summary['Semana'] = df_summary['Clock-in date'].dt.isocalendar().week
    
    # Agregar columnas para cada contenedor
    for container_col, pieces_col in container_pieces_map.items():
        df_summary[container_col] = ""  # Cambiado a string vacío en lugar de 0
        df_summary[pieces_col] = 0.0    # Cambiado a float en lugar de int

    # Agregar columnas de horas regulares y extras
    df_summary['Regular Hours'] = 0.0
    df_summary['Overtime Hours'] = 0.0
    df_summary['Overtime Rate Multiplier'] = overtime_rate_multiplier

    # Calcular horas regulares y extras por semana
    df_summary = calculate_weekly_hours(df_summary, weekly_hourly_limit)

    # Guardar la columna Semana antes de reordenar
    semana_column = df_summary['Semana']

    column_order = ["Worker Name", "Picker ID", "Clock-in date", "Job Types", "Total Hours", "Paid Hours", "Worked Hours", "Lunch Hours", "Break Hours", "Other Hours", "Regular Hours", "Overtime Hours", "Overtime Rate Multiplier"]
    # Agregar las columnas de contenedores al orden
    column_order.extend(container_columns)
    column_order.extend(pieces_columns)
    
    df_summary = df_summary[column_order]
    
    # Restaurar la columna Semana después de reordenar
    df_summary['Semana'] = semana_column

    # Obtener el primer día de cada semana para cada trabajador
    for worker in df_summary['Worker Name'].unique():
        worker_data = df_summary[df_summary['Worker Name'] == worker]
        for week in worker_data['Semana'].unique():
            week_data = worker_data[worker_data['Semana'] == week]
            first_day = week_data['Clock-in date'].min()
            first_day_of_week[f"{worker}_{week}"] = first_day

    for _, row in df_summary.iterrows():
        worker_name = row["Worker Name"]
        picker_id = row["Picker ID"]
        clock_in_date = row["Clock-in date"]
        current_week = row["Semana"]
        week_key = f"{worker_name}_{current_week}"
        
        # Buscar producción para este trabajador y fecha
        production_row = df_production[
            (df_production['Picker name'] == worker_name) &
            (df_production['Picker ID'] == picker_id) &
            (pd.to_datetime(df_production['Date']) == clock_in_date)
        ]
        
        if not production_row.empty:
            # Actualizar valores para cada contenedor
            for container_col, pieces_col in container_pieces_map.items():
                container_value = production_row.iloc[0][container_col]
                pieces_value = float(production_row.iloc[0][pieces_col])
                
                # Convertir el valor del contenedor a string y manejar NaN
                if pd.isna(container_value):
                    container_value = ""
                else:
                    container_value = str(container_value).strip()
                
                # Mostrar el valor del contenedor solo en el primer día de la semana
                if clock_in_date == first_day_of_week[week_key]:
                    # Si hay piezas pero no hay tipo de contenedor, usar el último tipo conocido
                    if pieces_value > 0 and not container_value:
                        # Buscar el último tipo de contenedor conocido para este trabajador
                        last_known_container = worker_week_containers.get(f"{worker_name}_{container_col}", "")
                        df_summary.loc[row.name, container_col] = last_known_container
                    else:
                        df_summary.loc[row.name, container_col] = container_value
                        # Guardar el tipo de contenedor para futuras referencias
                        if container_value:
                            worker_week_containers[f"{worker_name}_{container_col}"] = container_value
                else:
                    df_summary.loc[row.name, container_col] = ""
                
                df_summary.loc[row.name, pieces_col] = pieces_value

    processed_filename = f'processed_{filename}'
    processed_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], processed_filename)

    with pd.ExcelWriter(processed_filepath, engine='xlsxwriter') as writer:
        workbook = writer.book
        bold_format = workbook.add_format({'bold': True})
        
        # Hoja Details: escritura con agrupación por trabajador y semana
        details_sheet = workbook.add_worksheet('Details')
        headers = ["Worker", "Picker ID", "Clock-in date", "Schedule", "Description"]
        row_index = 0
        details_sheet.write_row(row_index, 0, headers, bold_format)
        row_index += 1
        
        groups = df_processed.groupby(['Worker', 'Semana'])
        for (worker, worker_id), group in groups:
            sample_date = group["Clock-in date"].iloc[0]
            monday = sample_date - timedelta(days=sample_date.weekday())
            sunday = monday + timedelta(days=6)
            group_title = f"Worker: {worker} (ID: {worker_id}), Week: {monday.strftime('%Y-%m-%d')} to {sunday.strftime('%Y-%m-%d')}"
            details_sheet.write(row_index, 0, group_title, bold_format)
            row_index += 1
            for _, record in group.iterrows():
                details_sheet.write(row_index, 0, record["Worker"])
                details_sheet.write(row_index, 1, record["Picker ID"])
                details_sheet.write(row_index, 2, record["Clock-in date"].strftime("%Y-%m-%d"))
                details_sheet.write(row_index, 3, record["Schedule"])
                details_sheet.write(row_index, 4, record["Description"])
                row_index += 1
            row_index += 1  # Línea en blanco entre grupos
        
        # Hoja Summary: escritura de cada registro diario agrupado por trabajador y semana con totales
        summary_sheet = workbook.add_worksheet('Summary')
        header_summary = [
            "Worker Name",
            "Picker ID",
            "Clock-in date",
            "Job Types",
            "Total Hours",
            "Paid Hours",
            "Worked Hours",
            "Lunch Hours",
            "Break Hours",
            "Other Hours",
            "Regular Hours",
            "Overtime Hours",
            "Overtime Rate Multiplier"
        ]
        # Agregar columnas de contenedores al encabezado con nombres mejorados
        for i, (container_col, pieces_col) in enumerate(container_pieces_map.items()):
            container_type = f"Container Type {i+1}"
            pieces_count = f"Pieces Count {i+1}"
            header_summary.extend([container_type, pieces_count])

        row_index_summary = 0
        summary_sheet.write_row(row_index_summary, 0, header_summary, bold_format)
        row_index_summary += 1
        
        groups_summary = df_summary.groupby(['Worker Name', 'Picker ID', 'Semana'])
        for (worker_name, picker_id, _), group in groups_summary:
            sample_date = group["Clock-in date"].iloc[0]
            monday = sample_date - timedelta(days=sample_date.weekday())
            sunday = monday + timedelta(days=6)
            group_title = f"Worker: {worker_name} (ID: {picker_id}), Week: {monday.strftime('%Y-%m-%d')} to {sunday.strftime('%Y-%m-%d')}"
            summary_sheet.write(row_index_summary, 0, group_title, bold_format)
            row_index_summary += 1
            
            for _, record in group.iterrows():
                # Escribir datos básicos
                for i, col in enumerate(header_summary[:13]):  # Primeras 13 columnas son datos básicos
                    summary_sheet.write(row_index_summary, i, record[col])
                
                # Escribir datos de contenedores
                col_index = 13
                for container_col, pieces_col in container_pieces_map.items():
                    summary_sheet.write(row_index_summary, col_index, record[container_col])
                    col_index += 1
                    summary_sheet.write(row_index_summary, col_index, record[pieces_col])
                    col_index += 1
                
                row_index_summary += 1

            # Calcular totales para cada columna del grupo
            total_columns = {
                "Total Hours": group["Total Hours"].sum(),
                "Paid Hours": group["Paid Hours"].sum(),
                "Worked Hours": group["Worked Hours"].sum(),
                "Lunch Hours": group["Lunch Hours"].sum(),
                "Break Hours": group["Break Hours"].sum(),
                "Other Hours": group["Other Hours"].sum(),
                "Regular Hours": group["Regular Hours"].sum(),
                "Overtime Hours": group["Overtime Hours"].sum()
            }
            
            # Agregar totales para columnas de contenedores
            for container_col, pieces_col in container_pieces_map.items():
                total_columns[container_col] = ""  # No sumamos los contenedores
                total_columns[pieces_col] = group[pieces_col].sum()  # Solo sumamos las piezas

            # Escribir fila de totales
            summary_sheet.write(row_index_summary, 0, "")
            summary_sheet.write(row_index_summary, 1, "")
            summary_sheet.write(row_index_summary, 2, "")
            summary_sheet.write(row_index_summary, 3, "TOTAL", bold_format)
            
            # Escribir totales para cada columna
            for i, col in enumerate(header_summary[4:], start=4):
                if col in total_columns:
                    if col.startswith('Pieces Count'):
                        summary_sheet.write(row_index_summary, i, total_columns[col], bold_format)
                    else:
                        summary_sheet.write(row_index_summary, i, total_columns[col], bold_format)
                else:
                    summary_sheet.write(row_index_summary, i, "")
            
            row_index_summary += 1
            row_index_summary += 1  # Línea en blanco entre grupos

        # Add Deliveries sheet
        deliveries_sheet = workbook.add_worksheet('Deliveries')
        row_index_deliveries = 0
        
        # Write headers
        deliveries_sheet.write_row(row_index_deliveries, 0, final_columns, bold_format)
        row_index_deliveries += 1
        
        # Write data
        for _, row in df_deliveries_grouped.iterrows():
            for col_num, value in enumerate(row):
                # Handle NaN and INF values
                if pd.isna(value) or value == float('inf') or value == float('-inf'):
                    deliveries_sheet.write(row_index_deliveries, col_num, '')
                else:
                    deliveries_sheet.write(row_index_deliveries, col_num, value)
            row_index_deliveries += 1

        # Add Deliveries Price sheet
        deliveries_price_sheet = workbook.add_worksheet('Deliveries Price')
        row_index_price = 0
        
        # Write headers
        deliveries_price_sheet.write_row(row_index_price, 0, df_deliveries_price.columns, bold_format)
        row_index_price += 1
        
        # Write data
        for _, row in df_deliveries_price.iterrows():
            for col_num, value in enumerate(row):
                # Handle NaN and INF values
                if pd.isna(value) or value == float('inf') or value == float('-inf'):
                    deliveries_price_sheet.write(row_index_price, col_num, '')
                else:
                    deliveries_price_sheet.write(row_index_price, col_num, value)
            row_index_price += 1

    return render_template('index.html', 
                         filename=filename, 
                         processed=True)

@main_bp.route('/download/<filename>')
def download_file(filename):
    processed_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(processed_filepath):
        return send_from_directory(current_app.config['PROCESSED_FOLDER'], filename, as_attachment=True)
    else:
        return "File not found", 404

@main_bp.route('/upload-cost-variables/<filename>', methods=['POST'])
def upload_cost_variables(filename):
    if 'cost_file' not in request.files:
        return 'No file part'
    
    cost_file = request.files['cost_file']
    if cost_file.filename == '':
        return 'No selected file'
    
    # Read the uploaded cost variables file with contractor prices
    df_contractors = pd.read_excel(cost_file, sheet_name='Contractor')
    
    # Read the deliveries file to get worker and delivery information
    deliveries_filename = request.args.get('deliveries_filename')
    if not deliveries_filename:
        return "Deliveries file not found", 404
        
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], deliveries_filename)
    df = pd.read_excel(filepath, sheet_name='DATA')
    
    # Create a mapping of contractor IDs to their prices
    contractor_prices = dict(zip(df_contractors['Contractor ID'], df_contractors['Price per Hour']))
    
    # Create Worker sheet with contractor prices
    workers_df = df[['Worker name', 'Worker ID', 'Contractor', 'Contractor ID']].drop_duplicates(subset=['Worker ID'])
    workers_df['Price per Hour'] = workers_df['Contractor ID'].map(contractor_prices)
    
    # Create Deliveries Price sheet
    unique_values = {
        'Workspace name': df['Workspace name'].dropna().unique(),
        'Space': df['Space'].dropna().unique(),
        'Variety': df['Variety'].dropna().unique(),
        'Registration date': pd.to_datetime(df['Registration date'].dropna().unique()).strftime('%m-%d-%Y'),
        'Container': df['Container'].dropna().unique()
    }
    
    from itertools import product
    combinations = list(product(
        unique_values['Workspace name'],
        unique_values['Space'],
        unique_values['Variety'],
        unique_values['Registration date'],
        unique_values['Container']
    ))
    
    deliveries_price_df = pd.DataFrame(
        combinations,
        columns=['Workspace name', 'Space', 'Variety', 'Registration date', 'Container']
    )
    deliveries_price_df['Price per Unit'] = ''
    
    # Create the complete cost variables file
    cost_vars_filename = f'complete_cost_variables_{filename}'
    cost_vars_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], cost_vars_filename)
    
    # Save to Excel with all sheets
    with pd.ExcelWriter(cost_vars_filepath, engine='xlsxwriter') as writer:
        # Write Contractor sheet (with prices)
        df_contractors.to_excel(writer, sheet_name='Contractor', index=False)
        
        # Write Worker sheet (with contractor prices)
        workers_df.to_excel(writer, sheet_name='Worker', index=False)
        
        # Write Deliveries Price sheet
        deliveries_price_df.to_excel(writer, sheet_name='Deliveries Price', index=False)
        
        # Get the workbook and the sheets
        workbook = writer.book
        contractor_sheet = writer.sheets['Contractor']
        worker_sheet = writer.sheets['Worker']
        deliveries_price_sheet = writer.sheets['Deliveries Price']
        
        # Add bold format for headers
        bold_format = workbook.add_format({'bold': True})
        
        # Format all sheet headers
        for sheet, df in [(contractor_sheet, df_contractors), 
                         (worker_sheet, workers_df), 
                         (deliveries_price_sheet, deliveries_price_df)]:
            for col_num, value in enumerate(df.columns.values):
                sheet.write(0, col_num, value, bold_format)
    
    # Store the cost variables filename in the session
    session['cost_vars_filename'] = cost_vars_filename
    
    return "File uploaded successfully. You can now download the complete cost variables file.", 200

@main_bp.route('/upload-complete-cost/<filename>', methods=['POST'])
def upload_complete_cost(filename):
    if 'complete_cost_file' not in request.files:
        return 'No file part'
    
    cost_file = request.files['complete_cost_file']
    if cost_file.filename == '':
        return 'No selected file'
    
    # Read the uploaded complete cost variables file
    df_contractors = pd.read_excel(cost_file, sheet_name='Contractor')
    df_workers = pd.read_excel(cost_file, sheet_name='Worker')
    df_deliveries = pd.read_excel(cost_file, sheet_name='Deliveries Price')
    
    # Save the complete file for later use
    cost_vars_filename = f'final_cost_variables_{filename}'
    cost_vars_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], cost_vars_filename)
    
    with pd.ExcelWriter(cost_vars_filepath, engine='xlsxwriter') as writer:
        df_contractors.to_excel(writer, sheet_name='Contractor', index=False)
        df_workers.to_excel(writer, sheet_name='Worker', index=False)
        df_deliveries.to_excel(writer, sheet_name='Deliveries Price', index=False)
        
        # Format headers
        workbook = writer.book
        bold_format = workbook.add_format({'bold': True})
        
        for sheet_name, df in [('Contractor', df_contractors), 
                             ('Worker', df_workers), 
                             ('Deliveries Price', df_deliveries)]:
            sheet = writer.sheets[sheet_name]
            for col_num, value in enumerate(df.columns.values):
                sheet.write(0, col_num, value, bold_format)
    
    # Store the final cost variables filename in the session
    session['cost_vars_filename'] = cost_vars_filename
    
    return "Complete cost variables file uploaded successfully.", 200
