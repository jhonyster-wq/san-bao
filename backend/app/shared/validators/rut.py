import re
from typing import Optional


class ChileanRUT:
    """
    Validador y formateador de RUT chileno (Cédula de Identidad / Rol Único Tributario).
    Aplica el algoritmo estándar de Módulo 11.
    """

    @staticmethod
    def clean(rut_str: str) -> str:
        """Limpia el RUT removiendo puntos, espacios y convierte el dígito verificador a mayúscula."""
        if not rut_str:
            return ""
        cleaned = re.sub(r"[^0-9kK]", "", str(rut_str).strip())
        if not cleaned:
            return ""
        body = cleaned[:-1]
        dv = cleaned[-1].upper()
        return f"{body}-{dv}"

    @staticmethod
    def calculate_dv(rut_body: int | str) -> str:
        """Calcula el dígito verificador para un cuerpo de RUT dado usando algoritmo Módulo 11."""
        body_str = str(rut_body).replace(".", "").replace("-", "")
        if not body_str.isdigit():
            raise ValueError("El cuerpo del RUT debe ser numérico")

        reversed_digits = [int(d) for d in reversed(body_str)]
        factors = [2, 3, 4, 5, 6, 7]
        total = 0
        for i, digit in enumerate(reversed_digits):
            factor = factors[i % len(factors)]
            total += digit * factor

        remainder = 11 - (total % 11)
        if remainder == 11:
            return "0"
        elif remainder == 10:
            return "K"
        else:
            return str(remainder)

    @classmethod
    def validate(cls, rut_str: str) -> bool:
        """Verifica si un RUT es formalmente válido según el algoritmo Módulo 11."""
        if not rut_str or not isinstance(rut_str, str):
            return False

        cleaned = re.sub(r"[^0-9kK]", "", rut_str.strip())
        if len(cleaned) < 2:
            return False

        body = cleaned[:-1]
        dv = cleaned[-1].upper()

        if not body.isdigit() or int(body) == 0:
            return False

        expected_dv = cls.calculate_dv(body)
        return dv == expected_dv

    @classmethod
    def format(cls, rut_str: str, with_dots: bool = True) -> str:
        """Formatea un RUT a su representación visual estándar (ej: 12.345.678-K o 12345678-K)."""
        cleaned = cls.clean(rut_str)
        if not cleaned or "-" not in cleaned:
            return rut_str

        body, dv = cleaned.split("-")
        if not with_dots:
            return f"{body}-{dv}"

        # Insertar puntos
        formatted_body = ""
        for i, char in enumerate(reversed(body)):
            if i > 0 and i % 3 == 0:
                formatted_body = "." + formatted_body
            formatted_body = char + formatted_body

        return f"{formatted_body}-{dv}"
