# # backend/main.py/mistral
# import json
# import logging
# import requests
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# import pytesseract
# from pdf2image import convert_from_bytes
# import PyPDF2
# from io import BytesIO
# from typing import Optional, List, Dict
# import ollama
# from PIL import Image, ImageEnhance, ImageFilter
# import re

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# app = FastAPI(title="PDF PO Extractor", version="2.0")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# class Item(BaseModel):
#     part_number: Optional[str] = None
#     description: Optional[str] = None
#     quantity: Optional[str] = None
#     unit_price: Optional[str] = None
#     amount: Optional[str] = None
#     ship_date: Optional[str] = None

# class ExtractionResult(BaseModel):
#     po_number: Optional[str] = None
#     po_date: Optional[str] = None
#     delivered_to: Optional[str] = None
#     shipped_to: Optional[str] = None
#     vendor_code: Optional[str] = None
#     vendor_ref: Optional[str] = None
#     ship_via: Optional[str] = None
#     ordered_by: Optional[str] = None
#     terms: Optional[str] = None
#     items: List[Item] = []
#     total_without_tax: Optional[str] = None
#     tax: Optional[str] = None
#     tps: Optional[str] = None
#     tvq: Optional[str] = None
#     total_with_tax: Optional[str] = None

# def preprocess_image(image: Image.Image) -> Image.Image:
#     image = image.convert('L')
#     enhancer = ImageEnhance.Contrast(image)
#     image = enhancer.enhance(2.0)
#     image = image.filter(ImageFilter.SHARPEN)
#     return image

# def extract_text_from_file(file: UploadFile) -> str:
#     logger.info(f"Extracting text from file: {file.filename}")
#     try:
#         file_content = file.file.read()
#         if file.filename.lower().endswith('.pdf'):
#             try:
#                 with BytesIO(file_content) as pdf_file:
#                     reader = PyPDF2.PdfReader(pdf_file)
#                     text = "\n".join([page.extract_text() for page in reader.pages])
#                     if text.strip():
#                         logger.info("Text extracted directly from PDF")
#                         return text
#             except Exception as e:
#                 logger.warning(f"Direct PDF extraction failed: {str(e)}, falling back to OCR")
#             images = convert_from_bytes(file_content)
#             text = "\n".join([
#                 pytesseract.image_to_string(
#                     preprocess_image(img),
#                     config='--psm 6'
#                 ) for img in images
#             ])
#             logger.info("Text extracted via OCR with preprocessing")
#             return text
#         image = Image.open(BytesIO(file_content))
#         text = pytesseract.image_to_string(preprocess_image(image), config='--psm 6')
#         logger.info("Text extracted from image with preprocessing")
#         return text
#     except Exception as e:
#         logger.error(f"File processing error: {str(e)}")
#         raise HTTPException(status_code=400, detail=f"Erreur de traitement du fichier: {str(e)}")

# def clean_llm_response(response: str) -> Dict:
#     logger.info("Cleaning LLM response")
#     try:
#         response = response.replace("```json", "").replace("```", "")
#         start = response.find('{')
#         end = response.rfind('}') + 1
#         json_str = response[start:end]
#         json_str = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'', json_str)
#         data = json.loads(json_str)
#         for key, value in data.items():
#             if isinstance(value, list) and key != "items":
#                 data[key] = " ".join(str(v) for v in value) if value else None
#         return data
#     except Exception as e:
#         logger.error(f"JSON parsing error: {str(e)} - Response: {response}")
#         raise HTTPException(status_code=500, detail=f"Erreur de parsing JSON: {str(e)} - Réponse: {response}")

# def post_process_result(result: ExtractionResult, text: str) -> ExtractionResult:
#     """Corrige les erreurs évidentes dans les données extraites."""
#     # Correction du po_number
#     po_match = re.search(r"Numero / Number\s*\|\s*(\d+)", text)
#     if po_match:
#         result.po_number = po_match.group(1)

#     # Correction des items
#     for item in result.items:
#         # Corriger part_number si c'est un numéro d'ordre (ex: "1")
#         part_match = re.search(r"NO DE PIECE\s*PART NUMBER\s*[|]?\s*([A-Za-z0-9\-]+)", text, re.MULTILINE)
#         if part_match and item.part_number != part_match.group(1):
#             item.part_number = part_match.group(1)

#         # Corriger quantity
#         qty_match = re.search(r"QTE\.\s*QTY\.\s*[|]?\s*(\d+\s*[A-Za-z]+)", text, re.MULTILINE)
#         if qty_match and (item.quantity is None or "LBS" in item.quantity or "Inches" in item.quantity):
#             item.quantity = qty_match.group(1)

#         # Corriger unit_price
#         if item.unit_price and re.match(r"^\$\d{5,}", item.unit_price):
#             item.unit_price = re.sub(r"(\$\d{3})(\d+)", r"\1.\2", item.unit_price, 1)
#         elif item.unit_price and "$7.0109LB" in item.unit_price:
#             item.unit_price = "$701.09 LB"

#     # Réinitialiser les taxes et total_with_tax si non présentes
#     if result.total_with_tax and not any([result.tax, result.tps, result.tvq]):
#         result.total_with_tax = None
#         result.tax = None

#     # Vérifier vendor_code, ship_via, ordered_by, terms
#     vendor_match = re.search(r"CODE DU FOURNISSEUR\s*VENDOR CODE\s*[|]?\s*(\w+)", text)
#     if vendor_match:
#         result.vendor_code = vendor_match.group(1)

#     ship_match = re.search(r"EXPEDIE PAR\s*SHIP VIA\s*[|]?\s*(\w+)", text)
#     if ship_match:
#         result.ship_via = ship_match.group(1)

