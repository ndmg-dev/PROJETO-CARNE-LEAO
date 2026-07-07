import os
import re
from datetime import datetime
from .config import DATE_PATTERN, VALUE_PATTERN, VALUE_KEYWORDS

def extract_description(filename):
    """Uses the filename without extension as the description."""
    base = os.path.splitext(filename)[0]
    return base.strip()

def parse_date(text):
    """Finds the first valid date in DD/MM/YYYY, DD.MM.YYYY, or DD-MM-YY formats."""
    matches = re.finditer(DATE_PATTERN, text)
    for match in matches:
        date_str = match.group(0)
        date_str_clean = date_str.replace("-", "/").replace(".", "/")
        parts = date_str_clean.split("/")
        
        if len(parts) == 3:
            # Handle 2-digit year
            if len(parts[2]) == 2:
                year = int(parts[2])
                parts[2] = f"20{year}" if year < 50 else f"19{year}"
            
            date_str_clean = f"{parts[0]}/{parts[1]}/{parts[2]}"
            
        try:
            dt = datetime.strptime(date_str_clean, "%d/%m/%Y")
            return dt.date()
        except ValueError:
            continue
    return None

def parse_value(text):
    """
    Finds a conservative monetary value. 
    Returns (value_float, confidence_boolean).
    If confidence is low, returns the largest value found with (val, False).
    """
    text_lower = text.lower()
    
    matches = list(re.finditer(VALUE_PATTERN, text, re.IGNORECASE))
    if not matches:
        return None, False
        
    def to_float(val_str):
        val_str = re.sub(r"[^\d,]", "", val_str) # Keep only digits and comma
        val_str = val_str.replace(",", ".")
        try:
            return float(val_str)
        except ValueError:
            return None

    best_value = None
    max_val = 0.0
    
    for match in matches:
        val_float = to_float(match.group(0))
        if val_float is None or val_float == 0:
            continue
            
        if val_float > max_val:
            max_val = val_float
            best_value = val_float
            
        start_idx = match.start()
        # Look at the text just before this match (e.g., 60 characters before)
        context_before = text_lower[max(0, start_idx - 60):start_idx]
        
        # Check if any keyword is in the context
        is_near_keyword = any(kw in context_before for kw in VALUE_KEYWORDS)
        
        if is_near_keyword:
            # Return immediately on the first high-confidence match
            return val_float, True
            
    # If we found matches but none near keywords, return the largest one with low confidence
    if best_value is not None:
        return best_value, False
        
    return None, False
