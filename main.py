import streamlit as st
import base64
import json
import os
import httpx
import asyncio
import time
import traceback
from typing import List, Dict, Any, Union
from openai import OpenAI
from openai._base_client import SyncHttpxClientWrapper
from functools import partial

# -----------------------------------------------------------------------------
# Setup: Custom HTTP Client & OpenAI Client Initialization
# -----------------------------------------------------------------------------
http_client = httpx.Client(
    base_url="https://api.openai.com/v1",
    follow_redirects=True,
)

client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    http_client=http_client
)

# -----------------------------------------------------------------------------
# Language Selection & Text Definitions
# -----------------------------------------------------------------------------
language = st.selectbox("Select Language / Seleccionar Idioma", options=["English", "Español"])

if language == "English":
    app_title = "TLC Insurance Application"
    app_description = (
        "This application allows you to upload multiple documents at once:\n"
        "- **NYS Driver License**\n"
        "- **TLC Hack License**\n"
        "- **Vehicle Certificate of Title or Bill of Sale**\n"
        "- **Radio Base Certification Letter**\n\n"
        "All documents are processed together by GPT‑4o to extract structured data. "
        "Once processed, you can review and edit the extracted data before submitting your application."
    )
    additional_info_title = "Additional Information"
    owned_by_self_question = "Is this vehicle owned and operated only by yourself or spouse?"
    other_driver_upload_label = "Upload Other Driver's License"
    yes_options = ["Yes", "No"]
else:
    app_title = "Solicitud de Seguro TLC"
    app_description = (
        "Esta solicitud te permite subir varios documentos a la vez:\n"
        "- **Licencia de Conducir del Estado de Nueva York (NYS)**\n"
        "- **Licencia de Conductor TLC**\n"
        "- **Certificado de Título del Vehículo o Factura de Venta**\n"
        "- **Carta de Certificación de la Base de Radio**\n\n"
        "Todos los documentos se procesan juntos mediante GPT‑4o para extraer datos estructurados. "
        "Una vez procesados, podrás revisar y editar los datos extraídos antes de enviar tu solicitud."
    )
    additional_info_title = "Información Adicional"
    owned_by_self_question = "¿Este vehículo es propiedad tuya y solo lo conduces tú o tu cónyuge?"
    other_driver_upload_label = "Sube la Licencia de Conducir del Otro Conductor"
    yes_options = ["Sí", "No"]

st.title(app_title)
st.write(app_description)

# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def detect_document_type(file_name: str) -> str:
    """
    Detect document type based on file name keywords.
    """
    file_name = file_name.lower()
    if any(term in file_name for term in ["nys", "driver", "license", "dl"]):
        return "nys_license"
    elif any(term in file_name for term in ["tlc", "hack", "hack_license"]):
        return "tlc_license"
    elif any(term in file_name for term in ["vehicle", "title", "bill", "sale", "cert", "certificate"]):
        return "vehicle_title"
    elif any(term in file_name for term in ["radio", "base", "certification", "letter"]):
        return "radio_base_cert"
    else:
        return "unknown"

