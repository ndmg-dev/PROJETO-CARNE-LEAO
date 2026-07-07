import os
import logging
import fitz  # PyMuPDF

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
    
    # Optional: Automatically find Tesseract on Windows if it's not in PATH
    if os.name == 'nt':
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe")
        ]
        for t_path in common_paths:
            if os.path.exists(t_path):
                pytesseract.pytesseract.tesseract_cmd = t_path
                break
                
    # Point TESSDATA_PREFIX to our local project 'tessdata' folder
    tessdata_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'tessdata')
    if os.path.exists(tessdata_path):
        os.environ['TESSDATA_PREFIX'] = tessdata_path

                
except ImportError:
    OCR_AVAILABLE = False
except Exception:
    OCR_AVAILABLE = False

logger = logging.getLogger(__name__)

def extract_text_from_pdf(filepath):
    text = ""
    try:
        doc = fitz.open(filepath)
        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                text += page_text + "\n"
                
        # If very little text, try OCR on the pages (scanned PDF)
        if len(text.strip()) < 50 and OCR_AVAILABLE:
            try:
                # Check if Tesseract is in PATH by running a dummy command
                pytesseract.get_tesseract_version()
                
                ocr_text = ""
                for page in doc:
                    pix = page.get_pixmap(dpi=200)
                    # Convert fitz pixmap to PIL Image
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    page_text = pytesseract.image_to_string(img, lang="por") # Assume Portuguese
                    ocr_text += page_text + "\n"
                text = ocr_text
            except Exception as e:
                logger.warning(f"OCR failed for {filepath}: {e}")
                
        doc.close()
    except Exception as e:
        logger.error(f"Failed to read PDF {filepath}: {e}")
    return text

def extract_text_from_image(filepath):
    text = ""
    if not OCR_AVAILABLE:
        logger.warning(f"OCR not available to read image {filepath}")
        return text
        
    try:
        pytesseract.get_tesseract_version()
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img, lang="por")
    except Exception as e:
        logger.warning(f"OCR failed for image {filepath}: {e}")
    return text

def extract_text(filepath):
    """Extracts text from a document (PDF or Image). Uses OCR as fallback."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(filepath)
    elif ext in {".jpg", ".jpeg", ".png"}:
        return extract_text_from_image(filepath)
    return ""
