from typing import List
from fastapi import HTTPException
from sqlalchemy.orm import Session
from models import Admin as AdminModel
from schemas import Admin, AdminCreate, AdminUpdate

def get_admin(db: Session, admin_id: int):
    return db.query(AdminModel).filter(AdminModel.id == admin_id).first()

def get_admins(db: Session, skip: int = 0, limit: int = 100) -> List[Admin]:
    return db.query(AdminModel).offset(skip).limit(limit).all()

def create_admin(db: Session, admin: AdminCreate):
    db_admin = AdminModel(**admin.dict())
    db.add(db_admin)
    db.commit()
    db.refresh(db_admin)
    return db_admin

def update_admin(db: Session, admin_id: int, admin: AdminUpdate):
    db_admin = db.query(AdminModel).filter(AdminModel.id == admin_id).first()
    if db_admin is None:
        raise HTTPException(status_code=404, detail="Admin not found")

    for key, value in admin.dict(exclude_unset=True).items():
        setattr(db_admin, key, value)

    db.commit()
    db.refresh(db_admin)
    return db_admin

def delete_admin(db: Session, admin_id: int):
    db_admin = db.query(AdminModel).filter(AdminModel.id == admin_id).first()
    if db_admin is None:
        raise HTTPException(status_code=404, detail="Admin not found")

    db.delete(db_admin)
    db.commit()
    return {"detail": "Admin deleted"}
