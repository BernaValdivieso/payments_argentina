# app/models.py
class ExtraJob:
    def __init__(self, hour, minutes, job_type, is_paid=False):
        self.hour = int(hour)
        self.minutes = int(minutes)
        self.job_type = job_type
        self.is_paid = bool(int(is_paid))  # Convertir a booleano

    def __repr__(self):
        return f"ExtraJob(hour={self.hour}, minutes={self.minutes}, type={self.job_type}, paid={self.is_paid})"
