import re


def normalize_cnpj(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def format_cnpj(digits: str) -> str:
    d = normalize_cnpj(digits)
    if len(d) != 14:
        return d
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def _calc_digit(numbers: list[int], weights: list[int]) -> int:
    total = sum(n * w for n, w in zip(numbers, weights))
    remainder = total % 11
    return 0 if remainder < 2 else 11 - remainder


def validate_cnpj(value: str) -> bool:
    digits = normalize_cnpj(value)
    if len(digits) != 14:
        return False
    if len(set(digits)) == 1:
        return False

    numbers = [int(c) for c in digits]
    first = _calc_digit(numbers[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    if first != numbers[12]:
        return False
    second = _calc_digit(numbers[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return second == numbers[13]
