import streamlit as st, base64, json, os, httpx, asyncio, traceback
from typing import List, Dict, Any, Union
from openai import OpenAI
from functools import partial
from typing_extensions import Annotated
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal

# -------------------------------
# i18n: language dictionary
# -------------------------------
LANG = {
    "English": {
        "app_title": "TLC Insurance Application",
        "app_description": (
            "This application allows you to upload multiple documents at once:\n"
            "- **NYS Driver License**\n"
            "- **TLC Hack License**\n"
            "- **Vehicle Certificate of Title or Bill of Sale**\n"
            "- **Radio Base Certification Letter**\n\n"
            "All documents are processed together by GPT‑4o to extract structured data. "
            "Once processed, you can review and edit the extracted data before submitting your application."
        ),
        "additional_info_title": "Additional Information",
        "owned_by_self_question": "Is this vehicle owned and operated ONLY by yourself or spouse?",
        "named_drivers_question": "Is this vehicle operated by approved Named Drivers?",
        "other_driver_upload_label": "Upload Other Driver's License",
        "yes_options": ["Yes", "No"],
        "contact_label": "Contact Information",
        "contact_email_label": "Email Address",
        "contact_phone_label": "Phone Number",
        "process_button": "Process All Documents",
        "submit_button": "Submit Application",
        "view_raw": "View Raw Extracted Data (JSON)",
        "processing_spinner": "Processing all documents...",
        "processing_success": "✅ Documents processed successfully!",
        "processing_failed": "Processing failed. See error above.",
        "review_title": "📝 Review and Edit Extracted Information",
        "submit_success": "✅ Application submitted successfully!",
        "upload_label": "Upload all documents",
        "uploaded_count_label": "Uploaded {count} documents:",
        "other_driver_file_label": "Other driver file: {filename}",
        "system_message": (
            "You are a document processing assistant that extracts structured information from multiple documents. "
            "For each document, you need to identify the document type, return a JSON object with exactly three keys: \"type\", \"filename\", and \"data\".\n\n"
            "Extract the following based on the document type:\n"
            "- For \"NYS Driver License\": extract \"license_number\", \"first_name\", \"middle_name\" (if present), \"last_name\", \"address\", \"city\", \"state\", and \"zip_code\".\n"
            "- For \"TLC Hack License\": extract \"license_number\", \"first_name\", and \"last_name\".\n"
            "- For \"Vehicle Certificate of Title\" or \"Bill of Sale\": extract \"VIN\", \"vehicle_make\", \"vehicle_model\", \"vehicle_year\", and \"owner_name\".\n"
            "- For \"Radio Base Certification Letter\": extract \"radio_base_name\".\n"
            "- For \"Other Driver's License\" (if exist): extract \"license_number\", \"first_name\", \"middle_name\" (if present), \"last_name\", \"address\", \"city\", \"state\", and \"zip_code\".\n\n"
            "Return a single combined JSON object with a \"documents\" array containing these document objects. "
            "Ensure the field names are consistent and, for address, return individual fields rather than a combined string."
        )
    },
    "Español": {
        "app_title": "Solicitud de Seguro TLC",
        "app_description": (
            "Esta solicitud te permite subir varios documentos a la vez:\n"
            "- **Licencia de Conducir del Estado de Nueva York (NYS)**\n"
            "- **Licencia de Conductor TLC**\n"
            "- **Certificado de Título del Vehículo o Factura de Venta**\n"
            "- **Carta de Certificación de la Base de Radio**\n\n"
            "Todos los documentos se procesan juntos mediante GPT‑4o para extraer datos estructurados. "
            "Una vez procesados, podrás revisar y editar los datos extraídos antes de enviar tu solicitud."
        ),
        "additional_info_title": "Información Adicional",
        "owned_by_self_question": "¿Este vehículo es propiedad tuya y SOLO lo conduces tú o tu cónyuge?",
        "named_drivers_question": "¿Este vehículo es conducido por conductores nombrados aprobados?",
        "other_driver_upload_label": "Sube la Licencia de Conducir del Otro Conductor",
        "yes_options": ["Sí", "No"],
        "contact_label": "Información de Contacto",
        "contact_email_label": "Correo Electrónico",
        "contact_phone_label": "Número de Teléfono",
        "process_button": "Procesar Todos los Documentos",
        "submit_button": "Enviar Solicitud",
        "view_raw": "Ver Datos Extraídos (JSON)",
        "processing_spinner": "Procesando todos los documentos...",
        "processing_success": "✅ Documentos procesados exitosamente!",
        "processing_failed": "El procesamiento falló. Ver error arriba.",
        "review_title": "📝 Revisar y Editar la Información Extraída",
        "submit_success": "✅ Solicitud enviada exitosamente!",
        "upload_label": "Sube todos los documentos",
        "uploaded_count_label": "Subido {count} documentos:",
        "other_driver_file_label": "Archivo del otro conductor: {filename}",
        "system_message": (
            "Eres un asistente de procesamiento de documentos que extrae información estructurada de múltiples documentos. "
            "Para cada documento, necesitas identificar el tipo de documento, devolver un objeto JSON con exactamente tres claves: \"type\", \"filename\", y \"data\".\n\n"
            "Extrae lo siguiente según el tipo de documento:\n"
            "- Para \"Licencia de Conducir del Estado de Nueva York\": extrae \"license_number\", \"first_name\", \"middle_name\" (si existe), \"last_name\", \"address\", \"city\", \"state\", y \"zip_code\".\n"
            "- Para \"Licencia de Conductor TLC\": extrae \"license_number\", \"first_name\", y \"last_name\".\n"
            "- Para \"Certificado de Título del Vehículo\" o \"Factura de Venta\": extrae \"VIN\", \"vehicle_make\", \"vehicle_model\", \"vehicle_year\", y \"owner_name\".\n"
            "- Para \"Carta de Certificación de la Base de Radio\": extrae \"radio_base_name\".\n"
            "- Para \"Licencia de Conducir del Otro Conductor\" (si existe): extrae \"license_number\", \"first_name\", \"middle_name\" (si existe), \"last_name\", \"address\", \"city\", \"state\", y \"zip_code\".\n\n"
            "Devuelve un único objeto JSON combinado con una matriz \"documents\" que contenga estos objetos de documento. "
            "Asegúrate de que los nombres de los campos sean consistentes y, para la dirección, devuelve campos individuales en lugar de una cadena combinada."
        )
    }
}

