import streamlit as st
import base64
import json
import os
import httpx
import traceback
from typing import List, Dict, Any, Union, Optional, Literal
from openai import OpenAI
from typing_extensions import Annotated
from pydantic import BaseModel, Field, validator

# --- Constants ---
MVRNOW_BASE_URL = "https://mvrnow.com/usd/"
MVRNOW_ORDER_ENDPOINT = f"{MVRNOW_BASE_URL}Mvr/OrderMvrRecord"
DPPA_CODE = "06"

# --- Language Dictionary (LANG) ---
LANG = {
    "English": {
        "pull_mvr_button": "Pull MVR Record(s)", "mvr_section_title": "Motor Vehicle Record (MVR) Results",
        "mvr_pull_success": "✅ MVR Record pulled successfully for License: {license_number}",
        "mvr_pull_error": "❌ Error pulling MVR for License: {license_number} - {error_message}",
        "mvr_pull_inprogress": "Pulling MVR for License: {license_number}...", "mvr_api_key_missing": "MVRNow API Key not configured. Please set MVRNOW_API_KEY in secrets.",
        "mvr_view_raw": "View Raw MVR Data (JSON)", "mvr_tab_driver": "Driver Info", "mvr_tab_license": "License Details",
        "mvr_tab_events": "Events", "mvr_tab_messages": "Messages", "mvr_field_name": "Name", "mvr_field_dob": "Date of Birth",
        "mvr_field_age": "Age", "mvr_field_gender": "Gender", "mvr_field_address": "Address", "mvr_field_eyes": "Eye Color",
        "mvr_field_height": "Height", "mvr_field_lic_num": "License Number", "mvr_field_class": "Class", "mvr_field_class_desc": "Class Description",
        "mvr_field_issued": "Issued", "mvr_field_expires": "Expires", "mvr_field_status": "Status", "mvr_field_prob_expires": "Probation Expires",
        "mvr_event_subtype": "Type", "mvr_event_date": "Date", "mvr_event_location": "Location", "mvr_event_description": "Description",
        "mvr_event_state_desc": "State Description", "mvr_event_points": "Points", "mvr_event_conviction": "Conviction Date", "mvr_event_fine": "Fine",
        "mvr_event_action_clear": "Clear Date", "mvr_event_action_reason": "Clear Reason", "mvr_no_events": "No events found.", "mvr_no_messages": "No messages found.",
        "app_title": "TLC Insurance Application", "app_description": ("This application allows you to upload multiple documents at once:\n- **NYS Driver License**\n- **TLC Hack License**\n- **Vehicle Certificate of Title or Bill of Sale**\n- **Radio Base Certification Letter**\n\nAll documents are processed together by GPT‑4o to extract structured data. Once processed, you can review and edit the extracted data before submitting your application."),
        "additional_info_title": "Additional Information", "owned_by_self_question": "Is this vehicle owned and operated ONLY by yourself or spouse?", "named_drivers_question": "Is this vehicle operated by approved Named Drivers?",
        "other_driver_upload_label": "Upload Other Driver's License", "yes_options": ["Yes", "No"], "contact_label": "Contact Information", "contact_email_label": "Email Address",
        "contact_phone_label": "Phone Number", "process_button": "Process All Documents", "submit_button": "Submit Application", "view_raw": "View Raw Extracted Data (JSON)",
        "processing_spinner": "Processing all documents...", "processing_success": "✅ Documents processed successfully!", "processing_failed": "Processing failed. See error above.",
        "review_title": "📝 Review and Edit Extracted Information", "submit_success": "✅ Application submitted successfully!", "upload_label": "Upload all documents",
        "other_driver_file_label": "Other driver file: {filename}",
        "system_message": ("""You are a document processing assistant that extracts structured information from multiple documents. For each document, you need to identify the document type based on its VISUAL CONTENT (not the filename), and return a JSON object with exactly three keys: "type", "filename", and "data".

Extract the following based on the document type:

- For "NYS Driver License": extract "license_number", "first_name", "middle_name" (if present), "last_name", "address", "city", "state", and "zip_code". This is a photo ID with New York State license information.

- For "TLC Hack License": extract "license_number", "first_name", and "last_name". This is a Taxi & Limousine Commission license for drivers, usually with TLC branding.

- For "Vehicle Certificate of Title" or "Bill of Sale": extract "VIN", "vehicle_make", "vehicle_model", "vehicle_year", and "owner_name". The title has official state header and ownership details.

- For "Radio Base Certification Letter": extract "radio_base_name". This is a business letter with letterhead confirming the driver's affiliation with a radio dispatch base. It may have official company logo, signature, and confirmation language.

- For "Other Driver's License" (if exist): extract "license_number", "first_name", "middle_name" (if present), "last_name", "address", "city", "state", and "zip_code".

PAY SPECIAL ATTENTION to identifying Radio Base Certification Letters correctly - these are formal business letters confirming the driver works with a dispatch service.

Return a single combined JSON object with a "documents" array containing these document objects. Ensure the field names are consistent and, for address, return individual fields rather than a combined string. DO NOT include document types that are not present in the images.""")
    },
    "Español": { # Add Spanish translations similarly...
        "pull_mvr_button": "Obtener Registro(s) MVR", "mvr_section_title": "Resultados del Registro de Vehículos Motorizados (MVR)", "mvr_pull_success": "✅ Registro MVR obtenido con éxito para Licencia: {license_number}", "mvr_pull_error": "❌ Error al obtener MVR para Licencia: {license_number} - {error_message}", "mvr_pull_inprogress": "Obteniendo MVR para Licencia: {license_number}...", "mvr_api_key_missing": "Clave API de MVRNow no configurada. Configure MVRNOW_API_KEY en los secretos.", "mvr_view_raw": "Ver Datos MVR Crudos (JSON)", "mvr_tab_driver": "Info. Conductor", "mvr_tab_license": "Detalles Licencia", "mvr_tab_events": "Eventos", "mvr_tab_messages": "Mensajes", "mvr_field_name": "Nombre", "mvr_field_dob": "Fecha de Nacimiento", "mvr_field_age": "Edad", "mvr_field_gender": "Género", "mvr_field_address": "Dirección", "mvr_field_eyes": "Color de Ojos", "mvr_field_height": "Altura", "mvr_field_lic_num": "Número de Licencia", "mvr_field_class": "Clase", "mvr_field_class_desc": "Descripción de Clase", "mvr_field_issued": "Emitida", "mvr_field_expires": "Expira", "mvr_field_status": "Estado", "mvr_field_prob_expires": "Expira Probatoria", "mvr_event_subtype": "Tipo", "mvr_event_date": "Fecha", "mvr_event_location": "Lugar", "mvr_event_description": "Descripción", "mvr_event_state_desc": "Descripción Estatal", "mvr_event_points": "Puntos", "mvr_event_conviction": "Fecha Condena", "mvr_event_fine": "Multa", "mvr_event_action_clear": "Fecha Liquidación", "mvr_event_action_reason": "Razón Liquidación", "mvr_no_events": "No se encontraron eventos.", "mvr_no_messages": "No se encontraron mensajes.", "app_title": "Solicitud de Seguro TLC", "app_description": ("Esta solicitud te permite subir varios documentos a la vez:\n- **Licencia de Conducir del Estado de Nueva York (NYS)**\n- **Licencia de Conductor TLC**\n- **Certificado de Título del Vehículo o Factura de Venta**\n- **Carta de Certificación de la Base de Radio**\n\nTodos los documentos se procesan juntos mediante GPT‑4o para extraer datos estructurados. Una vez procesados, podrás revisar y editar los datos extraídos antes de enviar tu solicitud."), "additional_info_title": "Información Adicional", "owned_by_self_question": "¿Este vehículo es propiedad tuya y SOLO lo conduces tú o tu cónyuge?", "named_drivers_question": "¿Este vehículo es conducido por conductores nombrados aprobados?", "other_driver_upload_label": "Sube la Licencia de Conducir del Otro Conductor", "yes_options": ["Sí", "No"], "contact_label": "Información de Contacto", "contact_email_label": "Correo Electrónico", "contact_phone_label": "Número de Teléfono", "process_button": "Procesar Todos los Documentos", "submit_button": "Enviar Solicitud", "view_raw": "Ver Datos Extraídos (JSON)", "processing_spinner": "Procesando todos los documentos...", "processing_success": "✅ Documentos procesados exitosamente!", "processing_failed": "El procesamiento falló. Ver error arriba.", "review_title": "📝 Revisar y Editar la Información Extraída", "submit_success": "✅ Solicitud enviada exitosamente!", "upload_label": "Sube todos los documentos", "other_driver_file_label": "Archivo del otro conductor: {filename}", "system_message": ("""Eres un asistente de procesamiento de documentos que extrae información estructurada de múltiples documentos. Para cada documento, necesitas identificar el tipo de documento basado en su CONTENIDO VISUAL (no el nombre del archivo), y devolver un objeto JSON con exactamente tres claves: "type", "filename", y "data".

Extrae lo siguiente según el tipo de documento:

- Para "Licencia de Conducir del Estado de Nueva York": extrae "license_number", "first_name", "middle_name" (si existe), "last_name", "address", "city", "state", y "zip_code". Esta es una identificación con foto con información de licencia del Estado de Nueva York.

- Para "Licencia de Conductor TLC": extrae "license_number", "first_name", y "last_name". Esta es una licencia de la Comisión de Taxis y Limusinas para conductores, generalmente con la marca TLC.

- Para "Certificado de Título del Vehículo" o "Factura de Venta": extrae "VIN", "vehicle_make", "vehicle_model", "vehicle_year", y "owner_name". El título tiene un encabezado oficial del estado y detalles de propiedad.

- Para "Carta de Certificación de la Base de Radio": extrae "radio_base_name". Esta es una carta comercial con membrete que confirma la afiliación del conductor con una base de despacho de radio. Puede tener un logotipo oficial de la empresa, firma e idioma de confirmación.

- Para "Licencia de Conducir del Otro Conductor" (si existe): extrae "license_number", "first_name", "middle_name" (si existe), "last_name", "address", "city", "state", y "zip_code".

PRESTA ESPECIAL ATENCIÓN a identificar correctamente las Cartas de Certificación de Base de Radio - estas son cartas comerciales formales que confirman que el conductor trabaja con un servicio de despacho.

Devuelve un único objeto JSON combinado con una matriz "documents" que contenga estos objetos de documento. Asegúrate de que los nombres de los campos sean consistentes y, para la dirección, devuelve campos individuales en lugar de una cadena combinada. NO incluyas tipos de documentos que no estén presentes en las imágenes.""")
    }
}

