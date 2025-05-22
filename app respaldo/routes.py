# app/routes.py
import os
from flask import Blueprint, render_template, request, send_from_directory, current_app
import pandas as pd
from datetime import datetime
from .models import ExtraJob
from .utils import round_to_nearest, generate_schedule

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return 'No file part'
    
    file = request.files['file']
    if file.filename == '':
        return 'No selected file'
    
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    return render_template('index.html', filename=file.filename)

@main_bp.route('/process/<filename>', methods=['POST'])
def process_file(filename):
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    df = pd.read_excel(filepath, sheet_name=0)

    # Incluir "Clock-in date" en la validación
    required_columns = ["Picker name", "Picker ID", "Clock-in date", "Clock-in time", "Clock-out time"]
    if any(col not in df.columns for col in required_columns):
        return f"Error: The file must contain the columns {', '.join(required_columns)}.", 400

    round_time = request.form.get("round_time") == "on"
    round_interval = int(request.form.get("round_interval", 15)) if round_time else None

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

    workers = []
    picker_ids = []
    clock_in_dates = []  # Nueva lista para las fechas
    schedules = []
    descriptions = []
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
            # Agregar la fecha formateada para la columna de detalle
            clock_in_dates.append(clock_in_date.strftime("%Y-%m-%d"))
            schedules.append(f"{schedule[0]} - {schedule[1]}")
            descriptions.append(schedule[2])
            job_types_set.add(schedule[2])

        total_hours = (end_time_dt - start_time_dt).total_seconds() / 3600
        summary["Total Hours"] = total_hours
        summary["Job Types"] = ", ".join(sorted(job_types_set))

        if decimal_places is not None:
            summary = {key: round(value, decimal_places) if isinstance(value, (int, float)) else value for key, value in summary.items()}

        summary["Worker Name"] = name
        summary["Picker ID"] = picker_id
        summary["Clock-in date"] = clock_in_date.strftime("%Y-%m-%d")
        key = f"{picker_id}_{summary['Clock-in date']}"
        summary_data[key] = summary

    # Incluir la nueva columna "Clock-in date" en el DataFrame de detalles
    df_processed = pd.DataFrame({
        "Worker": workers,
        "Picker ID": picker_ids,
        "Clock-in date": clock_in_dates,
        "Schedule": schedules,
        "Description": descriptions
    })
    df_summary = pd.DataFrame.from_dict(summary_data, orient='index').reset_index()
    df_summary.drop('index', axis=1, inplace=True)


    column_order = ["Worker Name", "Picker ID", "Clock-in date", "Job Types", "Total Hours", "Paid Hours", "Worked Hours", "Lunch Hours", "Break Hours", "Other Hours"]
    df_summary = df_summary[column_order]

    processed_filename = f'processed_{filename}'
    processed_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], processed_filename)

    with pd.ExcelWriter(processed_filepath, engine='xlsxwriter') as writer:
        df_processed.to_excel(writer, sheet_name='Details', index=False)
        df_summary.to_excel(writer, sheet_name='Summary', index=False)

    return render_template('index.html', filename=filename, processed=True)


@main_bp.route('/download/<filename>')
def download_file(filename):
    processed_filepath = os.path.join(current_app.config['PROCESSED_FOLDER'], filename)
    if os.path.exists(processed_filepath):
        return send_from_directory(current_app.config['PROCESSED_FOLDER'], filename, as_attachment=True)
    else:
        return "File not found", 404
