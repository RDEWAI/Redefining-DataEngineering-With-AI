"""Tests for silver transformation business rules."""

from __future__ import annotations

from datetime import date

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    DateType,
    DecimalType,
    IntegerType,
    StringType,
    StructField,
    StructType,
)

from patient_360.silver.transformations import (
    transform_allergy_fields,
    transform_condition_fields,
    transform_encounter_fields,
    transform_medication_fields,
    transform_patient_fields,
)


class TestPatientTransformations:
    def test_full_name_concatenated(self, spark: SparkSession):
        """TR-001: full_name = TRIM(CONCAT_WS(' ', prefix, first, middle, last, suffix))."""
        schema = StructType([
            StructField("id",     StringType(), True),
            StructField("prefix", StringType(), True),
            StructField("first",  StringType(), True),
            StructField("middle", StringType(), True),
            StructField("last",   StringType(), True),
            StructField("suffix", StringType(), True),
            StructField("ssn",      StringType(), True),
            StructField("birthdate", DateType(),   True),
            StructField("deathdate", DateType(),   True),
            StructField("address", StringType(), True),
            StructField("city",    StringType(), True),
            StructField("state",   StringType(), True),
            StructField("zip",     StringType(), True),
            StructField("phone",   StringType(), True),
            StructField("gender",    StringType(), True),
            StructField("race",      StringType(), True),
            StructField("ethnicity", StringType(), True),
        ])
        row = ("p1", "Dr.", "Alice", "M", "Smith", "Jr.",
               "123-45-6789", date(1980, 1, 1), None,
               "1 Main St", "Boston", "MA", "02101", "555-1234",
               "F", "white", "nonhispanic")
        df = spark.createDataFrame([row], schema=schema)
        result = transform_patient_fields(df).collect()[0]
        assert result.full_name == "Dr. Alice M Smith Jr."

    def test_full_name_nulls_skipped(self, spark: SparkSession):
        """TR-001: NULL name parts should be skipped in concat."""
        schema = StructType([
            StructField("id",     StringType(), True),
            StructField("prefix", StringType(), True),
            StructField("first",  StringType(), True),
            StructField("middle", StringType(), True),
            StructField("last",   StringType(), True),
            StructField("suffix", StringType(), True),
            StructField("ssn",      StringType(), True),
            StructField("birthdate", DateType(),   True),
            StructField("deathdate", DateType(),   True),
            StructField("address", StringType(), True),
            StructField("city",    StringType(), True),
            StructField("state",   StringType(), True),
            StructField("zip",     StringType(), True),
            StructField("phone",   StringType(), True),
            StructField("gender",    StringType(), True),
            StructField("race",      StringType(), True),
            StructField("ethnicity", StringType(), True),
        ])
        row = ("p1", None, "Alice", None, "Smith", None,
               None, date(1980, 1, 1), None,
               None, None, None, None, None, "F", None, None)
        df = spark.createDataFrame([row], schema=schema)
        result = transform_patient_fields(df).collect()[0]
        assert result.full_name == "Alice Smith"

    def test_ssn_masked(self, spark: SparkSession):
        """TR-003: ssn_masked = 'XXX-XX-' + last 4 digits."""
        schema = StructType([
            StructField("id",     StringType(), True),
            StructField("prefix", StringType(), True),
            StructField("first",  StringType(), True),
            StructField("middle", StringType(), True),
            StructField("last",   StringType(), True),
            StructField("suffix", StringType(), True),
            StructField("ssn",      StringType(), True),
            StructField("birthdate", DateType(),   True),
            StructField("deathdate", DateType(),   True),
            StructField("address", StringType(), True),
            StructField("city",    StringType(), True),
            StructField("state",   StringType(), True),
            StructField("zip",     StringType(), True),
            StructField("phone",   StringType(), True),
            StructField("gender",    StringType(), True),
            StructField("race",      StringType(), True),
            StructField("ethnicity", StringType(), True),
        ])
        row = ("p1", None, "Alice", None, "Smith", None,
               "123-45-6789", date(1980, 1, 1), None,
               None, None, None, None, None, "F", None, None)
        df = spark.createDataFrame([row], schema=schema)
        result = transform_patient_fields(df).collect()[0]
        assert result.ssn_masked == "XXX-XX-6789"

    def test_deceased_flag_true_when_deathdate_set(self, spark: SparkSession):
        """TR-004: deceased_flag=True when deathdate is not null."""
        schema = StructType([
            StructField("id", StringType(), True),
            StructField("prefix", StringType(), True), StructField("first", StringType(), True),
            StructField("middle", StringType(), True), StructField("last", StringType(), True),
            StructField("suffix", StringType(), True), StructField("ssn", StringType(), True),
            StructField("birthdate", DateType(), True), StructField("deathdate", DateType(), True),
            StructField("address", StringType(), True), StructField("city", StringType(), True),
            StructField("state", StringType(), True), StructField("zip", StringType(), True),
            StructField("phone", StringType(), True), StructField("gender", StringType(), True),
            StructField("race", StringType(), True), StructField("ethnicity", StringType(), True),
        ])
        row = ("p1", None, "Alice", None, "Smith", None, None,
               date(1980, 1, 1), date(2020, 6, 15),
               None, None, None, None, None, "F", None, None)
        df = spark.createDataFrame([row], schema=schema)
        result = transform_patient_fields(df).collect()[0]
        assert result.deceased_flag is True

    def test_deceased_flag_false_when_alive(self, spark: SparkSession):
        """TR-004: deceased_flag=False when deathdate is null."""
        schema = StructType([
            StructField("id", StringType(), True),
            StructField("prefix", StringType(), True), StructField("first", StringType(), True),
            StructField("middle", StringType(), True), StructField("last", StringType(), True),
            StructField("suffix", StringType(), True), StructField("ssn", StringType(), True),
            StructField("birthdate", DateType(), True), StructField("deathdate", DateType(), True),
            StructField("address", StringType(), True), StructField("city", StringType(), True),
            StructField("state", StringType(), True), StructField("zip", StringType(), True),
            StructField("phone", StringType(), True), StructField("gender", StringType(), True),
            StructField("race", StringType(), True), StructField("ethnicity", StringType(), True),
        ])
        row = ("p1", None, "Alice", None, "Smith", None, None,
               date(1980, 1, 1), None,
               None, None, None, None, None, "F", None, None)
        df = spark.createDataFrame([row], schema=schema)
        result = transform_patient_fields(df).collect()[0]
        assert result.deceased_flag is False


