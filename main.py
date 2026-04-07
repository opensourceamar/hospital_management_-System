import models
from database import engine, SessionLocal
from fastapi import FastAPI, Request, Form, Depends, HTTPException, UploadFile, File
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
import shutil

# Pydantic schema for patient registration
class PatientRegistration(BaseModel):
    name: str
    phone: str
    age: int
    gender: str
    assigned_doctor: str
    problem: str
    priority: str
    address: str = ""

# Pydantic schema for prescription submission
class PrescriptionSubmission(BaseModel):
    token: int
    medicine: str

app = FastAPI()

# Serve template files directly if requested
app.mount("/templates", StaticFiles(directory="c:/Users/hp/OneDrive/Desktop/HMS/templates"), name="templates")

# Serve uploaded files
app.mount("/uploads", StaticFiles(directory="c:/Users/hp/OneDrive/Desktop/HMS/uploads"), name="uploads")

# Create database tables on startup
models.Base.metadata.create_all(bind=engine)

# Use your specific path
templates = Jinja2Templates(directory="c:/Users/hp/OneDrive/Desktop/HMS/templates")

# Add custom Jinja2 filter for basename
def basename(path):
    from pathlib import Path
    return Path(path).name

templates.env.filters["basename"] = basename

# Temporary in-memory storage (for the dashboard counters)
patients_list = [] 
discharged_count = 0

# DB dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 🏠 Dashboard
@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    total_patients = db.query(models.Patient).count()
    
    # Get all patients for doctor queue
    patients = db.query(models.Patient).order_by(models.Patient.token.desc()).all()
    
    # Add prescription status and history to each patient
    for patient in patients:
        # Get the patient's current (latest) prescription if any
        current_prescription = (
            db.query(models.Prescription)
            .filter(models.Prescription.patient_token == patient.token)
            .filter(models.Prescription.medicine.isnot(None))
            .order_by(models.Prescription.created_at.desc())
            .first()
        )
        patient.current_prescription = current_prescription
        
        # Get patient's prescription history (past dispensed prescriptions)
        history = (
            db.query(models.Prescription)
            .filter(models.Prescription.patient_token == patient.token)
            .filter(models.Prescription.dispensed == True)
            .order_by(models.Prescription.created_at.desc())
            .all()
        )
        patient.prescription_history = history

    # Pharmacy: Only show non-dispensed prescriptions with medicine
    pharmacy_results = (
        db.query(models.Prescription, models.Patient)
        .join(models.Patient, models.Patient.token == models.Prescription.patient_token)
        .filter(models.Prescription.medicine.isnot(None))  # Only show prescriptions with medicine
        .filter(models.Prescription.dispensed == False)    # Not yet dispensed
        .order_by(models.Prescription.created_at.desc())
        .all()
    )

    pharmacy_items = [
        {
            "id": prescription.id,
            "token": prescription.patient_token,
            "patient_token": prescription.patient_token,
            "patient_name": patient.name,
            "phone": patient.phone,
            "medicine": prescription.medicine,
            "dispensed_by": prescription.dispensed_by,
            "dispensed_notes": prescription.dispensed_notes,
            "created_at": prescription.created_at,
        }
        for prescription, patient in pharmacy_results
    ]

    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context={
            "total": total_patients,
            "discharged": discharged_count,
            "patients": patients,
            "pharmacy_items": pharmacy_items
        }
    )

# 👤 Receptionist Section
@app.get("/receptionist")
def receptionist(request: Request, db: Session = Depends(get_db)):
    total_patients = db.query(models.Patient).count()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "total": total_patients,
            "discharged": discharged_count
        }
    )

# 🧾 Receptionist adds patient
@app.post("/register")
def register(
    request: Request, 
    name: str = Form(...), 
    phone: str = Form(...),
    age: int = Form(...),
    gender: str = Form(...),
    assigned_doctor: str = Form(...),
    problem: str = Form(...),
    priority: str = Form(...),
    db: Session = Depends(get_db)
):
    last_patient = db.query(models.Patient).order_by(models.Patient.token.desc()).first()
    token = (last_patient.token if last_patient else 0) + 1

    existing_visits = db.query(models.Patient).filter(models.Patient.phone == phone).count()
    visit_count = existing_visits + 1

    # Save to Database
    new_patient = models.Patient(
        name=name,
        phone=phone,
        age=age,
        gender=gender,
        assigned_doctor=assigned_doctor,
        problem=problem,
        priority=priority,
        token=token,
        visit_count=visit_count
    )
    db.add(new_patient)
    db.commit()
    db.refresh(new_patient)

    # For the dashboard UI counter
    patients_list.append(new_patient)

    return templates.TemplateResponse(
        request=request,
        name="doctor.html",
        context={"patient": new_patient}
    )