# --- Pydantic Models ---
class DocumentData(BaseModel):
    license_number: Optional[str] = None; first_name: Optional[str] = None; middle_name: Optional[str] = None; last_name: Optional[str] = None
    address: Optional[str] = None; city: Optional[str] = None; state: Optional[str] = None; zip_code: Optional[str] = None
    VIN: Optional[str] = None; vehicle_make: Optional[str] = None; vehicle_model: Optional[str] = None; vehicle_year: Optional[str] = None
    owner_name: Optional[str] = None; radio_base_name: Optional[str] = None
class DocumentBase(BaseModel): filename: str
class NYSDriverLicense(DocumentBase): type: Literal["NYS Driver License"]; data: DocumentData
class TLCHackLicense(DocumentBase): type: Literal["TLC Hack License"]; data: DocumentData
class VehicleCertificateOfTitle(DocumentBase): type: Literal["Vehicle Certificate of Title"]; data: DocumentData
class BillOfSale(DocumentBase): type: Literal["Bill of Sale"]; data: DocumentData
class RadioBaseCert(DocumentBase): type: Literal["Radio Base Certification Letter"]; data: DocumentData
class OtherDriverLicense(DocumentBase):
    type: Literal["Other Driver's License"]; data: DocumentData
    @validator('type', pre=True, always=True, allow_reuse=True)
    def normalize_type(cls, v):
        if v in ["Other", "Other Driver's License"]: return "Other Driver's License"
        raise ValueError(f"Invalid type for OtherDriverLicense: {v}")
