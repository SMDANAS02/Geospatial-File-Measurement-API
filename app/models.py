import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


def utc_now() -> datetime:
    """Return current UTC timestamp without timezone offset issues."""
    return datetime.now(timezone.utc)


def generate_short_id() -> str:
    """Generate a clean, readable unique identifier."""
    return f"geo-{uuid.uuid4().hex[:12]}"


class StoredFile(Base):
    """Represents a validated and persisted geospatial file record."""
    __tablename__ = "stored_files"

    id = Column(String(50), primary_key=True, default=generate_short_id, index=True)
    filename = Column(String(255), nullable=False)
    file_type = Column(String(50), nullable=False)  # kml, shapefile
    size_bytes = Column(Integer, nullable=False, default=0)
    source_crs = Column(String(100), nullable=False)
    measurement_crs = Column(String(100), nullable=True)
    projection_method = Column(String(255), nullable=True)
    feature_count = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="COMPLETED")  # COMPLETED, FAILED
    error_message = Column(Text, nullable=True)
    summary_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    features = relationship(
        "StoredFeature",
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="StoredFeature.feature_index",
    )


class StoredFeature(Base):
    """Represents an individual geospatial feature and its computed measurement."""
    __tablename__ = "stored_features"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_id = Column(String(50), ForeignKey("stored_files.id", ondelete="CASCADE"), nullable=False, index=True)
    feature_index = Column(Integer, nullable=False, index=True)
    geometry_type = Column(String(50), nullable=False)
    geometry_json = Column(Text, nullable=True)
    properties_json = Column(Text, nullable=True)

    # Measurement details
    measurement_status = Column(String(50), nullable=False, default="COMPLETED")
    measurement_type = Column(String(50), nullable=False)  # area, length, none, unsupported
    area_m2 = Column(Float, nullable=True)
    area_km2 = Column(Float, nullable=True)
    length_m = Column(Float, nullable=True)
    length_km = Column(Float, nullable=True)
    unit = Column(String(20), nullable=True)  # m², m, or None
    notes = Column(Text, nullable=True)

    file = relationship("StoredFile", back_populates="features")
