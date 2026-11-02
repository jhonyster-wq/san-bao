import pytest
from app.shared.validators.rut import ChileanRUT


def test_calculate_dv_standard():
    # Casos de prueba conocidos de RUT chileno con algoritmo Módulo 11
    assert ChileanRUT.calculate_dv("11111111") == "1"
    assert ChileanRUT.calculate_dv("77123456") == "9"
    assert ChileanRUT.calculate_dv("76987654") == "5"
    assert ChileanRUT.calculate_dv("12345678") == "5"


def test_validate_valid_ruts():
    assert ChileanRUT.validate("11.111.111-1") is True
    assert ChileanRUT.validate("11111111-1") is True
    assert ChileanRUT.validate("77.123.456-9") is True
    assert ChileanRUT.validate("76.987.654-5") is True
    assert ChileanRUT.validate("12.345.678-5") is True


def test_validate_invalid_ruts():
    assert ChileanRUT.validate("11.111.111-2") is False
    assert ChileanRUT.validate("77.123.456-7") is False  # DV incorrecto
    assert ChileanRUT.validate("12345678-0") is False
    assert ChileanRUT.validate("invalido") is False
    assert ChileanRUT.validate("") is False
    assert ChileanRUT.validate(None) is False


def test_format_rut():
    assert ChileanRUT.format("11111111-1", with_dots=True) == "11.111.111-1"
    assert ChileanRUT.format("11.111.111-1", with_dots=False) == "11111111-1"
    assert ChileanRUT.format("771234569", with_dots=True) == "77.123.456-9"
