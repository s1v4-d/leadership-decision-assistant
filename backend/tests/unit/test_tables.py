"""Tests for SQLAlchemy ORM table definitions."""

from __future__ import annotations

import uuid

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from backend.src.models.tables import Asset, Base, BusinessMetric, Collection


class TestCollectionModel:
    def test_collection_table_name(self) -> None:
        assert Collection.__tablename__ == "collections"

    def test_collection_has_expected_columns(self) -> None:
        columns = {c.name for c in Collection.__table__.columns}
        assert columns == {"id", "name", "description", "vector_table", "created_at", "updated_at"}

    def test_collection_default_id_is_uuid(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            collection = Collection(name="test", vector_table="vec_test")
            session.add(collection)
            session.flush()
            assert collection.id is not None
            uuid.UUID(collection.id)

    def test_collection_roundtrip_in_sqlite(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            collection = Collection(name="leadership", description="Core docs", vector_table="vec_leadership")
            session.add(collection)
            session.commit()
            loaded = session.get(Collection, collection.id)
            assert loaded is not None
            assert loaded.name == "leadership"
            assert loaded.description == "Core docs"
            assert loaded.vector_table == "vec_leadership"

    def test_collection_timestamps_set_automatically(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            collection = Collection(name="ts-test", vector_table="vec_ts")
            session.add(collection)
            session.commit()
            session.refresh(collection)
            assert collection.created_at is not None
            assert collection.updated_at is not None


class TestAssetModel:
    def test_asset_table_name(self) -> None:
        assert Asset.__tablename__ == "assets"

    def test_asset_has_expected_columns(self) -> None:
        columns = {c.name for c in Asset.__table__.columns}
        assert columns == {"id", "collection_id", "filename", "file_type", "metadata_", "created_at"}

    def test_asset_belongs_to_collection(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            collection = Collection(name="docs", vector_table="vec_docs")
            session.add(collection)
            session.flush()
            asset = Asset(collection_id=collection.id, filename="report.pdf", file_type="pdf")
            session.add(asset)
            session.commit()
            loaded = session.get(Asset, asset.id)
            assert loaded is not None
            assert loaded.collection_id == collection.id
            assert loaded.filename == "report.pdf"


class TestBusinessMetricModel:
    def test_business_metric_table_name(self) -> None:
        assert BusinessMetric.__tablename__ == "business_metrics"

    def test_business_metric_has_expected_columns(self) -> None:
        columns = {c.name for c in BusinessMetric.__table__.columns}
        assert columns == {
            "id",
            "collection_id",
            "metric_name",
            "metric_value",
            "unit",
            "period",
            "category",
            "source_file",
            "created_at",
        }

    def test_business_metric_roundtrip_in_sqlite(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            collection = Collection(name="kpis", vector_table="vec_kpis")
            session.add(collection)
            session.flush()
            metric = BusinessMetric(
                collection_id=collection.id,
                metric_name="Revenue",
                metric_value=1_500_000.0,
                unit="USD",
                period="2025-Q4",
                category="Financial",
                source_file="kpis.xlsx",
            )
            session.add(metric)
            session.commit()
            loaded = session.get(BusinessMetric, metric.id)
            assert loaded is not None
            assert loaded.metric_name == "Revenue"
            assert loaded.metric_value == 1_500_000.0
            assert loaded.unit == "USD"
            assert loaded.period == "2025-Q4"
            assert loaded.category == "Financial"

    def test_business_metric_nullable_fields(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        with Session(engine) as session:
            collection = Collection(name="minimal", vector_table="vec_min")
            session.add(collection)
            session.flush()
            metric = BusinessMetric(
                collection_id=collection.id,
                metric_name="Headcount",
                metric_value=250.0,
            )
            session.add(metric)
            session.commit()
            loaded = session.get(BusinessMetric, metric.id)
            assert loaded is not None
            assert loaded.unit is None
            assert loaded.period is None
            assert loaded.category is None
            assert loaded.source_file is None


class TestCreateAllIdempotent:
    def test_create_all_twice_does_not_raise(self) -> None:
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        Base.metadata.create_all(engine)
        inspector = inspect(engine)
        assert "collections" in inspector.get_table_names()
        assert "assets" in inspector.get_table_names()
        assert "business_metrics" in inspector.get_table_names()