# -------------------------------
# Pydantic models
# -------------------------------
class DocumentData(BaseModel):
    license_number: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    VIN: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[str] = None
    owner_name: Optional[str] = None
    radio_base_name: Optional[str] = None

class DocumentBase(BaseModel):
    filename: str # Keep filename in base model for processing context

class NYSDriverLicense(DocumentBase):
    type: Literal["NYS Driver License"]
    data: DocumentData

class TLCHackLicense(DocumentBase):
    type: Literal["TLC Hack License"]
    data: DocumentData

class VehicleCertificateOfTitle(DocumentBase):
    type: Literal["Vehicle Certificate of Title"]
    data: DocumentData

class BillOfSale(DocumentBase):
    type: Literal["Bill of Sale"]
    data: DocumentData

class RadioBaseCert(DocumentBase):
    type: Literal["Radio Base Certification Letter"]
    data: DocumentData

class OtherDriverLicense(DocumentBase):
    type: Literal["Other Driver's License"]
    data: DocumentData

    @validator('type', pre=True, always=True, allow_reuse=True)
    def normalize_type(cls, v):
        if v in ["Other", "Other Driver's License"]:
            return "Other Driver's License"
        raise ValueError(f"Invalid type for OtherDriverLicense: {v}")

DocumentUnion = Annotated[
    Union[
        NYSDriverLicense,
        TLCHackLicense,
        VehicleCertificateOfTitle,
        BillOfSale,
        RadioBaseCert,
        OtherDriverLicense
    ],
    Field(discriminator="type")
]

class ExtractionResult(BaseModel):
    documents: List[DocumentUnion]

# -------------------------------
# Streamlit app
# -------------------------------

# --- OpenAI Client Setup ---
# Ensure OPENAI_API_KEY is set in your environment variables or Streamlit secrets
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    http_client=httpx.Client(base_url="https://api.openai.com/v1", follow_redirects=True)
)

# --- Select Language & Display App ---
if 'lang' not in st.session_state:
    st.session_state.lang = list(LANG.keys())[0] # Default to English

def update_lang():
    st.session_state.lang = st.session_state.lang_select

lang_choice = st.selectbox(
    "Select Language / Seleccionar Idioma",
    list(LANG.keys()),
    key="lang_select",
    on_change=update_lang
)
L = LANG[st.session_state.lang]

st.title(L["app_title"])
st.write(L["app_description"])

# --- Helper Functions ---
def normalize_raw_documents(raw: dict) -> dict:
    """Ensures 'Other' type is mapped to 'Other Driver's License'."""
    for doc in raw.get("documents", []):
        if doc.get("type") == "Other":
            doc["type"] = "Other Driver's License"
    return raw

