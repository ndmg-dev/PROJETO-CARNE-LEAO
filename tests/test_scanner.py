import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scanner import is_valid_month_folder

def test_is_valid_month_folder():
    assert is_valid_month_folder("01 - JANEIRO") is True
    assert is_valid_month_folder("12 - DEZEMBRO") is True
    assert is_valid_month_folder("05-MAIO") is True
    assert is_valid_month_folder("03 - MARÇO") is True
    assert is_valid_month_folder("13 - MES INVALIDO") is False
    assert is_valid_month_folder("Janeiro") is False
    assert is_valid_month_folder("00 - TESTE") is False
