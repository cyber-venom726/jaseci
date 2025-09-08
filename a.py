# Global variables
hospital_name: str = "City Hospital"   # <-- Ok
hospital_code: int = "CH-2025"         # <-- Error (str assigned to int)


class Patient:
    def __init__(self, name: str, age: int, id_code: str) -> None:
        self.name = name
        self.age = age
        self.id_code = id_code


class MedicalRecord:
    def __init__(self, patient: Patient, diagnosis: str) -> None:
        self.patient = patient
        self.diagnosis = diagnosis


# Create instances
p = Patient("Alice", 30, "P123")
record = MedicalRecord(p, "Flu")

# Attribute assignments
patient_age: int = p.age        # <-- Ok
patient_age2: int = p.name      # <-- Error (name is str, expected int)

patient_name: str = p.name      # <-- Ok
patient_name2: str = p          # <-- Error (Patient object, expected str)

# Nested attribute
diag_text: str = record.diagnosis   # <-- Ok
diag_code: int = record.diagnosis   # <-- Error (diagnosis is str, expected int)
