from datetime import datetime, time

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass 

class Patient(Base):
    """
    stores information about patient
    """
    __tablename__ = "patients"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50),nullable=False)
    phone: Mapped[str] = mapped_column(String(13),unique=True,nullable=False,index=True)


class Slot(Base):
    """
    stores information about availability
    """
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    clinic_id: Mapped[int] = mapped_column(default=1,index=True, nullable=False)
    starts_at: Mapped[datetime] = mapped_column(index=True,nullable=False)
    ends_at: Mapped[datetime] = mapped_column(nullable=False)
    # ensure start datetime < endtime 
    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="check_slot_time")
    )
    

class Appointment(Base):
    """
    stores information about appointments
    """
    __tablename__ = "appointments"
    
    __table_args__ = (
        # only booked appointment per slot
        Index("unique_booked_slot", "slot_id", unique=True,sqlite_where=text("status='booked'")),
        # valid appointment statuses
        CheckConstraint("status in ('booked','cancelled')", name="check_appointment_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), nullable=False, index=True)
    slot_id: Mapped[int] = mapped_column(ForeignKey("slots.id"), nullable=False,index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64),unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(10),default="booked",nullable=False)

class OpeningHours(Base):
    """
    stores information about opening hours
    """
    __tablename__ = "opening_hours"
    id: Mapped[int] = mapped_column(primary_key=True)
    weekday: Mapped[int] = mapped_column(unique=True,nullable=False)
    opens: Mapped[time] = mapped_column(nullable=False)
    closes: Mapped[time] = mapped_column(nullable=False)

    __table_args__ = (
        # valid weekday 
        CheckConstraint("weekday between 0 and 6", name="check_weekday"),
        # valid open and close time 
        CheckConstraint("opens < closes", name="check_opening_hours")
    )