expected_fields = {
    "NYS Driver License": [
        "license_number", "first_name", "middle_name", "last_name",
        "address", "city", "state", "zip_code"
    ],
    "TLC Hack License": [
        "license_number", "first_name", "last_name"
    ],
    "Vehicle Certificate of Title": [
        "VIN", "vehicle_make", "vehicle_model", "vehicle_year", "owner_name"
    ],
    "Bill of Sale": [
        "VIN", "vehicle_make", "vehicle_model", "vehicle_year", "owner_name"
    ],
    "Radio Base Certification Letter": [
        "radio_base_name"
    ],
    "Other Driver's License": [
        "license_number", "first_name", "middle_name", "last_name",
        "address", "city", "state", "zip_code"
    ]
}

async def process_documents_async(files: List[Any], sys_message: str) -> ExtractionResult:
    """Processes uploaded files using OpenAI API asynchronously."""
    try:
        messages = [
            {"role": "system", "content": sys_message},
            {"role": "user", "content": []} # Content will be added below
        ]
        user_message_content = [{
            "type": "text",
            "text": (
                "Process these documents and extract all relevant information. "
                "Return a JSON with a 'documents' array where each document object "
                "has exactly three keys: 'type', 'filename', and 'data'. "
                "Determine the document type from the content. The filename is provided for context."
            )
        }]

        for file in files:
            file_bytes = file.getvalue() # Read bytes without affecting main file pointer
            b64 = base64.b64encode(file_bytes).decode("utf-8")
            # Determine mime type (basic implementation)
            mime_type = "image/jpeg" if file.name.lower().endswith(('.jpg', '.jpeg')) else \
                        "image/png" if file.name.lower().endswith('.png') else \
                        "application/pdf" if file.name.lower().endswith('.pdf') else \
                        "application/octet-stream" # Fallback

            desc = f"Filename: {file.name}" # Still provide filename to GPT for context
            user_message_content.extend([
                {"type": "text", "text": desc},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64}", "detail": "high"}}
            ])

        messages[1]["content"] = user_message_content # Add content to the user message

        create_completion = partial(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1
        )
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, create_completion)
        raw = json.loads(response.choices[0].message.content)
        raw = normalize_raw_documents(raw) # Normalize type names
        return ExtractionResult.parse_obj(raw) # Validate with Pydantic

    except Exception as e:
        st.error(f"Error during OpenAI processing: {type(e).__name__} - {str(e)}")
        st.code(traceback.format_exc(), language="python")
        raise