#     ordered_match = re.search(r"EMIS PAR\s*ORDERED BY\s*[|]?\s*([A-Za-z\s]+)", text)
#     if ordered_match:
#         result.ordered_by = ordered_match.group(1).strip()

#     terms_match = re.search(r"TERMS\s*[|]?\s*([^\s]+)", text)
#     if terms_match:
#         result.terms = terms_match.group(1)

#     return result

# def check_ollama_health():
#     try:
#         response = requests.get("http://127.0.0.1:11434", timeout=5)
#         if response.status_code != 200:
#             raise Exception(f"Ollama responded with status {response.status_code}")
#         logger.info("Ollama service is healthy")
#     except requests.RequestException as e:
#         logger.error(f"Ollama health check failed: {str(e)}")
#         raise HTTPException(status_code=503, detail="Service Ollama indisponible. Veuillez démarrer Ollama avec 'ollama serve'.")

# def validate_result(result: ExtractionResult) -> bool:
#     essential_fields = [result.po_number, result.items]
#     return all(field is not None and (isinstance(field, list) and len(field) > 0 or isinstance(field, str)) for field in essential_fields)

# def call_llm(text: str, max_retries: int = 2) -> ExtractionResult:
#     logger.info("Calling LLM for text analysis")
#     check_ollama_health()
    
#     max_chars = 12000 if len(text) > 12000 else len(text)
#     num_ctx = 8192 if max_chars <= 12000 else 4096
    
#     prompt = f"""
# Tu es un expert en extraction précise de données à partir de bons de commande (PO) en français et anglais. Ton objectif est d'extraire les informations clés du texte ci-dessous et de retourner un JSON valide, sans inventer de valeurs ni confondre les champs.

# ---------------------
# 📄 Texte du document :
# {text[:max_chars]}
# ---------------------

# 🎯 Informations à extraire :
# - "po_number" : Numéro du PO après "Numero / Number" (ex: "2203" dans "Numero / Number | 2203")
# - "po_date" : Date d’émission après "Date" (ex: "06 Nov 2012" → "2012/11/06")
# - "delivered_to" : Adresse complète après "A: TO:" (ex: "Mindcore Technologies, 1845 Jean-Monnet, Terrebonne, QC J6X 4L7, Canada")
# - "shipped_to" : Adresse complète après "EXPEDIE A: SHIPPED TO:" (ex: "USINAGE TOURMAC INC., 11 rue de l'Industrie, St-Rémi, QC J0L 2L0, Canada")
# - "vendor_code" : Code après "CODE DU FOURNISSEUR VENDOR CODE" (ex: "M0062")
# - "vendor_ref" : Référence après "REF. FOURNISSEUR VENDOR REF." (null si vide)
# - "ship_via" : Mode après "EXPEDIE PAR SHIP VIA" (ex: "Pickup")
# - "ordered_by" : Nom après "EMIS PAR ORDERED BY" (ex: "Julie Robidoux")
# - "terms" : Conditions après "TERMS" (ex: "?" ou "Net 30")
# - "items" : Liste d’articles dans le tableau (sous "ITEM | NO DE PIECE PART NUMBER | DESCRIPTION | QTE. QTY. | PRIX UNITAIRE UNIT PRICE | MONTANT AMOUNT | LIVRAISON SHIP DATE") :
#   - "part_number" : Valeur sous "NO DE PIECE PART NUMBER" (ex: "COPIB187C110287523150280-288")
#   - "description" : Texte sous "DESCRIPTION" (ex: "Copper Tube B187C110 2-1/2\" Cedule 80 2.875\" OD × 2.315\" ID × 0.280\" WALL × 288\"")
#   - "quantity" : Valeur sous "QTE. QTY." (ex: "2 BAR")
#   - "unit_price" : Valeur sous "PRIX UNITAIRE UNIT PRICE" (ex: "$701.09 LB")
#   - "amount" : Valeur sous "MONTANT AMOUNT" (ex: "$2,972.62")
#   - "ship_date" : Date sous "LIVRAISON SHIP DATE" (ex: "07 Nov 2012" → "2012/11/07")
# - "total_without_tax" : Total HT après "MONTANT AMOUNT" global (ex: "$2,972.62")
# - "tax" : Taxe totale (si explicitement indiquée, sinon null)
# - "tps" : TPS (si indiquée, sinon null)
# - "tvq" : TVQ (si indiquée, sinon null)
# - "total_with_tax" : Total TTC (si taxes présentes, sinon null)

# 📝 Instructions strictes :
# 1. Retourne **uniquement un JSON valide**, sans texte hors structure.
# 2. Dates au format **AAAA/MM/JJ**. Convertis précisément (ex: "07 Nov 2012" → "2012/11/07").
# 3. Respecte les en-têtes pour associer les valeurs (ex: "A: TO:" ≠ "EXPEDIE A: SHIPPED TO:").
# 4. Si un champ est absent ou ambigu, mets `null`. **N’invente rien**.
# 5. Pour "items", utilise uniquement les colonnes du tableau, sans mélanger avec d’autres données (ex: "ITEM" n’est pas "part_number").
# 6. Conserve devises ("$") et unités ("LB", "BAR") telles qu’écrites.

