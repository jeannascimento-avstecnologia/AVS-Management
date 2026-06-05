from src.cnpj.validator import format_cnpj, normalize_cnpj, validate_cnpj


def test_normalize_cnpj():
    assert normalize_cnpj("12.345.678/0001-95") == "12345678000195"


def test_format_cnpj():
    assert format_cnpj("12345678000195") == "12.345.678/0001-95"


def test_validate_cnpj_known_valid():
    assert validate_cnpj("19.131.243/0001-97") is True


def test_validate_cnpj_invalid():
    assert validate_cnpj("00.000.000/0000-00") is False
    assert validate_cnpj("123") is False
