"""
Módulo de Extração via Inteligência Artificial (OpenAI)
Lê PDFs/Imagens, converte para base64 e envia para o modelo (ex: GPT-4o-mini).
"""
import os
import io
import json
import base64
from PIL import Image
from openai import OpenAI

from . import config

PROMPT = """Você é um assistente especializado em contabilidade brasileira e IRPF.
Sua missão é extrair dados de despesas de um comprovante de pagamento.
O usuário vai enviar a imagem do documento.
Você DEVE retornar APENAS um JSON válido. Não inclua markdown, não inclua blocos de código (```json), apenas o texto JSON limpo.

Extraia as seguintes chaves:
- "data_pagamento": Data em que o pagamento foi realizado no formato DD/MM/YYYY. Se não encontrar, retorne null.
- "valor": Valor do pagamento como número float (ex: 1250.50). Não inclua 'R$' e use ponto para decimais. Se não encontrar, retorne null.
- "tipo_documento": Um resumo muito curto (1-3 palavras) do que é o documento (ex: "Boleto", "Recibo Médico", "Comprovante Pix").
- "confianca": Qual sua confiança na extração da data e valor? Use "alta", "media" ou "baixa".
"""

def get_image_base64(file_ref, filename):
    """
    Converte o documento referenciado em base64 para envio à IA.

    - Em modo Google Drive (config.USE_GOOGLE_DRIVE): file_ref é o ID do
      arquivo no Drive; o conteúdo é baixado via API.
    - Em modo local (fallback): file_ref é o caminho no filesystem.

    `filename` é usado apenas para determinar a extensão (IDs do Drive não
    têm extensão).

    Se for imagem, converte direto para base64.
    Se for PDF, renderiza a primeira página usando PyMuPDF e converte para base64.
    """
    ext = os.path.splitext(filename)[1].lower()

    if config.USE_GOOGLE_DRIVE:
        from .drive_client import get_drive_service, download_file
        service = get_drive_service()
        buf = download_file(service, file_ref)

        if ext in {".jpg", ".jpeg", ".png"}:
            return base64.b64encode(buf.getvalue()).decode('utf-8')

        elif ext == ".pdf":
            import fitz  # PyMuPDF
            doc = fitz.open(stream=buf.getvalue(), filetype="pdf")
            page = doc[0]
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            doc.close()

            out_buf = io.BytesIO()
            img.save(out_buf, format="JPEG")
            return base64.b64encode(out_buf.getvalue()).decode('utf-8')

        else:
            raise ValueError(f"Formato não suportado para extração via IA: {ext}")

    # Modo local (fallback de desenvolvimento)
    if ext in {".jpg", ".jpeg", ".png"}:
        with open(file_ref, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    elif ext == ".pdf":
        import fitz  # PyMuPDF
        doc = fitz.open(file_ref)
        page = doc[0]
        # Reduzir DPI para economizar tokens sem perder muita qualidade
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        return base64.b64encode(buf.getvalue()).decode('utf-8')

    else:
        raise ValueError(f"Formato não suportado para extração via IA: {ext}")


def extract_with_ai(file_ref, filename, api_key, model_name="gpt-4o-mini"):
    """
    Envia a imagem para a OpenAI e retorna um dicionário JSON.
    """
    if not api_key:
        return {"error": "API Key não fornecida."}

    try:
        base64_image = get_image_base64(file_ref, filename)
        
        client = OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300,
            temperature=0.0
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Limpar possiveis formatações indesejadas (markdown de código)
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
            
        result_text = result_text.strip()
        
        try:
            data = json.loads(result_text)
            return data
        except json.JSONDecodeError:
            return {"error": f"O modelo não retornou um JSON válido. Retorno bruto: {result_text}"}
            
    except Exception as e:
        return {"error": str(e)}