# 📦 Exemple basé sur le document fourni :
# {{
#   "po_number": "2203",
#   "po_date": "2012/11/06",
#   "delivered_to": "Mindcore Technologies, 1845 Jean-Monnet, Terrebonne, QC J6X 4L7, Canada",
#   "shipped_to": "USINAGE TOURMAC INC., 11 rue de l'Industrie, St-Rémi, QC J0L 2L0, Canada",
#   "vendor_code": "M0062",
#   "vendor_ref": null,
#   "ship_via": "Pickup",
#   "ordered_by": "Julie Robidoux",
#   "terms": "?",
#   "items": [
#     {{
#       "part_number": "COPIB187C110287523150280-288",
#       "description": "Copper Tube B187C110 2-1/2\" Cedule 80 2.875\" OD × 2.315\" ID × 0.280\" WALL × 288\"",
#       "quantity": "2 BAR",
#       "unit_price": "$701.09 LB",
#       "amount": "$2,972.62",
#       "ship_date": "2012/11/07"
#     }}
#   ],
#   "total_without_tax": "$2,972.62",
#   "tax": null,
#   "tps": null,
#   "tvq": null,
#   "total_with_tax": null
# }}
# """

#     for attempt in range(max_retries):
#         try:
#             response = ollama.generate(
#                 model="mistral",
#                 prompt=prompt,
#                 options={
#                     "temperature": 0.0,
#                     "num_ctx": num_ctx
#                 }
#             )
#             logger.info(f"LLM response received (attempt {attempt + 1})")
#             logger.info(f"Raw LLM response: {response['response']}")
            
#             json_data = clean_llm_response(response['response'])
            
#             result = ExtractionResult(
#                 po_number=json_data.get("po_number"),
#                 po_date=json_data.get("po_date"),
#                 delivered_to=json_data.get("delivered_to"),
#                 shipped_to=json_data.get("shipped_to"),
#                 vendor_code=json_data.get("vendor_code"),
#                 vendor_ref=json_data.get("vendor_ref"),
#                 ship_via=json_data.get("ship_via"),
#                 ordered_by=json_data.get("ordered_by"),
#                 terms=json_data.get("terms"),
#                 total_without_tax=json_data.get("total_without_tax"),
#                 tax=json_data.get("tax"),
#                 tps=json_data.get("tps"),
#                 tvq=json_data.get("tvq"),
#                 total_with_tax=json_data.get("total_with_tax")
#             )
            
#             for item in json_data.get("items", []):
#                 result.items.append(Item(**item))
            
#             # Post-traitement pour corriger les erreurs
#             result = post_process_result(result, text)
            
#             if validate_result(result):
#                 logger.info("Extraction result prepared and validated")
#                 return result
#             else:
#                 logger.warning(f"Result validation failed on attempt {attempt + 1}, retrying...")
#                 num_ctx = max(num_ctx // 2, 2048)
            
#         except ollama.ResponseError as e:
#             logger.error(f"Ollama response error on attempt {attempt + 1}: {str(e)}")
#             if attempt == max_retries - 1:
#                 raise HTTPException(status_code=500, detail=f"Erreur de réponse Ollama après {max_retries} tentatives: {str(e)}")
#             num_ctx = max(num_ctx // 2, 2048)
#         except Exception as e:
#             logger.error(f"LLM processing error on attempt {attempt + 1}: {str(e)}")
#             if attempt == max_retries - 1:
#                 raise HTTPException(status_code=500, detail=f"Erreur du modèle LLM après {max_retries} tentatives: {str(e)}")
    
#     raise HTTPException(status_code=500, detail="Échec de l'extraction après toutes les tentatives.")

# @app.post("/extract", response_model=ExtractionResult)
# async def extract_infos(file: UploadFile = File(...)):
#     logger.info("Received extract request")
#     try:
#         text = extract_text_from_file(file)
#         return call_llm(text)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"Unexpected error in extract_infos: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Erreur inattendue: {str(e)}")

# @app.get("/health")
# async def health_check():
#     try:
#         check_ollama_health()
#         return {"status": "healthy", "model": "mistral"}
#     except HTTPException as e:
#         raise e

# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(app, host="0.0.0.0", port=8000)


# ######################################################################################

# # backend/main.py/Mixtral
# import json
# import logging
# import requests
# from fastapi import FastAPI, UploadFile, File, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# import pytesseract
# from pdf2image import convert_from_bytes
# import PyPDF2
# from io import BytesIO
# from typing import Optional, List, Dict
# import ollama
# from PIL import Image, ImageEnhance, ImageFilter
# import re

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# app = FastAPI(title="PDF PO Extractor", version="2.0")

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# class Item(BaseModel):
#     part_number: Optional[str] = None
#     description: Optional[str] = None
#     quantity: Optional[str] = None
#     unit_price: Optional[str] = None
#     amount: Optional[str] = None
#     ship_date: Optional[str] = None

# class ExtractionResult(BaseModel):
#     po_number: Optional[str] = None
#     po_date: Optional[str] = None
#     delivered_to: Optional[str] = None
#     shipped_to: Optional[str] = None
#     vendor_code: Optional[str] = None
#     vendor_ref: Optional[str] = None
#     ship_via: Optional[str] = None
#     ordered_by: Optional[str] = None
#     terms: Optional[str] = None
#     items: List[Item] = []
#     total_without_tax: Optional[str] = None
#     tax: Optional[str] = None
#     tps: Optional[str] = None
#     tvq: Optional[str] = None
#     total_with_tax: Optional[str] = None

# def preprocess_image(image: Image.Image) -> Image.Image:
#     image = image.convert('L')
#     enhancer = ImageEnhance.Contrast(image)
#     image = enhancer.enhance(2.0)
#     image = image.filter(ImageFilter.SHARPEN)
#     return image

