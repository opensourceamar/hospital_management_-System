from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Patient(Base):
    __tablename__ = "patients"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    phone = Column(String(20), index=True)
    age = Column(Integer)
    gender = Column(String(10))
    problem = Column(Text)
    priority = Column(String(20)) # High, Medium, Low
    assigned_doctor = Column(String(100))
    token = Column(Integer, unique=True) # Unique Token for this visit
    arrival_time = Column(DateTime, default=datetime.utcnow)
    visit_count = Column(Integer, default=1)
    
    # Relationship to the Prescription table
    # This allows us to access patient.prescription directly in the code
    prescription = relationship("Prescription", back_populates="patient", uselist=False)

class Prescription(Base):
    __tablename__ = "prescriptions"

    id = Column(Integer, primary_key=True, index=True)
    # This maps the prescription token field to the existing DB column named `token`
    patient_token = Column("token", Integer, ForeignKey("patients.token"))
    medicine = Column(String(255), nullable=True)
    test_required = Column(String(255), nullable=True) # If doctor wants scans
    test_completed = Column(Boolean, default=False) # Whether test results are uploaded
    test_result_file = Column(String(500), nullable=True) # Path to uploaded result file
    test_result_notes = Column(Text, nullable=True) # Additional notes about results
    dispensed = Column(Boolean, default=False) # Whether pharmacist has dispensed
    dispensed_by = Column(String(100), nullable=True) # Pharmacist name
    dispensed_notes = Column(Text, nullable=True) # Dosage or notes from pharmacist
    created_at = Column(DateTime, default=datetime.utcnow)

    # Link back to the Patient
    patient = relationship("Patient", back_populates="prescription")