def display_field_groups(doc_type: str, address_fields: Dict[str, Any],
                         owner_fields: Dict[str, Any], other_fields: Dict[str, Any],
                         idx: Union[int, None] = None) -> None:
    """
    Display field groups (Address, Owner, Other Information) in a consistent layout.
    """
    key_suffix = f"_{doc_type}" + (f"_{idx}" if idx is not None else "")

    if address_fields:
        st.write("**Address:**")
        cols = st.columns(2)
        col_idx = 0
        for field, value in sorted(address_fields.items()):
            cols[col_idx].text_input(
                field.title(),
                value,
                disabled=True,
                key=f"result_address_{field}{key_suffix}"
            )
            col_idx = (col_idx + 1) % 2

    if owner_fields:
        st.write("**Owner:**")
        cols = st.columns(2)
        col_idx = 0
        for field, value in sorted(owner_fields.items()):
            cols[col_idx].text_input(
                field.title(),
                value,
                disabled=True,
                key=f"result_owner_{field}{key_suffix}"
            )
            col_idx = (col_idx + 1) % 2

    if other_fields:
        # Display contact fields first if present
        contact_fields = {k: v for k, v in other_fields.items() if k.startswith("Contact -")}
        if contact_fields:
            st.write("**Contact Information:**")
            cols = st.columns(2)
            col_idx = 0
            for field, value in sorted(contact_fields.items()):
                field_name = field.replace("Contact - ", "")
                cols[col_idx].text_input(
                    field_name,
                    value,
                    disabled=True,
                    key=f"result_contact_{field_name}{key_suffix}"
                )
                col_idx = (col_idx + 1) % 2

        # Display additional information fields if present
        additional_fields = {k: v for k, v in other_fields.items() if k.startswith("Additional -")}
        if additional_fields:
            st.write("**Additional Information:**")
            cols = st.columns(2)
            col_idx = 0
            for field, value in sorted(additional_fields.items()):
                field_name = field.replace("Additional - ", "")
                cols[col_idx].text_input(
                    field_name,
                    value,
                    disabled=True,
                    key=f"result_additional_{field_name}{key_suffix}"
                )
                col_idx = (col_idx + 1) % 2

        # Display any remaining fields
        remaining_fields = {
            k: v for k, v in other_fields.items() 
            if not k.startswith(("Contact -", "Additional -"))
        }
        if remaining_fields:
            if address_fields or owner_fields:
                st.write("**Other Information:**")
            cols = st.columns(2)
            col_idx = 0
            for field, value in sorted(remaining_fields.items()):
                if isinstance(value, dict):
                    st.write(f"**{field.title()}:**")
                    subcols = st.columns(2)
                    subcol_idx = 0
                    for subfield, subvalue in sorted(value.items()):
                        subcols[subcol_idx].text_input(
                            subfield.title(),
                            subvalue,
                            disabled=True,
                            key=f"result_{field}_{subfield}{key_suffix}"
                        )
                        subcol_idx = (subcol_idx + 1) % 2
                else:
                    cols[col_idx].text_input(
                        field.title(),
                        value,
                        disabled=True,
                        key=f"result_{field}{key_suffix}"
                    )
                    col_idx = (col_idx + 1) % 2

async def process_documents_with_gpt4o(files: List[Any]) -> Dict[str, Any]:
    """
    Process multiple documents using GPT‑4o via OpenAI chat completions.
    """
    try:
        system_message = (
            "You are a document processing assistant that extracts information from multiple documents.\n"
            "Extract information from each document and categorize them properly.\n\n"
            "For NYS Driver License: extract license_number, first_name, middle_name (if present), last_name, address, city, state, zip_code.\n"
            "For TLC Hack License: extract license_number, first_name, last_name.\n"
            "For Vehicle Certificate of Title or Bill of Sale: extract VIN, vehicle_make, vehicle_model, vehicle_year, owner_name.\n"
            "For Radio Base Certification Letter: extract radio_base_name.\n"
            "For Other Driver's License (if provided): extract license_number, first_name, last_name.\n\n"
            "Return a single combined JSON with the following structure:\n"
            '{ "documents": [ { "document_type": "NYS Driver License", "data": { "license_number": "123456789", "first_name": "John", "last_name": "Doe", ... } }, ... ] }\n\n'
            "Always use consistent field names like license_number, first_name, last_name, address, city, state, zip_code.\n"
            "For address information, return individual fields (address, city, state, zip_code) instead of a combined string."
        )
        messages = [{"role": "system", "content": system_message}]
        user_message_content = [{
            "type": "text",
            "text": "Process these documents and extract all relevant information. Return the data in a single combined JSON format."
        }]

        # Process each file as an image with a description
        for file in files:
            file_bytes = file.read()
            file.seek(0)  # Reset pointer for potential reuse
            base64_image = base64.b64encode(file_bytes).decode("utf-8")
            doc_type = detect_document_type(file.name)
            doc_desc = f"Document type (if detectable): {doc_type}, Filename: {file.name}"
            user_message_content.append({"type": "text", "text": doc_desc})
            user_message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}",
                    "detail": "high"
                }
            })

        messages.append({"role": "user", "content": user_message_content})
        create_completion = partial(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"}
        )
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, create_completion)
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data

    except Exception as e:
        st.error(f"Exception details: {type(e).__name__} - {str(e)}")
        st.code(traceback.format_exc(), language="python")
        return {"error": f"Failed to process documents: {str(e)}"}

