import os
import argparse
import logging
import sys

# Ensure the src directory is in the path to allow direct execution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import DEFAULT_BASE_PATH
from src.scanner import scan_folders
from src.extractor import extract_text
from src.parser import extract_description, parse_date, parse_value
from src.exporter import export_to_excel

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Expense Consolidation Tool for Monthly IRPF/Carnê-Leão")
    parser.add_argument("--base-path", type=str, default=DEFAULT_BASE_PATH,
                        help="Base path for the monthly folders")
    parser.add_argument("--output", type=str, default="despesas_carne_leao_2024.xlsx",
                        help="Output Excel file path")
    args = parser.parse_args()
    
    base_path = args.base_path
    output_path = args.output
    
    logging.info(f"Starting scan on: {base_path}")
    try:
        folders_data = scan_folders(base_path)
    except ValueError as e:
        logging.error(e)
        return
        
    logging.info(f"Found {len(folders_data)} valid monthly folder(s).")
    
    successful_records = []
    pending_records = []
    total_files = 0
    
    for month_num, folder_info in folders_data.items():
        files = folder_info['files']
        total_files += len(files)
        
        for filepath in files:
            filename = os.path.basename(filepath)
            logging.info(f"Processing ({folder_info['folder_name']}): {filename} ...")
            desc = extract_description(filename)
            
            # Extract text
            text = extract_text(filepath)
            
            if not text.strip():
                pending_records.append({
                    "month": folder_info['folder_name'],
                    "filename": filename,
                    "filepath": filepath,
                    "status": "Falha Extração",
                    "motivo": "Texto não encontrado ou OCR falhou/indisponível"
                })
                continue
                
            # Parse Date and Value
            date_val = parse_date(text)
            amount_val, confidence = parse_value(text)
            
            if date_val or amount_val:
                status = "OK"
                motivos = []
                if not date_val:
                    motivos.append("Data Ausente")
                if not amount_val:
                    motivos.append("Valor Ausente")
                elif not confidence:
                    motivos.append("Valor - Baixa Confiança")
                    
                if motivos:
                    status = " | ".join(motivos)
                    
                successful_records.append({
                    "month": folder_info['folder_name'],
                    "date": date_val if date_val else "",
                    "description": desc,
                    "value": amount_val if amount_val else "",
                    "filename": filename,
                    "filepath": filepath,
                    "status": status
                })
            else:
                pending_records.append({
                    "month": folder_info['folder_name'],
                    "filename": filename,
                    "filepath": filepath,
                    "status": "Revisão Manual",
                    "motivo": "Dados não encontrados"
                })
                
    logging.info(f"Total files processed: {total_files}")
    logging.info(f"Successfully extracted: {len(successful_records)}")
    logging.info(f"Requires manual review: {len(pending_records)}")
    
    # Export to Excel
    export_to_excel(successful_records, pending_records, output_path)
    logging.info(f"Consolidated Excel saved to: {os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()
