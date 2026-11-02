from typing import List, Optional
from sqlalchemy.orm import Session
from app.modules.institutional.models.company import Company
from app.modules.institutional.schemas.company import CompanyCreate, CompanyUpdate
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException
from app.shared.validators.rut import ChileanRUT


class CompanyService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, company_id: str) -> Company:
        company = self.db.query(Company).filter(Company.id == company_id, Company.deleted_at.is_(None)).first()
        if not company:
            raise EntityNotFoundException("Sociedad", company_id)
        return company

    def get_by_rut(self, rut: str) -> Optional[Company]:
        cleaned_rut = ChileanRUT.clean(rut)
        return self.db.query(Company).filter(Company.rut == cleaned_rut, Company.deleted_at.is_(None)).first()

    def list_all(self, only_active: bool = True) -> List[Company]:
        query = self.db.query(Company).filter(Company.deleted_at.is_(None))
        if only_active:
            query = query.filter(Company.is_active == True)
        return query.all()

    def create(self, data: CompanyCreate) -> Company:
        cleaned_rut = ChileanRUT.clean(data.rut)
        if self.get_by_rut(cleaned_rut):
            raise EntityAlreadyExistsException("Sociedad", "RUT", cleaned_rut)

        company = Company(
            rut=cleaned_rut,
            legal_name=data.legal_name,
            trade_name=data.trade_name,
            tax_activity=data.tax_activity,
            address=data.address,
            phone=data.phone,
            email=data.email,
            website=data.website,
            is_active=data.is_active,
        )
        self.db.add(company)
        self.db.commit()
        self.db.refresh(company)
        return company

    def update(self, company_id: str, data: CompanyUpdate) -> Company:
        company = self.get_by_id(company_id)
        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(company, key, value)
        self.db.commit()
        self.db.refresh(company)
        return company

    def soft_delete(self, company_id: str):
        company = self.get_by_id(company_id)
        company.soft_delete()
        self.db.commit()