# -----------------------------------------------------------------------------
# UI: Contact, Additional Information, & Document Upload
# -----------------------------------------------------------------------------
st.header("Document Upload")

# Contact Information Section
st.subheader("📞 Contact Information")
contact_col1, contact_col2 = st.columns(2)
email = contact_col1.text_input("Email Address" if language == "English" else "Correo Electrónico", key="email")
phone = contact_col2.text_input("Phone Number" if language == "English" else "Número de Teléfono", key="phone")

# Additional Information Section
st.subheader("📋 " + (additional_info_title))
questions_col1, questions_col2 = st.columns(2)
owned_by_self = questions_col1.radio(owned_by_self_question, options=yes_options, key="owned_by_self")
named_drivers = questions_col2.radio(
    "Is this vehicle operated by approved Named Drivers?" if language == "English" else "¿Este vehículo es conducido por conductores nombrados aprobados?",
    options=yes_options,
    key="named_drivers"
)
workers_comp = questions_col1.radio(
    "Do you currently carry workers compensation?" if language == "English" else "¿Actualmente cuentas con compensación para trabajadores?",
    options=yes_options,
    key="workers_comp"
)
radio_base = questions_col2.radio(
    "Do you obtain fares via Radio Base?" if language == "English" else "¿Obtienes tarifas a través de la Base de Radio?",
    options=yes_options,
    key="radio_base"
)

# Persist user input for later use
if 'user_input' not in st.session_state:
    st.session_state.user_input = {}
st.session_state.user_input.update({
    "Contact - Email": email,
    "Contact - Phone": phone,
    "Additional - Vehicle Owned By Self/Spouse": owned_by_self,
    "Additional - Has Named Drivers": named_drivers,
    "Additional - Has Workers Compensation": workers_comp,
    "Additional - Obtains Fares via Radio Base": radio_base
})

# Main File Uploader for Documents
uploaded_files = st.file_uploader(
    "Upload all documents" if language == "English" else "Sube todos los documentos",
    type=["jpg", "jpeg", "png", "pdf"],
    accept_multiple_files=True
)

# Conditional File Uploader: If the vehicle is NOT solely operated by the applicant,
# require the upload of the other driver's license.
other_driver_file = None
if owned_by_self == ("No" if language == "English" else "No"):
    other_driver_file = st.file_uploader(
        other_driver_upload_label,
        type=["jpg", "jpeg", "png", "pdf"],
        key="other_driver"
    )

if uploaded_files:
    st.write(f"Uploaded {len(uploaded_files)} documents:")
    for file in uploaded_files:
        st.write(f"- {file.name} ({detect_document_type(file.name)})")