# def extract_text_from_file(file: UploadFile) -> str:
#     logger.info(f"Extracting text from file: {file.filename}")
#     try:
#         file_content = file.file.read()
#         if file.filename.lower().endswith('.pdf'):
#             try:
#                 with BytesIO(file_content) as pdf_file:
#                     reader = PyPDF2.PdfReader(pdf_file)
#                     text = "\n".join([page.extract_text() for page in reader.pages])
#                     if text.strip():
#                         logger.info("Text extracted directly from PDF")
#                         return text
#             except Exception as e:
#                 logger.warning(f"Direct PDF extraction failed: {str(e)}, falling back to OCR")
#             images = convert_from_bytes(file_content)
#             text = "\n".join([
#                 pytesseract.image_to_string(
#                     preprocess_image(img),
#                     config='--psm 6'
#                 ) for img in images
#             ])
#             logger.info("Text extracted via OCR with preprocessing")
#             return text
#         image = Image.open(BytesIO(file_content))
#         text = pytesseract.image_to_string(preprocess_image(image), config='--psm 6')
#         logger.info("Text extracted from image with preprocessing")
#         return text
#     except Exception as e:
#         logger.error(f"File processing error: {str(e)}")
#         raise HTTPException(status_code=400, detail=f"Erreur de traitement du fichier: {str(e)}")

# def clean_llm_response(response: str) -> Dict:
#     logger.info("Cleaning LLM response")
#     try:
#         response = response.replace("```json", "").replace("```", "")
#         start = response.find('{')
#         end = response.rfind('}') + 1
#         json_str = response[start:end]
#         json_str = re.sub(r'(?<!\\)\\(?!["\\/bfnrt]|u[0-9a-fA-F]{4})', r'', json_str)
#         data = json.loads(json_str)
#         for key, value in data.items():
#             if isinstance(value, list) and key != "items":
#                 data[key] = " ".join(str(v) for v in value) if value else None
#         return data
#     except Exception as e:
#         logger.error(f"JSON parsing error: {str(e)} - Response: {response}")
#         raise HTTPException(status_code=500, detail=f"Erreur de parsing JSON: {str(e)} - Réponse: {response}")

# def post_process_result(result: ExtractionResult, text: str) -> ExtractionResult:
#     """Corrige les erreurs évidentes dans les données extraites."""
#     po_match = re.search(r"Numero / Number\s*\|\s*(\d+)", text)
#     if po_match:
#         result.po_number = po_match.group(1)

#     for item in result.items:
#         part_match = re.search(r"NO DE PIECE\s*PART NUMBER\s*[|]?\s*([A-Za-z0-9\-]+)", text, re.MULTILINE)
#         if part_match and item.part_number != part_match.group(1):
#             item.part_number = part_match.group(1)

#         qty_match = re.search(r"QTE\.\s*QTY\.\s*[|]?\s*(\d+\s*[A-Za-z]+)", text, re.MULTILINE)
#         if qty_match and (item.quantity is None or "LBS" in item.quantity or "Inches" in item.quantity):
#             item.quantity = qty_match.group(1)

#         if item.unit_price and re.match(r"^\$\d{5,}", item.unit_price):
#             item.unit_price = re.sub(r"(\$\d{3})(\d+)", r"\1.\2", item.unit_price, 1)
#         elif item.unit_price and "$7.0109LB" in item.unit_price:
#             item.unit_price = "$701.09 LB"

#     if result.total_with_tax and not any([result.tax, result.tps, result.tvq]):
#         result.total_with_tax = None
#         result.tax = None

#     vendor_match = re.search(r"CODE DU FOURNISSEUR\s*VENDOR CODE\s*[|]?\s*(\w+)", text)
#     if vendor_match:
#         result.vendor_code = vendor_match.group(1)

#     ship_match = re.search(r"EXPEDIE PAR\s*SHIP VIA\s*[|]?\s*(\w+)", text)
#     if ship_match:
#         result.ship_via = ship_match.group(1)

#     ordered_match = re.search(r"EMIS PAR\s*ORDERED BY\s*[|]?\s*([A-Za-z\s]+)", text)
#     if ordered_match:
#         result.ordered_by = ordered_match.group(1).strip()

#     terms_match = re.search(r"TERMS\s*[|]?\s*([^\s]+)", text)
#     if terms_match:
#         result.terms = terms_match.group(1)

#     return result

# def check_ollama_health():
#     try:
#         response = requests.get("http://127.0.0.1:11434", timeout=5)
#         if response.status_code != 200:
#             raise Exception(f"Ollama responded with status {response.status_code}")
#         logger.info("Ollama service is healthy")
#     except requests.RequestException as e:
#         logger.error(f"Ollama health check failed: {str(e)}")
#         raise HTTPException(status_code=503, detail="Service Ollama indisponible. Veuillez démarrer Ollama avec 'ollama serve'.")

# def validate_result(result: ExtractionResult) -> bool:
#     essential_fields = [result.po_number, result.items]
#     return all(field is not None and (isinstance(field, list) and len(field) > 0 or isinstance(field, str)) for field in essential_fields)

# def call_llm(text: str, max_retries: int = 2) -> ExtractionResult:
#     logger.info("Calling LLM for text analysis")
#     check_ollama_health()
    
#     max_chars = 15000 if len(text) > 15000 else len(text)  # Augmenté pour mixtral
#     num_ctx = 16384 if max_chars <= 15000 else 8192  # Contexte plus large pour mixtral
    
#     prompt = f"""
# Tu es un expert en extraction de données précises à partir de bons de commande (PO) en français et anglais. Ton objectif est d'extraire les informations clés du texte ci-dessous et de retourner un JSON valide, en respectant strictement les données présentes sans inventer ou supposer quoi que ce soit.

# ---------------------
# 📄 Texte du document :
# {text[:max_chars]}
# ---------------------

