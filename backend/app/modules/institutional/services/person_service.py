from typing import List, Optional
from sqlalchemy.orm import Session
from app.modules.institutional.models.person import Person
from app.modules.institutional.schemas.person import PersonCreate, PersonUpdate
from app.core.exceptions import EntityNotFoundException, EntityAlreadyExistsException, InvalidRUTException
from app.shared.validators.rut import ChileanRUT


class PersonService:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, person_id: str) -> Person:
        person = self.db.query(Person).filter(Person.id == person_id, Person.deleted_at.is_(None)).first()
        if not person:
            raise EntityNotFoundException("Persona", person_id)
        return person

    def get_by_rut(self, rut: str) -> Optional[Person]:
        cleaned_rut = ChileanRUT.clean(rut)
        return self.db.query(Person).filter(Person.rut == cleaned_rut, Person.deleted_at.is_(None)).first()

    def get_by_email(self, email: str) -> Optional[Person]:
        return self.db.query(Person).filter(Person.email == email.lower().strip(), Person.deleted_at.is_(None)).first()

    def list_all(self, skip: int = 0, limit: int = 50, search: Optional[str] = None) -> tuple[List[Person], int]:
        query = self.db.query(Person).filter(Person.deleted_at.is_(None))
        if search:
            search_term = f"%{search.strip()}%"
            query = query.filter(
                (Person.first_name.ilike(search_term))
                | (Person.last_name.ilike(search_term))
                | (Person.rut.ilike(search_term))
                | (Person.email.ilike(search_term))
            )
        total = query.count()
        people = query.offset(skip).limit(limit).all()
        return people, total

    def create(self, data: PersonCreate) -> Person:
        cleaned_rut = ChileanRUT.clean(data.rut)
        if not ChileanRUT.validate(cleaned_rut):
            raise InvalidRUTException(data.rut)

        if self.get_by_rut(cleaned_rut):
            raise EntityAlreadyExistsException("Persona", "RUT", cleaned_rut)

        person = Person(
            rut=cleaned_rut,
            first_name=data.first_name.strip(),
            last_name=data.last_name.strip(),
            second_last_name=data.second_last_name.strip() if data.second_last_name else None,
            email=data.email.lower().strip(),
            phone=data.phone,
            birth_date=data.birth_date,
            gender=data.gender,
            address=data.address,
            city=data.city,
            is_active=data.is_active,
        )
        self.db.add(person)
        self.db.commit()
        self.db.refresh(person)
        return person

    def update(self, person_id: str, data: PersonUpdate) -> Person:
        person = self.get_by_id(person_id)
        update_data = data.model_dump(exclude_unset=True)
        if "email" in update_data and update_data["email"]:
            update_data["email"] = update_data["email"].lower().strip()

        for key, value in update_data.items():
            setattr(person, key, value)
        self.db.commit()
        self.db.refresh(person)
        return person

    def soft_delete(self, person_id: str):
        person = self.get_by_id(person_id)
        person.soft_delete()
        self.db.commit()