DocumentUnion = Annotated[Union[NYSDriverLicense, TLCHackLicense, VehicleCertificateOfTitle, BillOfSale, RadioBaseCert, OtherDriverLicense], Field(discriminator="type")]
class ExtractionResult(BaseModel): documents: List[DocumentUnion]

# --- API and Client Setup ---
# @st.cache_resource
def get_openai_client():
    try:
        openai_api_key = os.environ.get("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY")
        if not openai_api_key: st.error("OpenAI API Key not found."); st.stop()
        return OpenAI(api_key=openai_api_key, http_client=httpx.Client(base_url="https://api.openai.com/v1", follow_redirects=True, timeout=60.0))
    except Exception as e: st.error(f"Error initializing OpenAI client: {e}"); st.stop()
client = get_openai_client()
mvrnow_api_key = os.environ.get("MVRNOW_API_KEY") or st.secrets.get("MVRNOW_API_KEY")

# --- Language Setup ---
if 'lang' not in st.session_state: st.session_state.lang = list(LANG.keys())[0]
def update_lang(): st.session_state.lang = st.session_state.lang_select
st.sidebar.selectbox("Select Language / Seleccionar Idioma", list(LANG.keys()), key="lang_select", on_change=update_lang)
L = LANG[st.session_state.lang]

