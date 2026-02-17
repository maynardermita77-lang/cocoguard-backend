from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..deps import get_db, get_current_admin

router = APIRouter(prefix="/pest-types", tags=["pest-types"])


# Public (mobile/web) – list active pest types
@router.get("", response_model=list[schemas.PestTypeOut])
def get_pest_types(db: Session = Depends(get_db)):
    pests = db.query(models.PestType).filter(models.PestType.is_active == True).all()
    return pests


# Admin CRUD
@router.post("", response_model=schemas.PestTypeOut, dependencies=[Depends(get_current_admin)])
def create_pest_type(
    pest_in: schemas.PestTypeCreate,
    db: Session = Depends(get_db),
):
    pest = models.PestType(**pest_in.dict())
    db.add(pest)
    db.commit()
    db.refresh(pest)
    return pest


@router.put("/{pest_id}", response_model=schemas.PestTypeOut, dependencies=[Depends(get_current_admin)])
def update_pest_type(
    pest_id: int,
    pest_in: schemas.PestTypeCreate,
    db: Session = Depends(get_db),
):
    pest = db.query(models.PestType).filter(models.PestType.id == pest_id).first()
    if not pest:
        raise HTTPException(404, "Pest type not found")
    for field, value in pest_in.dict().items():
        setattr(pest, field, value)
    db.commit()
    db.refresh(pest)
    return pest


@router.delete("/{pest_id}", dependencies=[Depends(get_current_admin)])
def delete_pest_type(pest_id: int, db: Session = Depends(get_db)):
    pest = db.query(models.PestType).filter(models.PestType.id == pest_id).first()
    if not pest:
        raise HTTPException(404, "Pest type not found")
    db.delete(pest)
    db.commit()
    return {"detail": "Deleted"}