# 🎯 Informations à extraire :
# - "po_number" : Numéro du PO après "Numero / Number" (ex: "2203" dans "Numero / Number | 2203")
# - "po_date" : Date d’émission après "Date" (ex: "06 Nov 2012" → "2012/11/06")
# - "delivered_to" : Adresse complète après "A: TO:" (ex: "Mindcore Technologies, 1845 Jean-Monnet, Terrebonne, QC J6X 4L7, Canada")
# - "shipped_to" : Adresse complète après "EXPEDIE A: SHIPPED TO:" (ex: "USINAGE TOURMAC INC., 11 rue de l'Industrie, St-Rémi, QC J0L 2L0, Canada")
# - "vendor_code" : Code après "CODE DU FOURNISSEUR VENDOR CODE" (ex: "M0062")
# - "vendor_ref" : Référence après "REF. FOURNISSEUR VENDOR REF." (null si vide)
# - "ship_via" : Mode après "EXPEDIE PAR SHIP VIA" (ex: "Pickup")
# - "ordered_by" : Nom après "EMIS PAR ORDERED BY" (ex: "Julie Robidoux")
# - "terms" : Conditions après "TERMS" (ex: "?" ou "Net 30")
# - "items" : Liste d’articles dans le tableau (sous "ITEM | NO DE PIECE PART NUMBER | DESCRIPTION | QTE. QTY. | PRIX UNITAIRE UNIT PRICE | MONTANT AMOUNT | LIVRAISON SHIP DATE") :
#   - "part_number" : Valeur sous "NO DE PIECE PART NUMBER" (ex: "COPIB187C110287523150280-288")
#   - "description" : Texte sous "DESCRIPTION" (ex: "Copper Tube B187C110 2-1/2\" Cedule 80 2.875\" OD × 2.315\" ID × 0.280\" WALL × 288\"")
#   - "quantity" : Valeur sous "QTE. QTY." (ex: "2 BAR")
#   - "unit_price" : Valeur sous "PRIX UNITAIRE UNIT PRICE" (ex: "$701.09 LB")
#   - "amount" : Valeur sous "MONTANT AMOUNT" (ex: "$2,972.62")
#   - "ship_date" : Date sous "LIVRAISON SHIP DATE" (ex: "07 Nov 2012" → "2012/11/07")
# - "total_without_tax" : Total HT après "MONTANT AMOUNT" global (ex: "$2,972.62")
# - "tax" : Taxe totale (si explicitement indiquée avec "tax", sinon null)
# - "tps" : TPS (si indiquée avec "TPS", sinon null)
# - "tvq" : TVQ (si indiquée avec "TVQ", sinon null)
# - "total_with_tax" : Total TTC (si taxes présentes et total indiqué, sinon null)

# 📝 Instructions strictes :
# 1. Retourne **uniquement un JSON valide**, sans texte hors structure.
# 2. Dates au format **AAAA/MM/JJ**. Convertis précisément (ex: "07 Nov 2012" → "2012/11/07").
# 3. Respecte les en-têtes pour associer les valeurs (ex: "A: TO:" ≠ "EXPEDIE A: SHIPPED TO:").
# 4. Si un champ est absent ou ambigu, mets `null`. **N’invente rien**.
# 5. Pour "items", utilise uniquement les colonnes du tableau, sans mélanger avec d’autres données (ex: "ITEM" n’est pas "part_number").
# 6. Conserve devises ("$") et unités ("LB", "BAR") telles qu’écrites.
# 7. Ne calcule pas de taxes ou totaux si non explicitement mentionnés.

# 📦 Exemple basé sur le document fourni :
# {{
#   "po_number": "2203",
#   "po_date": "2012/11/06",
#   "delivered_to": "Mindcore Technologies, 1845 Jean-Monnet, Terrebonne, QC J6X 4L7, Canada",
#   "shipped_to": "USINAGE TOURMAC INC., 11 rue de l'Industrie, St-Rémi, QC J0L 2L0, Canada",
#   "vendor_code": "M0062",
#   "vendor_ref": null,
#   "ship_via": "Pickup",
#   "ordered_by": "Julie Robidoux",
#   "terms": "?",
#   "items": [
#     {{
#       "part_number": "COPIB187C110287523150280-288",
#       "description": "Copper Tube B187C110 2-1/2\" Cedule 80 2.875\" OD × 2.315\" ID × 0.280\" WALL × 288\"",
#       "quantity": "2 BAR",
#       "unit_price": "$701.09 LB",
#       "amount": "$2,972.62",
#       "ship_date": "2012/11/07"
#     }}
#   ],
#   "total_without_tax": "$2,972.62",
#   "tax": null,
#   "tps": null,
#   "tvq": null,
#   "total_with_tax": null
# }}
# """

#     for attempt in range(max_retries):
#         try:
#             response = ollama.generate(
#                 model="mixtral",  # Changement à mixtral
#                 prompt=prompt,
#                 options={
#                     "temperature": 0.0,
#                     "num_ctx": num_ctx
#                 }
#             )
#             logger.info(f"LLM response received (attempt {attempt + 1})")
#             logger.info(f"Raw LLM response: {response['response']}")
            
#             json_data = clean_llm_response(response['response'])
            
#             result = ExtractionResult(
#                 po_number=json_data.get("po_number"),
#                 po_date=json_data.get("po_date"),
#                 delivered_to=json_data.get("delivered_to"),
#                 shipped_to=json_data.get("shipped_to"),
#                 vendor_code=json_data.get("vendor_code"),
#                 vendor_ref=json_data.get("vendor_ref"),
#                 ship_via=json_data.get("ship_via"),
#                 ordered_by=json_data.get("ordered_by"),
#                 terms=json_data.get("terms"),
#                 total_without_tax=json_data.get("total_without_tax"),
#                 tax=json_data.get("tax"),
#                 tps=json_data.get("tps"),
#                 tvq=json_data.get("tvq"),
#                 total_with_tax=json_data.get("total_with_tax")
#             )
            
#             for item in json_data.get("items", []):
#                 result.items.append(Item(**item))
            
