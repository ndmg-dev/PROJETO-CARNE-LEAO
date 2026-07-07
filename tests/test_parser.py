import pytest
from datetime import date
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.parser import parse_date, parse_value, extract_description

def test_extract_description():
    assert extract_description("RECIBO MEDICO 123.pdf") == "RECIBO MEDICO 123"
    assert extract_description("  Pagamento  .jpg  ") == "Pagamento"

def test_parse_date():
    assert parse_date("Data de pagamento: 15/04/2024") == date(2024, 4, 15)
    assert parse_date("Vencimento 10-05-2024 valor...") == date(2024, 5, 10)
    assert parse_date("Sem data aqui") is None

def test_parse_value_high_confidence():
    text = "Valor pago: R$ 1.234,56"
    val, conf = parse_value(text)
    assert val == 1234.56
    assert conf is True

def test_parse_value_no_currency_symbol():
    text = "Total: 500,00"
    val, conf = parse_value(text)
    assert val == 500.0
    assert conf is True

def test_parse_value_low_confidence():
    text = "Apenas o número 150,00 no meio do texto sem palavra chave"
    val, conf = parse_value(text)
    assert val == 150.0
    assert conf is False

def test_parse_value_thousands_separator():
    text = "Valor do documento: R$ 10.500,99"
    val, conf = parse_value(text)
    assert val == 10500.99
    assert conf is True
