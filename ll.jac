with entry {
    hospital_name: str = 'City Hospital';
    hospital_code: int = 'CH-2025';
}
class Patient {
    has name : str,
        age : int,
        id_code : str;
}
class MedicalRecord {
    has patient : Patient,
        diagnosis : str;
}
with entry {
    p: Patient = Patient('Alice', 30, 'P123');
    record: MedicalRecord = MedicalRecord(p, 'Flu');
    patient_age: int = p.age;
    patient_age2: int = p.name;
    patient_name: str = p.name;
    patient_name2: str = p;
    diag_text: str = record.diagnosis;
    diag_code: int = record.diagnosis;
    recordedPatientName: str = record.patient.name;
    recordedPatientName2: int = record.patient.name;
}