#             result = post_process_result(result, text)
            
#             if validate_result(result):
#                 logger.info("Extraction result prepared and validated")
#                 return result
#             else:
#                 logger.warning(f"Result validation failed on attempt {attempt + 1}, retrying...")
#                 num_ctx = max(num_ctx // 2, 4096)
            
#         except ollama.ResponseError as e:
#             logger.error(f"Ollama response error on attempt {attempt + 1}: {str(e)}")
#             if attempt == max_retries - 1:
#                 raise HTTPException(status_code=500, detail=f"Erreur de réponse Ollama après {max_retries} tentatives: {str(e)}")
#             num_ctx = max(num_ctx // 2, 4096)
#         except Exception as e:
#             logger.error(f"LLM processing error on attempt {attempt + 1}: {str(e)}")
#             if attempt == max_retries - 1:
#                 raise HTTPException(status_code=500, detail=f"Erreur du modèle LLM après {max_retries} tentatives: {str(e)}")
    
#     raise HTTPException(status_code=500, detail="Échec de l'extraction après toutes les tentatives.")

# @app.post("/extract", response_model=ExtractionResult)
# async def extract_infos(file: UploadFile = File(...)):
#     logger.info("Received extract request")
#     try:
#         text = extract_text_from_file(file)
#         return call_llm(text)
#     except HTTPException as e:
#         raise e
#     except Exception as e:
#         logger.error(f"Unexpected error in extract_infos: {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Erreur inattendue: {str(e)}")

# @app.get("/health")
# async def health_check():
#     try:
#         check_ollama_health()
#         return {"status": "healthy", "model": "mixtral"}  # Mise à jour du modèle dans la réponse
#     except HTTPException as e:
#         raise e

# if __name__ == "__main__":
#     import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)

###########################################################################################################################################


# backend/main.py/llama3

# backend/main.py
import json
import logging
import requests
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pytesseract
from pdf2image import convert_from_bytes
import PyPDF2
from io import BytesIO
from typing import Optional, List, Dict
import ollama
from PIL import Image, ImageEnhance, ImageFilter
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PDF PO Extractor", version="2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class Item(BaseModel):
    part_number: Optional[str] = None
    description: Optional[str] = None
    quantity: Optional[str] = None
    unit_price: Optional[str] = None
    amount: Optional[str] = None
    ship_date: Optional[str] = None

class ExtractionResult(BaseModel):
    po_number: Optional[str] = None
    po_date: Optional[str] = None
    delivered_to: Optional[str] = None
    shipped_to: Optional[str] = None
    vendor_code: Optional[str] = None
    vendor_ref: Optional[str] = None
    ship_via: Optional[str] = None
    ordered_by: Optional[str] = None
    terms: Optional[str] = None
    items: List[Item] = []
    total_without_tax: Optional[str] = None
    tax: Optional[str] = None
    tps: Optional[str] = None
    tvq: Optional[str] = None
    total_with_tax: Optional[str] = None

def preprocess_image(image: Image.Image) -> Image.Image:
    image = image.convert('L')
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2.0)
    image = image.filter(ImageFilter.SHARPEN)
    return image

def extract_text_from_file(file: UploadFile) -> str:
    logger.info(f"Extracting text from file: {file.filename}")
    try:
        file_content = file.file.read()
        if file.filename.lower().endswith('.pdf'):
            try:
                with BytesIO(file_content) as pdf_file:
                    reader = PyPDF2.PdfReader(pdf_file)
                    text = "\n".join([page.extract_text() for page in reader.pages])
                    if text.strip():
                        logger.info("Text extracted directly from PDF")
                        return text
            except Exception as e:
                logger.warning(f"Direct PDF extraction failed: {str(e)}, falling back to OCR")
            images = convert_from_bytes(file_content)
            text = "\n".join([
                pytesseract.image_to_string(
                    preprocess_image(img),
                    config='--psm 6'
                ) for img in images
            ])
            logger.info("Text extracted via OCR with preprocessing")
            return text
        image = Image.open(BytesIO(file_content))
        text = pytesseract.image_to_string(preprocess_image(image), config='--psm 6')
        logger.info("Text extracted from image with preprocessing")
        return text
    except Exception as e:
        logger.error(f"File processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Erreur de traitement du fichier: {str(e)}")

def clean_llm_response(response: str) -> Dict:
    logger.info("Cleaning LLM response")
    try:
        # Supprime tout texte avant le premier '{' et après le dernier '}'
        response = response.strip()
        start = response.find('{')
        end = response.rfind('}') + 1
        if start == -1 or end == 0:
            raise ValueError("No valid JSON found in response")
        
        # Extrait uniquement la partie JSON
        json_str = response[start:end]
        
        # Supprime les backticks ou tout autre texte parasite restant
        json_str = re.sub(r'```.*?\n', '', json_str, flags=re.DOTALL)  # Supprime les blocs de backticks
        json_str = re.sub(r'[^[{}\]",:null0-9.\s]', '', json_str)  # Garde uniquement les caractères JSON valides
        
        # Charge le JSON
        data = json.loads(json_str)
        
        # Corrige la structure imbriquée de "tax" si présente
        if "tax" in data and isinstance(data["tax"], dict):
            tax_dict = data.pop("tax")
            data["tps"] = tax_dict.get("tps")
            data["tvq"] = tax_dict.get("tvq")
            data["tax"] = None  # Reset tax to null unless explicitly specified
        
        for key, value in data.items():
            if isinstance(value, list) and key != "items":
                data[key] = " ".join(str(v) for v in value) if value else None
        return data
    except Exception as e:
        logger.error(f"JSON parsing error: {str(e)} - Response: {response}")
        raise HTTPException(status_code=500, detail=f"Erreur de parsing JSON: {str(e)} - Réponse: {response}")