# API endpoint for JS registration flow
@app.post("/api/register")
def api_register(
    patient_data: PatientRegistration,
    db: Session = Depends(get_db)
):
    try:
        last_patient = db.query(models.Patient).order_by(models.Patient.token.desc()).first()
        token = (last_patient.token if last_patient else 0) + 1

        existing_visits = db.query(models.Patient).filter(models.Patient.phone == patient_data.phone).count()
        visit_count = existing_visits + 1

        new_patient = models.Patient(
            name=patient_data.name,
            phone=patient_data.phone,
            age=patient_data.age,
            gender=patient_data.gender,
            assigned_doctor=patient_data.assigned_doctor,
            problem=patient_data.problem,
            priority=patient_data.priority,
            token=token,
            visit_count=visit_count
        )
        db.add(new_patient)
        db.commit()
        db.refresh(new_patient)

        patients_list.append(new_patient)

        return {
            "success": True,
            "message": "Details added successfully.",
            "redirect_url": f"/doctor_form/{new_patient.token}"
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/doctor_form/{token}")
def doctor_form(request: Request, token: int, db: Session = Depends(get_db)):
    patient = db.query(models.Patient).filter(models.Patient.token == token).first()
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    
    # Get patient's prescription history (past dispensed prescriptions)
    prescription_history = (
        db.query(models.Prescription)
        .filter(models.Prescription.patient_token == token)
        .filter(models.Prescription.dispensed == True)
        .order_by(models.Prescription.created_at.desc())
        .all()
    )
    
    return templates.TemplateResponse(
        request=request,
        name="doctor.html",
        context={
            "patient": patient,
            "prescription_history": prescription_history
        }
    )

@app.get("/api/patient_history/{phone}")
def patient_history(phone: str, db: Session = Depends(get_db)):
    phone = phone.strip()
    patients = db.query(models.Patient).filter(models.Patient.phone == phone).order_by(models.Patient.token.desc()).all()
    if not patients:
        return {"exists": False}

    visit_count = len(patients)
    latest = patients[0]
    patient_tokens = [p.token for p in patients]
    records = db.query(models.Prescription).filter(models.Prescription.patient_token.in_(patient_tokens)).order_by(models.Prescription.created_at.desc()).all()

    history = [
        {
            "token": record.patient_token,
            "medicine": record.medicine,
            "test_required": record.test_required,
            "created_at": record.created_at.isoformat()
        }
        for record in records
    ]

    return {
        "exists": True,
        "name": latest.name,
        "age": latest.age,
        "phone": latest.phone,
        "visit_count": visit_count,
        "assigned_doctor": latest.assigned_doctor,
        "records": history
    }

# 👨‍⚕️ Doctor writes prescription
@app.post("/api/prescription")
def api_prescription(
    prescription_data: PrescriptionSubmission,
    db: Session = Depends(get_db)
):
    try:
        # Save prescription to DB
        new_prescription = models.Prescription(
            patient_token=prescription_data.token,
            medicine=prescription_data.medicine
        )
        db.add(new_prescription)
        db.commit()
        db.refresh(new_prescription)

        return {
            "success": True,
            "message": "Prescription submitted successfully.",
            "prescription_id": new_prescription.id
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/doctor")
def doctor(
    request: Request, 
    token: int = Form(...), 
    medicine: str = Form(...),
    db: Session = Depends(get_db)
):
    # Save prescription to DB
    new_prescription = models.Prescription(
        patient_token=token,
        medicine=medicine
    )
    db.add(new_prescription)
    
    db.commit()
    db.refresh(new_prescription)

    return templates.TemplateResponse(
        request=request,
        name="pharmacy.html",
        context={"prescription": new_prescription}
    )

# 🧪 Doctor sends patient to scan center

# 💊 Mark prescription as dispensed (AJAX endpoint)
class DispenseData(BaseModel):
    prescription_id: int
    dispensed_by: str
    dispensed_notes: str = ""

@app.post("/api/dispense")
def dispense_prescription(
    dispense_data: DispenseData,
    db: Session = Depends(get_db)
):
    try:
        prescription = db.query(models.Prescription).filter(
            models.Prescription.id == dispense_data.prescription_id
        ).first()
        
        if not prescription:
            return {
                "success": False,
                "error": "Prescription not found"
            }
        
        prescription.dispensed = True
        prescription.dispensed_by = dispense_data.dispensed_by
        prescription.dispensed_notes = dispense_data.dispensed_notes
        
        db.commit()
        global discharged_count
        discharged_count += 1
        
        return {
            "success": True,
            "message": "Prescription dispensed successfully"
        }
    except Exception as e:
        db.rollback()
        return {
            "success": False,
            "error": str(e)
        }

# 💊 Pharmacy completes
@app.post("/pharmacy")
def pharmacy(request: Request):
    global discharged_count
    discharged_count += 1

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "total": len(patients_list),
            "discharged": discharged_count
        }
    )

@app.post("/api/pharmacy")
def api_pharmacy(
    token: int = Form(...),
    dispensed_by: str = Form(...),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    prescription = db.query(models.Prescription).filter(models.Prescription.patient_token == token).first()
    if not prescription:
        raise HTTPException(status_code=404, detail="Prescription not found")

    global discharged_count
    discharged_count += 1

    return {
        "success": True,
        "message": f"Pharmacy details have been sent for token {token}."
    }

# 🔍 API for returning patients (Used by your HTML script)
@app.get("/api/lookup/{phone}")
def lookup_patient(phone: str, db: Session = Depends(get_db)):
    phone = phone.strip()
    patient = db.query(models.Patient).filter(models.Patient.phone == phone).first()
    if patient:
        return {
            "exists": True, 
            "name": patient.name, 
            "age": patient.age
        }
    return {"exists": False}