class TestAllergyTransformations:
    def _schema(self):
        return StructType([
            StructField("patient",      StringType(), True),
            StructField("encounter",    StringType(), True),
            StructField("code",         StringType(), True),
            StructField("description",  StringType(), True),
            StructField("type",         StringType(), True),
            StructField("severity1",    StringType(), True),
            StructField("description1", StringType(), True),
            StructField("start",        DateType(),   True),
        ])

    def test_severity_display_null_becomes_unknown(self, spark: SparkSession):
        """TR-012: NULL severity → 'Unknown severity'."""
        row = ("p1", "e1", "code", "Peanut allergy", "allergy", None, None, date(2020, 1, 1))
        df = spark.createDataFrame([row], self._schema())
        result = transform_allergy_fields(df).collect()[0]
        assert result.severity_display == "Unknown severity"

    def test_severity_display_preserved_when_set(self, spark: SparkSession):
        """TR-012: Non-null severity is preserved as-is."""
        row = ("p1", "e1", "code", "Peanut allergy", "allergy", "SEVERE", None, date(2020, 1, 1))
        df = spark.createDataFrame([row], self._schema())
        result = transform_allergy_fields(df).collect()[0]
        assert result.severity_display == "SEVERE"

    def test_severity_sort_order_severe(self, spark: SparkSession):
        """TR-013: SEVERE → sort_order 1."""
        row = ("p1", "e1", "code", "desc", "allergy", "SEVERE", None, date(2020, 1, 1))
        df = spark.createDataFrame([row], self._schema())
        result = transform_allergy_fields(df).collect()[0]
        assert result.severity_sort_order == 1

    def test_severity_sort_order_unknown(self, spark: SparkSession):
        """TR-013: NULL severity → sort_order 4."""
        row = ("p1", "e1", "code", "desc", "allergy", None, None, date(2020, 1, 1))
        df = spark.createDataFrame([row], self._schema())
        result = transform_allergy_fields(df).collect()[0]
        assert result.severity_sort_order == 4


class TestMedicationTransformations:
    def _schema(self):
        return StructType([
            StructField("patient",           StringType(),    True),
            StructField("payer",             StringType(),    True),
            StructField("encounter",         StringType(),    True),
            StructField("code",              StringType(),    True),
            StructField("description",       StringType(),    True),
            StructField("start",             DateType(),      True),
            StructField("stop",              DateType(),      True),
            StructField("totalcost",         DecimalType(18, 2), True),
            StructField("dispenses",         IntegerType(),   True),
            StructField("base_cost",         DecimalType(18, 2), True),
            StructField("payer_coverage",    DecimalType(18, 2), True),
            StructField("reasoncode",        StringType(),    True),
            StructField("reasondescription", StringType(),    True),
        ])

    def test_active_flag_null_stop(self, spark: SparkSession):
        """TR-010: stop IS NULL → is_active=True."""
        row = ("p1", None, "e1", "code", "desc", date(2020, 1, 1), None,
               None, 1, None, None, None, None)
        df = spark.createDataFrame([row], self._schema())
        result = transform_medication_fields(df).collect()[0]
        assert result.is_active is True

    def test_payer_null_defaults_to_self_pay(self, spark: SparkSession):
        """TR-011: NULL payer → 'Self-Pay / Not Documented'."""
        row = ("p1", None, "e1", "code", "desc", date(2020, 1, 1), None,
               None, 1, None, None, None, None)
        df = spark.createDataFrame([row], self._schema())
        result = transform_medication_fields(df).collect()[0]
        assert result.payer_display == "Self-Pay / Not Documented"