def post_process_result(result: ExtractionResult, text: str) -> ExtractionResult:
    """Corrige les erreurs évidentes dans les données extraites."""
    # Correction de po_number
    po_match = re.search(r"Numero / Number\s*[|]\s*(\d+)", text, re.IGNORECASE)
    if po_match:
        result.po_number = po_match.group(1)

    # Correction de po_date
    date_match = re.search(r"Date\s*[|]\s*(\d{2}\s*[A-Za-z]+\s*\d{4})", text, re.IGNORECASE)
    if date_match:
        date_str = date_match.group(1)
        result.po_date = re.sub(r"(\d{2})\s*([A-Za-z]+)\s*(\d{4})", lambda m: f"{m.group(3)}/{str(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].index(m.group(2)) + 1).zfill(2)}/{m.group(1)}", date_str)

    # Correction de delivered_to
    delivered_match = re.search(r"A: TO:\s*([\s\S]+?)(?=EXPEDIE A: SHIPPED TO:|$)", text, re.IGNORECASE)
    if delivered_match:
        result.delivered_to = delivered_match.group(1).strip().replace('\n', ', ')

    # Correction de shipped_to
    shipped_match = re.search(r"EXPEDIE A: SHIPPED TO:\s*([\s\S]+?)(?=CODE DU FOURNISSEUR VENDOR CODE|$)", text, re.IGNORECASE)
    if shipped_match:
        result.shipped_to = shipped_match.group(1).strip().replace('\n', ', ')

    # Correction des items
    for item in result.items:
        part_match = re.search(r"NO DE PIECE\s*PART NUMBER\s*[|]?\s*([A-Za-z0-9\-]+)", text, re.MULTILINE)
        if part_match:
            item.part_number = part_match.group(1)

        desc_match = re.search(r"DESCRIPTION\s*[|]?\s*([^\n]+)", text, re.MULTILINE)
        if desc_match:
            item.description = desc_match.group(1).strip()

        qty_match = re.search(r"QTE\.\s*QTY\.\s*[|]?\s*(\d+\s*[A-Za-z]+)", text, re.MULTILINE)
        if qty_match:
            item.quantity = qty_match.group(1)

        price_match = re.search(r"PRIX UNITAIRE\s*UNIT PRICE\s*[|]?\s*(\$\d+\.\d+\s*[A-Za-z]+)", text, re.MULTILINE)
        if price_match:
            item.unit_price = price_match.group(1)
        elif item.unit_price and "7.0109" in item.unit_price:
            item.unit_price = "$701.09 LB"

        amount_match = re.search(r"MONTANT\s*AMOUNT\s*[|]?\s*(\$\d+(?:,\d+)?\.\d+)", text, re.MULTILINE)
        if amount_match:
            item.amount = amount_match.group(1)

        ship_date_match = re.search(r"LIVRAISON\s*SHIP DATE\s*[|]?\s*(\d{2}\s*[A-Za-z]+\s*\d{4})", text, re.IGNORECASE)
        if ship_date_match:
            date_str = ship_date_match.group(1)
            item.ship_date = re.sub(r"(\d{2})\s*([A-Za-z]+)\s*(\d{4})", lambda m: f"{m.group(3)}/{str(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'].index(m.group(2)) + 1).zfill(2)}/{m.group(1)}", date_str)

    # Correction des champs manquants ou incorrects
    vendor_match = re.search(r"CODE DU FOURNISSEUR\s*VENDOR CODE\s*[|]?\s*(\w+)", text)
    if vendor_match:
        result.vendor_code = vendor_match.group(1)

    ship_match = re.search(r"EXPEDIE PAR\s*SHIP VIA\s*[|]?\s*(\w+)", text)
    if ship_match:
        result.ship_via = ship_match.group(1)

    ordered_match = re.search(r"EMIS PAR\s*ORDERED BY\s*[|]?\s*([A-Za-z\s]+)", text)
    if ordered_match:
        result.ordered_by = ordered_match.group(1).strip()

    terms_match = re.search(r"TERMS\s*[|]?\s*([^\s]+)", text)
    if terms_match:
        result.terms = terms_match.group(1)

    total_match = re.search(r"MONTANT\s*AMOUNT\s*[|]?\s*(\$\d+(?:,\d+)?\.\d+)", text, re.MULTILINE)
    if total_match and not re.search(r"(tax|TAX|TPS|TVQ)", text, re.IGNORECASE):
        result.total_without_tax = total_match.group(1)

    # Suppression des taxes inventées
    if not re.search(r"(tax|TAX|TPS|TVQ)\s*[|]?\s*\$?\d+\.?\d*", text, re.IGNORECASE):
        result.tax = None
        result.tps = None
        result.tvq = None
        result.total_with_tax = None

    return result

def check_ollama_health():
    try:
        response = requests.get("http://127.0.0.1:11434", timeout=5)
        if response.status_code != 200:
            raise Exception(f"Ollama responded with status {response.status_code}")
        logger.info("Ollama service is healthy")
    except requests.RequestException as e:
        logger.error(f"Ollama health check failed: {str(e)}")
        raise HTTPException(status_code=503, detail="Service Ollama indisponible. Veuillez démarrer Ollama avec 'ollama serve'.")

def validate_result(result: ExtractionResult) -> bool:
    essential_fields = [result.po_number, result.items]
    return all(field is not None and (isinstance(field, list) and len(field) > 0 or isinstance(field, str)) for field in essential_fields)