# --- Helper Functions ---
def normalize_raw_documents(raw: dict) -> dict:
    for doc in raw.get("documents", []):
        if doc.get("type") == "Other": doc["type"] = "Other Driver's License"
    return raw

expected_fields = {
    "NYS Driver License": ["license_number", "first_name", "middle_name", "last_name", "address", "city", "state", "zip_code"],
    "TLC Hack License": ["license_number", "first_name", "last_name"], "Vehicle Certificate of Title": ["VIN", "vehicle_make", "vehicle_model", "vehicle_year", "owner_name"],
    "Bill of Sale": ["VIN", "vehicle_make", "vehicle_model", "vehicle_year", "owner_name"], "Radio Base Certification Letter": ["radio_base_name"],
    "Other Driver's License": ["license_number", "first_name", "middle_name", "last_name", "address", "city", "state", "zip_code"]
}

def process_documents(sync_openai_client: OpenAI, files: List[Any], sys_message: str, owned_by_self: str = "No") -> ExtractionResult:
    try:
        messages = [{"role": "system", "content": sys_message}, {"role": "user", "content": []}]
        
        # Create a more detailed instruction for document analysis
        content = [{
            "type": "text", 
            "text": """Process these documents and identify each one correctly. The documents could include:
            
1. NYS Driver License - Contains driver's license number, name, address fields, photo ID
2. TLC Hack License - Special license for taxi/livery drivers, contains license number and name
3. Vehicle Certificate of Title - Contains VIN, vehicle make, model, year, and owner information
4. Bill of Sale - Document showing vehicle purchase details, contains similar info to title
5. Radio Base Certification Letter - A letter with letterhead confirming affiliation with a radio base/dispatch service

DO NOT include any document types that are not actually present in the images. For each document, return type, filename, and data fields as specified."""
        }]
        
        # Process each file without attempting to detect type from filename
        for file in files:
            b64 = base64.b64encode(file.getvalue()).decode("utf-8")
            content.extend([
                {"type": "text", "text": f"Filename: {file.name}"},
                {"type": "image_url", "image_url": {"url": f"data:{file.type};base64,{b64}", "detail": "high"}}
            ])
        
        # Add a reminder about correct document identification
        content.append({
            "type": "text", 
            "text": "Remember to accurately identify each document type based on its visual content, not its filename. Ensure you identify any Radio Base Certification Letter if present - this is an official letter showing affiliation with a radio dispatch base."
        })
        
        messages[1]["content"] = content
        response = sync_openai_client.chat.completions.create(
            model="gpt-4o-mini", 
            messages=messages, 
            response_format={"type": "json_object"}, 
            temperature=0.1
        )
        raw = json.loads(response.choices[0].message.content)
        
        # Post-process the results
        if "documents" in raw:
            # If user selected they're the only driver, filter out any "Other Driver's License"
            if owned_by_self == "Yes" and any(doc.get("type") == "Other Driver's License" for doc in raw.get("documents", [])):
                raw["documents"] = [doc for doc in raw.get("documents", []) if doc.get("type") != "Other Driver's License"]
            
            # Check for missing Radio Base Certification - debug info
            has_radio_base = any(doc.get("type") == "Radio Base Certification Letter" for doc in raw.get("documents", []))
            if not has_radio_base:
                print("Note: Radio Base Certification Letter not found in processed documents")
        
        return ExtractionResult.parse_obj(normalize_raw_documents(raw))
    except Exception as e: 
        st.error(f"OpenAI Error: {e}")
        st.code(traceback.format_exc())
        raise

