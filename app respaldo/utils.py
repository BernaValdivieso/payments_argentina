# app/utils.py
from datetime import datetime, timedelta

def round_to_nearest(dt, interval):
    """Redondea la hora al intervalo de minutos más cercano."""
    minutes = dt.minute
    remainder = minutes % interval
    if remainder < interval / 2:
        rounded_minutes = minutes - remainder
    else:
        rounded_minutes = minutes + (interval - remainder)
    return dt.replace(minute=rounded_minutes, second=0)

def generate_schedule(start_time_str, end_time_str, jobs):
    """Genera el horario de trabajo con jobs personalizados."""
    start_time = datetime.strptime(start_time_str, "%H:%M:%S")
    end_time = datetime.strptime(end_time_str, "%H:%M:%S")
    
    current_time = start_time
    schedules = []
    
    summary = {
        "Worked Hours": 0,
        "Lunch Hours": 0,
        "Break Hours": 0,
        "Other Hours": 0,
        "Paid Hours": 0,
    }

    while current_time < end_time:
        next_hour = current_time + timedelta(hours=1)
        if next_hour > end_time:
            next_hour = end_time

        schedules.append((current_time.strftime('%H:%M:%S'), next_hour.strftime('%H:%M:%S'), "Work"))
        summary["Worked Hours"] += (next_hour - current_time).total_seconds() / 3600
        summary["Paid Hours"] += (next_hour - current_time).total_seconds() / 3600
        current_time = next_hour

        for job in jobs:
            if summary["Worked Hours"] % job.hour == 0 and current_time < end_time:
                job_duration = timedelta(minutes=job.minutes)
                next_job = current_time + job_duration
                if next_job > end_time:
                    next_job = end_time
                schedules.append((current_time.strftime('%H:%M:%S'), next_job.strftime('%H:%M:%S'), job.job_type))
                
                time_to_add = (next_job - current_time).total_seconds() / 3600

                if job.is_paid:
                    summary["Paid Hours"] += time_to_add

                if job.job_type == "Lunch":
                    summary["Lunch Hours"] += time_to_add
                elif job.job_type == "Break":
                    summary["Break Hours"] += time_to_add
                else:
                    summary["Other Hours"] += time_to_add
                
                current_time = next_job

    return schedules, summary