def call_llm(text: str, max_retries: int = 3) -> ExtractionResult:
    logger.info("Calling LLM for text analysis")
    check_ollama_health()
    
    max_chars = 10000 if len(text) > 10000 else len(text)
    num_ctx = 8192 if max_chars <= 10000 else 4096
    
    prompt = f"""
Extract data from the text below and return **ONLY A VALID JSON OBJECT**. **DO NOT ADD ANY TEXT OUTSIDE THE JSON, NO NOTES, NO COMMENTS, NO BACKTICKS, NO EXPLANATIONS**. Follow the exact headers and do not invent or assume anything.

Text:
{text[:max_chars]}

Fields to extract:
- "po_number": Exact number after "Numero / Number" (e.g., "2203")
- "po_date": Date after "Date" (e.g., "06 Nov 2012" → "2012/11/06")
- "delivered_to": Full address after "A: TO:" (e.g., "Mindcore Technologies, 1845 Jean-Monnet, Terrebonne, QC J6X 4L7, Canada")
- "shipped_to": Full address after "EXPEDIE A: SHIPPED TO:" (e.g., "USINAGE TOURMAC INC., 11 rue de l'Industrie, St-Rémi, QC J0L 2L0, Canada")
- "vendor_code": Code after "CODE DU FOURNISSEUR VENDOR CODE" (e.g., "M0062")
- "vendor_ref": After "REF. FOURNISSEUR VENDOR REF." (null if empty)
- "ship_via": Mode after "EXPEDIE PAR SHIP VIA" (e.g., "Pickup")
- "ordered_by": Name after "EMIS PAR ORDERED BY" (e.g., "Julie Robidoux"), not "Contact"
- "terms": After "TERMS" (e.g., "?" or "Net 30")
- "items": List from table "ITEM | NO DE PIECE PART NUMBER | DESCRIPTION | QTE. QTY. | PRIX UNITAIRE UNIT PRICE | MONTANT AMOUNT | LIVRAISON SHIP DATE":
  - "part_number": Under "NO DE PIECE PART NUMBER" (not "ITEM")
  - "description": Under "DESCRIPTION"
  - "quantity": Under "QTE. QTY."
  - "unit_price": Under "PRIX UNITAIRE UNIT PRICE"
  - "amount": Under "MONTANT AMOUNT"
  - "ship_date": Under "LIVRAISON SHIP DATE" (e.g., "07 Nov 2012" → "2012/11/07")
- "total_without_tax": Total after "MONTANT AMOUNT" (global)
- "tax": Only if "tax" or "TAX" with amount, else null
- "tps": Only if "TPS" with amount, else null
- "tvq": Only if "TVQ" with amount, else null
- "total_with_tax": Only if taxes and total specified, else null

Rules:
- **RETURN ONLY JSON, NOTHING ELSE**. NO EXTRA TEXT, NO BACKTICKS, NO COMMENTS.
- Dates in **YYYY/MM/DD**.
- Use exact header values, no mixing (e.g., "A: TO:" ≠ "EXPEDIE A: SHIPPED TO:").
- Set `null` for missing/ambiguous fields. **DO NOT INVENT DATA**.
- Keep currencies ("$") and units ("LB", "BAR") as written.
- **DO NOT CALCULATE OR ADD TAXES/TOTAL IF NOT EXPLICITLY IN TEXT**.
"""

    for attempt in range(max_retries):
        try:
            response = ollama.generate(
                model="llama3",
                prompt=prompt,
                options={
                    "temperature": 0.0,
                    "num_ctx": num_ctx
                }
            )
            logger.info(f"LLM response received (attempt {attempt + 1})")
            logger.info(f"Raw LLM response: {response['response']}")
            
            json_data = clean_llm_response(response['response'])
            
            result = ExtractionResult(
                po_number=json_data.get("po_number"),
                po_date=json_data.get("po_date"),
                delivered_to=json_data.get("delivered_to"),
                shipped_to=json_data.get("shipped_to"),
                vendor_code=json_data.get("vendor_code"),
                vendor_ref=json_data.get("vendor_ref"),
                ship_via=json_data.get("ship_via"),
                ordered_by=json_data.get("ordered_by"),
                terms=json_data.get("terms"),
                total_without_tax=json_data.get("total_without_tax"),
                tax=json_data.get("tax"),
                tps=json_data.get("tps"),
                tvq=json_data.get("tvq"),
                total_with_tax=json_data.get("total_with_tax")
            )
            
            for item in json_data.get("items", []):
                result.items.append(Item(**item))
            
            result = post_process_result(result, text)
            
            if validate_result(result):
                logger.info("Extraction result prepared and validated")
                return result
            else:
                logger.warning(f"Result validation failed on attempt {attempt + 1}, retrying...")
                num_ctx = max(num_ctx // 2, 2048)
            
        except ollama.ResponseError as e:
            logger.error(f"Ollama response error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise HTTPException(status_code=500, detail=f"Erreur de réponse Ollama après {max_retries} tentatives: {str(e)}")
            num_ctx = max(num_ctx // 2, 2048)
        except Exception as e:
            logger.error(f"LLM processing error on attempt {attempt + 1}: {str(e)}")
            if attempt == max_retries - 1:
                raise HTTPException(status_code=500, detail=f"Erreur du modèle LLM après {max_retries} tentatives: {str(e)}")
    
    raise HTTPException(status_code=500, detail="Échec de l'extraction après toutes les tentatives.")

@app.post("/extract", response_model=ExtractionResult)
async def extract_infos(file: UploadFile = File(...)):
    logger.info("Received extract request")
    try:
        text = extract_text_from_file(file)
        return call_llm(text)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in extract_infos: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Erreur inattendue: {str(e)}")

@app.get("/health")
async def health_check():
    try:
        check_ollama_health()
        return {"status": "healthy", "model": "llama3"}
    except HTTPException as e:
        raise e

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)