def flatten_doc_by_expected(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc_type = doc.get("type", "Unknown")
    data = doc.get("data", {})
    fields = expected_fields.get(doc_type, list(data.keys()))
    return {f"{doc_type} - {f}": data.get(f, "") for f in fields if data and f in data}

def flatten_all_data(docs: List[Dict[str, Any]], contact: Dict[str, str]) -> Dict[str, Any]:
    flat = {f"{L['contact_label']} - {k}": v for k, v in contact.items()}
    for doc in docs: flat.update(flatten_doc_by_expected(doc))
    return flat

def pull_mvr_record(api_key: str, state: str, lic_num: str, fname: Optional[str], lname: Optional[str]) -> Dict[str, Any]:
    if not api_key: return {"Error": True, "Message": L["mvr_api_key_missing"]}
    ln_c = str(lic_num).strip(); state_c = str(state).strip().upper()
    if not state_c or not ln_c: return {"Error": True, "Message": "State/License required."}
    payload = {"ApiKey": api_key, "State": state_c, "LicenseNumber": ln_c, "DPPACode": DPPA_CODE,
               "FirstName": str(fname).strip(), "LastName": str(lname).strip(), "ReferenceId": f"nivlapp_{ln_c}"}
    payload = {k: v for k, v in payload.items() if v}
    try:
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(MVRNOW_ORDER_ENDPOINT, json=payload)
            resp.raise_for_status()
            return resp.json() | {"_query_license_number": lic_num}
    except httpx.HTTPStatusError as e: err_msg = f"API Error {e.response.status_code}: {e.response.text}"
    except httpx.RequestError as e: err_msg = f"Network Error: {e}"
    except Exception as e: err_msg = f"Unexpected Error: {e}"; print(traceback.format_exc())
    st.error(f"MVR API Error for {ln_c}: {err_msg}")
    return {"Error": True, "Message": err_msg, "_query_license_number": lic_num}

def format_date(d: Optional[Dict[str, Any]]) -> str:
    if not isinstance(d, dict): return "N/A"
    try: m, dy, y = str(d.get("Month","")).zfill(2), str(d.get("Day","")).zfill(2), str(d.get("Year",""))
    except: return "N/A"
    return f"{m}/{dy}/{y}" if m!="00" and dy!="00" and y else "N/A"

def format_address(addr: Optional[Dict[str, Any]]) -> str:
    if not isinstance(addr, dict): return "N/A"
    s_data = addr.get("State"); state = s_data.get("Abbrev","") if isinstance(s_data,dict) else str(s_data or "")
    parts = [str(addr.get(k,"") or "") for k in ["Street","City"]] + [state] + [str(addr.get("Zip","") or "")]
    return ", ".join(p for p in parts if p) or "N/A"

# --- MVR Display Helper Function ---
def _display_mvr_tabs(dl_record: Dict[str, Any], original_mvr_result: Dict[str, Any], L: Dict[str, str]):
    """Displays MVR data in tabs, using safe dictionary access."""
    tab_drv, tab_lic, tab_evt, tab_msg, tab_raw = st.tabs([
        L["mvr_tab_driver"], L["mvr_tab_license"], L["mvr_tab_events"],
        L["mvr_tab_messages"], L["mvr_view_raw"]
    ])

    with tab_drv:
        driver = dl_record.get("Driver", {})
        if driver:
            name = " ".join(filter(None, [driver.get(k) for k in ["FirstName","MiddleName","LastName"]]))
            st.write(f"**{L['mvr_field_name']}:** {name or 'N/A'}")
            st.write(f"**{L['mvr_field_dob']}:** {format_date(driver.get('BirthDate'))}")
            st.write(f"**{L['mvr_field_age']}:** {driver.get('Age', 'N/A')}")
            st.write(f"**{L['mvr_field_gender']}:** {driver.get('Gender', 'N/A')}")
            st.write(f"**{L['mvr_field_eyes']}:** {driver.get('EyeColor', 'N/A')}")
            st.write(f"**{L['mvr_field_height']}:** {driver.get('Height', 'N/A')}")
            addr_item = driver.get('AddressList', {}).get('AddressItem')
            addr = addr_item[0] if isinstance(addr_item, list) else addr_item
            st.write(f"**{L['mvr_field_address']}:** {format_address(addr)}")
        else: st.write("Driver information not available.")

    with tab_lic:
        lic = dl_record.get("CurrentLicense", {})
        if lic:
            st.write(f"**{L['mvr_field_lic_num']}:** {lic.get('Number', 'N/A')}")
            st.write(f"**{L['mvr_field_class']}:** {lic.get('ClassCode', 'N/A')}")
            st.write(f"**{L['mvr_field_class_desc']}:** {lic.get('ClassDescription', 'N/A')}")
            st.write(f"**{L['mvr_field_issued']}:** {format_date(lic.get('IssueDate'))}")
            st.write(f"**{L['mvr_field_expires']}:** {format_date(lic.get('ExpirationDate'))}")
            status_item = lic.get('PersonalStatusList', {}).get('StatusItem')
            status = [status_item] if isinstance(status_item, dict) else (status_item if isinstance(status_item, list) else [])
            st.write(f"**{L['mvr_field_status']}:** {', '.join(s.get('Name','') for s in status if s.get('Name')) or 'N/A'}")
            st.write(f"**{L['mvr_field_prob_expires']}:** {format_date(lic.get('ProbationExpireDate'))}")

            # --- Corrected Restriction Handling ---
            restriction_list_data = lic.get("RestrictionList") # Get value (might be None or dict)
            restrictions = []
            if isinstance(restriction_list_data, dict): # Only proceed if it's a dictionary
                restriction_item_data = restriction_list_data.get("RestrictionItem") # Get item (might be dict, list, or None)
                if isinstance(restriction_item_data, list):
                    restrictions = restriction_item_data
                elif isinstance(restriction_item_data, dict):
                    restrictions = [restriction_item_data] # Ensure it's a list
            # Now display if the final restrictions list is not empty
            if restrictions:
                res_text = ", ".join([
                    r.get('CodeDescription', r.get('Code', 'Unknown'))
                    for r in restrictions if isinstance(r, dict) # Process only if item is a dict
                ])
                st.write(f"**Restrictions:** {res_text if res_text else 'N/A'}")
            # --- End Corrected ---
        else: st.write("License details not available.")

    with tab_evt:
        evt_item = dl_record.get("EventList", {}).get("EventItem")
        events = [evt_item] if isinstance(evt_item, dict) else (evt_item if isinstance(evt_item, list) else [])
        if events:
            for i, event in enumerate(events):
                if not isinstance(event, dict): continue
                st.markdown(f"**Event {i+1}**")
                com, desc_i = event.get("Common", {}), event.get("DescriptionList", {}).get("DescriptionItem", {})
                viol, acc, act = event.get("Violation", {}), event.get("Accident", {}), event.get("Action", {})
                st.write(f" - **{L['mvr_event_subtype']}:** {com.get('Subtype', 'N/A')}")
                st.write(f" - **{L['mvr_event_date']}:** {format_date(com.get('Date'))}")
                st.write(f" - **{L['mvr_event_location']}:** {com.get('Location', 'N/A')}")
                st.write(f" - **{L['mvr_event_description']}:** {desc_i.get('AdrSmallDescription', 'N/A')}")
                st.write(f" - **{L['mvr_event_state_desc']}:** {desc_i.get('StateDescription', 'N/A')}")
                st.write(f" - **{L['mvr_event_points']}:** {desc_i.get('StateAssignedPoints', 'N/A')}")
                if viol: st.write(f" - **{L['mvr_event_conviction']}:** {format_date(viol.get('ConvictionDate'))}"); st.write(f" - **{L['mvr_event_fine']}:** {viol.get('FineAmount', 'N/A')}")
                if acc: st.write(f" - **Accident Report:** {acc.get('ReportNumber', 'N/A')}")
                if act: st.write(f" - **{L['mvr_event_action_clear']}:** {format_date(act.get('ClearDate'))}"); st.write(f" - **{L['mvr_event_action_reason']}:** {act.get('ClearReason', 'N/A')}")
                st.markdown("---")
        else: st.write(L["mvr_no_events"])

    with tab_msg:
        msg_item = dl_record.get("MessageList", {}).get("MessageItem")
        msgs = [msg_item] if isinstance(msg_item, dict) else (msg_item if isinstance(msg_item, list) else ([{"Line": msg_item}] if isinstance(msg_item, str) else []))
        if msgs: [st.write(f"- {m.get('Line', m) if isinstance(m,dict) else m}") for m in msgs]
        else: st.write(L["mvr_no_messages"])

    with tab_raw:
        # Use the passed original_mvr_result
        # Create a copy excluding the internal query key to avoid potential circular refs
        data_to_display = {k: v for k, v in original_mvr_result.items() if k != '_query_license_number'}
        st.json(data_to_display)

# --- MVR Pull Helper Function ---
def _get_licenses_from_form(widget_keys: Dict[str, Dict[str, str]]) -> List[Dict[str, str]]:
    """Extracts and cleans license info from form state."""
    licenses = []
    processed = set()
    for category, field_keys in widget_keys.items():
        keys = ('license_number', 'state', 'first_name', 'last_name')
        vals = {k: str(st.session_state.get(field_keys.get(k), '')).strip() for k in keys}
        if vals['license_number'] and vals['state']:
            pair = (vals['license_number'], vals['state'].upper())
            if pair not in processed:
                licenses.append(vals)
                processed.add(pair)
    return licenses

# --- Main App ---
st.title(L["app_title"])
st.markdown(L["app_description"])
st.markdown("---")

# UI Sections (Contact, Additional Info, File Uploaders)
st.subheader(f"📞 {L['contact_label']}")
c1, c2 = st.columns(2)
st.session_state.email = c1.text_input(L["contact_email_label"], value=st.session_state.get("email", ""), key="email_input")
st.session_state.phone = c2.text_input(L["contact_phone_label"], value=st.session_state.get("phone", ""), key="phone_input")
st.subheader(f"📋 {L['additional_info_title']}")
a1, a2 = st.columns(2)
owned = a1.radio(L["owned_by_self_question"], L["yes_options"], key="owned_by_self", index=st.session_state.get("owned_by_self_idx", 1))
named = a2.radio(L["named_drivers_question"], L["yes_options"], key="named_drivers", index=st.session_state.get("named_drivers_idx", 1))
st.session_state.owned_by_self_idx = L["yes_options"].index(owned)
st.session_state.named_drivers_idx = L["yes_options"].index(named)
st.markdown("---")
uploaded = st.file_uploader(L["upload_label"], type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True, key="uploaded_files")
other_file = st.file_uploader(L["other_driver_upload_label"], type=["jpg", "jpeg", "png", "pdf"], key="other_driver_file") if owned == ("No" if st.session_state.lang == "English" else "No") else None
files_to_process = (uploaded or []) + ([other_file] if other_file else [])
if other_file: st.caption(L["other_driver_file_label"].format(filename=other_file.name))
st.markdown("---")

# Initialize Session State
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'mvr_records' not in st.session_state: st.session_state.mvr_records = {}

# Process Button Logic
if st.button(L["process_button"], disabled=not files_to_process, key="process_docs_button"):
    if files_to_process:
        with st.spinner(L["processing_spinner"]):
            try:
                st.session_state.processed_data = process_documents(client, files_to_process, L["system_message"], owned_by_self=owned)
                st.session_state.mvr_records = {} # Clear old MVRs
                st.success(L["processing_success"])
            except Exception:
                st.session_state.processed_data = None; st.session_state.mvr_records = {}
                st.error(L['processing_failed'])
    else: st.warning("Please upload documents.")
st.markdown("---")

# --- Review/Edit Form ---
if st.session_state.processed_data:
    with st.expander(L["view_raw"]): st.json(st.session_state.processed_data.json(indent=2)) # V1
    st.header(L["review_title"])
    docs = [doc.dict() for doc in st.session_state.processed_data.documents] # V1
    contact = {"Email Address": st.session_state.get('email', ''), "Phone Number": st.session_state.get('phone', '')}
    flat_data = flatten_all_data(docs, contact)
    # --- CORRECTED GROUPING LOGIC ---
    grouped = {}
    for k, v in flat_data.items():
        try:
            # Try splitting into category and field based on " - "
            cat, field = k.split(" - ", 1)
            grouped.setdefault(cat, {})[field] = v
        except ValueError:
            # If split fails (key likely doesn't contain " - ")
            # Assign to a default "Uncategorized" category or handle specific keys
            # Based on flatten_all_data, only contact info should lack " - "
            # The flatten function adds "Contact Information - Field", so this except
            # block might only catch truly unexpected keys in flat_data.
            grouped.setdefault("Uncategorized", {})[k] = v
    # --- END CORRECTED GROUPING LOGIC ---

    # Optional: Sort fields within each category for consistent display
    for cat in grouped:
        grouped[cat] = dict(sorted(grouped[cat].items()))


    with st.form(key="review_form"):
        widget_keys = {}
        init_licenses = []
        cat_order = [L['contact_label']] + sorted([c for c in grouped if c != L['contact_label']])

        # Render Form Fields and MVR display area
        for cat in cat_order:
            if cat in grouped:
                st.markdown(f"#### {cat}")
                is_lic = cat in ["NYS Driver License", "Other Driver's License"]
                cat_keys = {}
                init_info = {} if is_lic else None
                cols = st.columns(2)
                for i, (field, value) in enumerate(grouped[cat].items()):
                    key = f"form_{''.join(filter(str.isalnum, cat))}_{''.join(filter(str.isalnum, field))}"
                    val = st.session_state.get(key, str(value or ""))
                    cols[i % 2].text_input(field, value=val, key=key)
                    if is_lic:
                        cat_keys[field] = key
                        if field in ('license_number', 'state', 'first_name', 'last_name') and value: init_info[field] = value
                if is_lic:
                    widget_keys[cat] = cat_keys
                    # Add to initial list for button disabling
                    if init_info.get('license_number') and init_info.get('state'):
                        pair = (str(init_info.get('license_number','')).strip(), str(init_info.get('state','')).strip().upper())
                        if pair[0] and pair[1] and pair not in set((str(l.get('license_number','')).strip(), str(l.get('state','')).strip().upper()) for l in init_licenses): init_licenses.append(init_info)

                # Display MVR Data if available
                if is_lic:
                    lic_key = cat_keys.get('license_number')
                    lic_num = str(st.session_state.get(lic_key, '')).strip() if lic_key else None
                    if lic_num and lic_num in st.session_state.get('mvr_records', {}):
                        mvr_data = st.session_state['mvr_records'][lic_num]
                        st.markdown("---")
                        st.subheader(f"{L['mvr_section_title']} ({lic_num})")
                        if mvr_data and not mvr_data.get("Error"):
                            st.success(L['mvr_pull_success'].format(license_number=lic_num))
                            dl_record = mvr_data.get("Record", {}).get("DlRecord", {})
                            # Don't add the original result to the dl_record itself
                            _display_mvr_tabs(dl_record, mvr_data, L) # Pass original mvr_data as separate param
                        elif mvr_data: st.error(L['mvr_pull_error'].format(license_number=lic_num, error_message=mvr_data.get("Message", "Unknown")))
                        st.markdown("---")

        # Form Buttons
        st.markdown("---")
        if not mvrnow_api_key: st.warning(L["mvr_api_key_missing"], icon="⚠️")
        b1, b2 = st.columns(2)
        pull_clicked = b1.form_submit_button(L["pull_mvr_button"], disabled=(not mvrnow_api_key or not init_licenses), type="secondary")
        submit_clicked = b2.form_submit_button(L["submit_button"], type="primary")

        # --- Form Submission Logic ---
        if pull_clicked:
            licenses_to_pull = _get_licenses_from_form(widget_keys) # Use helper
            if not licenses_to_pull: 
                st.warning("No valid license/state found in form.")
            else:
                results = {}
                placeholder = st.empty()
                errors = False
                with st.spinner("Pulling MVR records..."):
                    for lic in licenses_to_pull:
                        ln = lic['license_number']
                        placeholder.info(L["mvr_pull_inprogress"].format(license_number=ln))
                        try:
                            res = pull_mvr_record(mvrnow_api_key, lic['state'], ln, lic.get('first_name'), lic.get('last_name'))
                            results[ln] = res
                            errors = errors or res.get("Error", False)
                        except Exception as e: 
                            errors=True
                            results[ln] = {"Error":True,"Message":f"Script error: {e}"}
                            print(traceback.format_exc())
                placeholder.empty()
                st.session_state.mvr_records.update(results)
                if not errors:
                    st.success("MVR Pull process completed.")
                else:
                    st.warning("MVR Pull completed with errors.")

        if submit_clicked:
            final_data = {}
            for cat, keys in widget_keys.items():
                for fld, key in keys.items(): final_data[f"{cat} - {fld}"] = st.session_state.get(key, "")
            final_data[f"{L['contact_label']} - {L['contact_email_label']}"] = st.session_state.get('email_input', "")
            final_data[f"{L['contact_label']} - {L['contact_phone_label']}"] = st.session_state.get('phone_input', "")
            final_data[f"Additional Info - {L['owned_by_self_question']}"] = st.session_state.get('owned_by_self')
            final_data[f"Additional Info - {L['named_drivers_question']}"] = st.session_state.get('named_drivers')
            submission = {"formData": final_data, "mvrRecords": st.session_state.get('mvr_records', {})}
            st.success(L["submit_success"]); st.json(submission)
            # TODO: Send submission to backend