# -----------------------------------------------------------------------------
# Process & Submit Documents
# -----------------------------------------------------------------------------
if st.button("Process All Documents" if language == "English" else "Procesar Todos los Documentos"):
    with st.spinner("Processing all documents... This may take a minute." if language == "English" else "Procesando todos los documentos... Puede tardar un minuto."):
        # Combine main documents with the additional driver's license if provided
        files_to_process = list(uploaded_files)
        if owned_by_self == ("No" if language == "English" else "No") and other_driver_file is not None:
            # Ensure the extra file has a proper filename if missing
            if not hasattr(other_driver_file, "name") or other_driver_file.name == "":
                other_driver_file.name = "other_driver_license.jpg"
            files_to_process.append(other_driver_file)
        results = asyncio.run(process_documents_with_gpt4o(files_to_process))
        
        if "error" not in results:
            st.success("✅ Documents processed successfully!" if language == "English" else "¡✅ Documentos procesados con éxito!")
            with st.expander("View Raw Extracted Data (JSON)" if language == "English" else "Ver Datos Extraídos (JSON)", expanded=False):
                st.json(results)

            st.subheader("📝 Review and Edit Extracted Information" if language == "English" else "📝 Revisa y Edita la Información Extraída")
            st.info("Please review the extracted information below. You can edit any field if needed." if language == "English" else "Revisa la información extraída a continuación. Puedes editar cualquier campo si es necesario.")

            # -----------------------------------------------------------------------------
            # Data Flattening & Standardization for Editing
            # -----------------------------------------------------------------------------
            flat_data = {}
            flat_data.update(st.session_state.user_input)
            standardized_documents = []
            try:
                if "documents" in results and isinstance(results["documents"], list):
                    for doc in results["documents"]:
                        if not isinstance(doc, dict):
                            continue
                        doc_type_field = next((f for f in ["document_type", "type", "doc_type"] if f in doc), None)
                        if not doc_type_field:
                            continue
                        doc_type = doc[doc_type_field].lower().replace(" ", "_")
                        doc_type_value = doc[doc_type_field].lower()
                        if ("tlc" in doc_type_value or "hack" in doc_type_value):
                            doc_type = "tlc_license"
                        elif ("driver" in doc_type_value or "nys" in doc_type_value):
                            doc_type = "nys_license"
                        elif ("vehicle" in doc_type_value or "title" in doc_type_value or "bill" in doc_type_value or "sale" in doc_type_value):
                            doc_type = "vehicle_title"
                        elif ("radio" in doc_type_value or "base" in doc_type_value):
                            doc_type = "radio_base_cert"
                        elif ("other" in doc_type_value):
                            doc_type = "other_driver_license"
                        if "data" in doc and isinstance(doc["data"], dict):
                            doc_data = doc["data"]
                        else:
                            doc_data = {k: v for k, v in doc.items() if k not in ["document_type", "type", "doc_type"]}
                        standardized_data = {}
                        if ("address" not in doc_data or not isinstance(doc_data["address"], dict)) and \
                           any(k in ["address", "street", "city", "state", "zip", "zip_code"] for k in doc_data):
                            standardized_data["address"] = {}
                            field_mappings = {
                                "address": "street",
                                "street": "street",
                                "city": "city", 
                                "state": "state",
                                "zip": "zip",
                                "zip_code": "zip"
                            }
                            for src_field, dest_field in field_mappings.items():
                                if src_field in doc_data:
                                    standardized_data["address"][dest_field] = doc_data[src_field]
                                    if src_field != "address":
                                        doc_data.pop(src_field, None)
                        for key, value in doc_data.items():
                            standardized_data[key] = value
                        standardized_documents.append({
                            "document_type": doc_type,
                            "data": standardized_data
                        })
                else:
                    for doc_type, content in results.items():
                        if (not isinstance(content, (dict, list))) or doc_type.startswith("_"):
                            continue
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict):
                                    standardized_documents.append({
                                        "document_type": doc_type,
                                        "data": item
                                    })
                        elif isinstance(content, dict):
                            standardized_documents.append({
                                "document_type": doc_type,
                                "data": content
                            })
                with st.expander("View Standardized Data Structure" if language == "English" else "Ver Estructura de Datos Estandarizada", expanded=False):
                    st.json({"documents": standardized_documents})
                for doc in standardized_documents:
                    doc_type = doc["document_type"]
                    doc_data = doc["data"]
                    for field_name, field_value in doc_data.items():
                        if isinstance(field_value, dict):
                            for nested_key, nested_value in field_value.items():
                                label = f"{doc_type.title()} - {field_name.title()} {nested_key.title()}"
                                flat_data[label] = nested_value
                        else:
                            label = f"{doc_type.title()} - {field_name.title()}"
                            flat_data[label] = field_value
            except Exception as e:
                st.error(f"Error processing JSON data: {str(e)}")
                st.code(traceback.format_exc(), language="python")
            
            # -----------------------------------------------------------------------------
            # Data Editing UI: Grouping by Document Type
            # -----------------------------------------------------------------------------
            if flat_data:
                grouped_data = {}
                for key, value in flat_data.items():
                    doc_type, field_name = key.split(' - ', 1)
                    if doc_type not in grouped_data:
                        grouped_data[doc_type] = {}
                    grouped_data[doc_type][field_name] = value

                edited_values = {}
                for doc_type, fields in grouped_data.items():
                    with st.expander(f"📄 {doc_type} Information", expanded=True):
                        field_groups = {}
                        for field_name, field_value in fields.items():
                            parts = field_name.split(' ', 1)
                            if len(parts) > 1 and parts[0] in ['Address', 'Owner']:
                                parent = parts[0]
                                if parent not in field_groups:
                                    field_groups[parent] = {}
                                field_groups[parent][parts[1]] = field_value
                            else:
                                if 'Other' not in field_groups:
                                    field_groups['Other'] = {}
                                field_groups['Other'][field_name] = field_value
                        for group_name, group_fields in field_groups.items():
                            if group_name != 'Other':
                                st.subheader(f"{group_name}")
                            if group_name in ['Address', 'Owner']:
                                cols = st.columns(2)
                                col_idx = 0
                                for field_name, field_value in group_fields.items():
                                    edited_field = cols[col_idx].text_input(
                                        field_name,
                                        value=field_value,
                                        key=f"{doc_type}_{group_name}_{field_name}"
                                    )
                                    full_key = f"{doc_type} - {group_name} {field_name}"
                                    edited_values[full_key] = edited_field
                                    col_idx = (col_idx + 1) % 2
                            else:
                                cols = st.columns(2)
                                col_idx = 0
                                for field_name, field_value in sorted(group_fields.items()):
                                    edited_field = cols[col_idx].text_input(
                                        field_name,
                                        value=field_value,
                                        key=f"{doc_type}_Other_{field_name}"
                                    )
                                    full_key = f"{doc_type} - {field_name}"
                                    edited_values[full_key] = edited_field
                                    col_idx = (col_idx + 1) % 2
                st.write("")
                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    submit_button = st.button("📤 Submit Application" if language == "English" else "📤 Enviar Solicitud", type="primary", use_container_width=True)
                if submit_button:
                    with st.spinner("Processing your submission..." if language == "English" else "Procesando tu solicitud..."):
                        time.sleep(0.5)
                        final_data = edited_values
                        final_data.update(st.session_state.user_input)
                        organized_data = {}
                        contact_data = {
                            "document_type": "Contact Information" if language == "English" else "Información de Contacto",
                            "data": {
                                "email": st.session_state.user_input["Contact - Email"],
                                "phone": st.session_state.user_input["Contact - Phone"]
                            }
                        }
                        additional_data = {
                            "document_type": "Additional Information" if language == "English" else "Información Adicional",
                            "data": {
                                "vehicle_owned_by_self": st.session_state.user_input["Additional - Vehicle Owned By Self/Spouse"],
                                "has_named_drivers": st.session_state.user_input["Additional - Has Named Drivers"],
                                "has_workers_compensation": st.session_state.user_input["Additional - Has Workers Compensation"],
                                "obtains_fares_via_radio_base": st.session_state.user_input["Additional - Obtains Fares via Radio Base"]
                            }
                        }
                        original_structure = {}
                        for doc_type, content in results.items():
                            if isinstance(content, list):
                                original_structure[doc_type.lower().replace(" ", "_")] = "array"
                            elif isinstance(content, dict):
                                original_structure[doc_type.lower().replace(" ", "_")] = "object"
                        doc_fields = {}
                        for key, value in final_data.items():
                            parts = key.split(' - ', 1)
                            if len(parts) == 2:
                                key_doc_type = parts[0].lower().replace(' ', '_')
                                field = parts[1].lower().replace(' ', '_')
                                field_parts = field.split('_')
                                if key_doc_type not in doc_fields:
                                    doc_fields[key_doc_type] = set()
                                if len(field_parts) > 1 and field_parts[0] in ['address', 'owner']:
                                    doc_fields[key_doc_type].add(field_parts[0])
                                else:
                                    doc_fields[key_doc_type].add(field)
                        for doc_type in doc_fields:
                            doc_data = {}
                            for field in doc_fields[doc_type]:
                                if field in ['address', 'owner']:
                                    doc_data[field] = {}
                            for key, value in final_data.items():
                                parts = key.split(' - ', 1)
                                if len(parts) == 2:
                                    key_doc_type = parts[0].lower().replace(' ', '_')
                                    field = parts[1].lower().replace(' ', '_')
                                    if key_doc_type == doc_type:
                                        field_parts = field.split('_')
                                        if len(field_parts) > 1 and field_parts[0] in ['address', 'owner']:
                                            parent_field = field_parts[0]
                                            child_field = '_'.join(field_parts[1:])
                                            doc_data[parent_field][child_field] = value
                                        else:
                                            doc_data[field] = value
                            if doc_type in original_structure and original_structure[doc_type] == "array":
                                organized_data[doc_type] = [doc_data]
                            else:
                                organized_data[doc_type] = doc_data
                        if "documents" in results:
                            final_organized_data = {"documents": []}
                            final_organized_data["documents"].append(contact_data)
                            final_organized_data["documents"].append(additional_data)
                            for doc_type, data in organized_data.items():
                                if isinstance(data, list):
                                    for item in data:
                                        final_organized_data["documents"].append({
                                            "document_type": doc_type.replace('_', ' ').title(),
                                            "data": item
                                        })
                                else:
                                    final_organized_data["documents"].append({
                                        "document_type": doc_type.replace('_', ' ').title(),
                                        "data": data
                                    })
                            organized_data = final_organized_data
                        else:
                            organized_data["contact_information"] = contact_data["data"]
                            organized_data["additional_information"] = additional_data["data"]
                        st.success("✅ Application submitted successfully!" if language == "English" else "¡✅ Solicitud enviada con éxito!")
                        st.subheader("Submitted Information" if language == "English" else "Información Enviada")
                        if "documents" in organized_data:
                            for doc_index, doc in enumerate(organized_data["documents"]):
                                with st.expander(f"{doc['document_type']} Information" if language == "English" else f"{doc['document_type']} Información", expanded=True):
                                    address_fields = {}
                                    owner_fields = {}
                                    other_fields = {}
                                    for field, value in doc["data"].items():
                                        if field.lower() == "address" and isinstance(value, dict):
                                            address_fields = value
                                        elif field.lower() == "owner" and isinstance(value, dict):
                                            owner_fields = value
                                        else:
                                            other_fields[field] = value
                                    display_field_groups(doc['document_type'], address_fields, owner_fields, other_fields, doc_index)
                        else:
                            for doc_type, content in organized_data.items():
                                display_title = doc_type.replace('_', ' ').title()
                                if isinstance(content, list):
                                    for idx, item in enumerate(content):
                                        with st.expander(f"{display_title} #{idx+1}", expanded=True):
                                            if isinstance(item, dict):
                                                address_fields = {}
                                                owner_fields = {}
                                                other_fields = {}
                                                for field, value in item.items():
                                                    if field.lower() == "address" and isinstance(value, dict):
                                                        address_fields = value
                                                    elif field.lower() == "owner" and isinstance(value, dict):
                                                        owner_fields = value
                                                    else:
                                                        other_fields[field] = value
                                                display_field_groups(display_title, address_fields, owner_fields, other_fields, idx)
                                else:
                                    with st.expander(f"{display_title} Information", expanded=True):
                                        if isinstance(content, dict):
                                            address_fields = {}
                                            owner_fields = {}
                                            other_fields = {}
                                            for field, value in content.items():
                                                if field.lower() == "address" and isinstance(value, dict):
                                                    address_fields = value
                                                elif field.lower() == "owner" and isinstance(value, dict):
                                                    owner_fields = value
                                                else:
                                                    other_fields[field] = value
                                            display_field_groups(display_title, address_fields, owner_fields, other_fields)