def flatten_doc_by_expected(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Flattens a single document based on its expected fields,
    prepending the document type to each field name.
    Does NOT include the filename in the flattened output.
    """
    doc_type = doc.get("type", "Unknown Document Type")
    data = doc.get("data", {})
    flat = {}
    fields_to_use = expected_fields.get(doc_type, list(data.keys())) # Use defined fields or all if type unknown

    # # --- REMOVED THIS LINE ---
    # # flat[f"{doc_type} - Filename"] = doc.get("filename", "N/A")
    # # --- ---

    for field in fields_to_use:
        # Ensure only expected fields for the type are included, or all if type unknown/unexpected
        if field in data or doc_type not in expected_fields:
             flat[f"{doc_type} - {field}"] = data.get(field, "") # Use empty string for missing fields

    return flat


def flatten_all_data(docs: List[Dict[str, Any]], contact_info: Dict[str, str]) -> Dict[str, Any]:
    """Flattens all document data and adds contact information."""
    flat = {}
    # Add contact info first
    for key, value in contact_info.items():
        flat[f"{L['contact_label']} - {key}"] = value

    # Then add document data
    for doc in docs:
        flat.update(flatten_doc_by_expected(doc))
    return flat

# --- UI: Contact & Additional Information ---
st.subheader("📞 " + L["contact_label"])
c1, c2 = st.columns(2)
# Initialize email and phone in session state if not present
if 'email' not in st.session_state:
    st.session_state.email = ""
if 'phone' not in st.session_state:
    st.session_state.phone = ""

email = c1.text_input(L["contact_email_label"], key="email")
phone = c2.text_input(L["contact_phone_label"], key="phone")


st.subheader("📋 " + L["additional_info_title"])
a1, a2 = st.columns(2)
# Use index=1 for 'No' as default, matching the condition for 'other_file' uploader
owned_default_index = 1 if L['yes_options'][1] == ("No" if st.session_state.lang == "English" else "No") else 0
owned = a1.radio(L["owned_by_self_question"], options=L["yes_options"], key="owned_by_self", index=owned_default_index)

named_default_index = 1 # Default to 'No'
named = a2.radio(L["named_drivers_question"], options=L["yes_options"], key="named_drivers", index=named_default_index)

# Store current user inputs (non-file) for potential later use or persistence
st.session_state.user_input = {
    L["contact_email_label"]: st.session_state.email,
    L["contact_phone_label"]: st.session_state.phone,
    L["owned_by_self_question"]: owned,
    L["named_drivers_question"]: named
}

# --- UI: File Uploaders ---
uploaded = st.file_uploader(L["upload_label"],
                            type=["jpg", "jpeg", "png", "pdf"],
                            accept_multiple_files=True,
                            key="uploaded_files")

other_file = None
# Check if the selected option corresponds to 'No'
is_owned_no = owned == ("No" if st.session_state.lang == "English" else "No")
if is_owned_no:
    other_file = st.file_uploader(L["other_driver_upload_label"],
                                  type=["jpg", "jpeg", "png", "pdf"],
                                  key="other_driver_file")

files_to_process = []
if uploaded:
    files_to_process.extend(uploaded)
if other_file:
    files_to_process.append(other_file)

# Display uploaded file names
if uploaded:
    st.write(L["uploaded_count_label"].format(count=len(uploaded)))
    # Use columns for better layout if many files
    cols = st.columns(3)
    for i, f in enumerate(uploaded):
        cols[i % 3].write(f"- {f.name}")
if other_file:
    st.write(L["other_driver_file_label"].format(filename=other_file.name))

# --- Process Button and Review Section ---
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None

if st.button(L["process_button"], disabled=not files_to_process):
    if files_to_process:
        with st.spinner(L["processing_spinner"]):
            try:
                # Run the async function
                extraction_result = asyncio.run(process_documents_async(files_to_process, L["system_message"]))
                st.session_state.processed_data = extraction_result # Store result in session state
                st.success(L["processing_success"])
                # Rerun to update the display immediately after processing
                st.rerun()
            except Exception as e:
                # Error is already displayed in the async function
                st.session_state.processed_data = None # Clear previous results on failure
                st.error(L["processing_failed"]) # Generic failure message
    else:
        st.warning("Please upload documents before processing.")

# --- Display Review/Edit Form if processing was successful ---
if st.session_state.processed_data:
    extraction_result = st.session_state.processed_data
    with st.expander(L["view_raw"]):
        # Display raw data (includes filename from GPT)
        st.json(extraction_result.dict())

    st.subheader(L["review_title"])

    # Convert each document Pydantic model to a dict
    docs_as_dicts = [doc.dict() for doc in extraction_result.documents]

    # Prepare contact info dictionary using current values from state
    contact_info = {
        L["contact_email_label"]: st.session_state.email,
        L["contact_phone_label"]: st.session_state.phone
    }

    # Flatten all data including contact info (flatten_doc_by_expected no longer adds filename)
    flat_data = flatten_all_data(docs_as_dicts, contact_info)

    # Group fields by category (Contact Info or Document Type)
    grouped_data = {}
    for key, value in flat_data.items():
        try:
            # Split key into Category (e.g., "Contact Information", "NYS Driver License") and Field Name
            category, field = key.split(" - ", 1)
            grouped_data.setdefault(category, {})[field] = value
        except ValueError:
            # Handle cases where the key might not have " - " (shouldn't happen with current logic)
            grouped_data.setdefault("Uncategorized", {})[key] = value

    # --- Form for Editing ---
    with st.form(key="review_form"):
        edited_data = {}

        # Determine the order: Contact first, then documents alphabetically by type
        category_order = [L['contact_label']] + sorted([cat for cat in grouped_data if cat != L['contact_label']])

        for category in category_order:
             if category in grouped_data:
                st.subheader(category) # Display Category/Document Type as subheader
                fields = grouped_data[category]
                items = list(fields.items())
                # Sort fields alphabetically within each category for consistent order
                items.sort(key=lambda item: item[0])

                for i in range(0, len(items), 2): # Display in 2 columns
                    cols = st.columns(2)
                    for j in range(2):
                        if i + j < len(items):
                            field, value = items[i + j]
                            # Use a unique key combining category and field name, replacing spaces
                            input_key = f"{category.replace(' ', '_')}_{field.replace(' ', '_')}"
                            # The edited value is stored with the original combined key format
                            edited_data[f"{category} - {field}"] = cols[j].text_input(
                                field, # Use the readable field name as the label
                                value=str(value),
                                key=input_key
                            )

        # Add the non-editable radio button choices to the final data for submission context
        edited_data["Additional Info - " + L["owned_by_self_question"]] = owned
        edited_data["Additional Info - " + L["named_drivers_question"]] = named

        # Submit button for the form
        submitted = st.form_submit_button(L["submit_button"])
        if submitted:
            st.success(L["submit_success"])
            st.json(edited_data) # Display the final edited data
            # Here you would typically send the 'edited_data' to your backend/API
            # e.g., httpx.post("YOUR_API_ENDPOINT", json=edited_data)
            # Optionally clear processed data after submission
            # st.session_state.processed_data = None
            # st.rerun()