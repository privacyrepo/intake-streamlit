import streamlit as st
import base64
import json
import pandas as pd
from typing import List, Dict, Any
import os
import httpx
from openai import OpenAI
from openai._base_client import SyncHttpxClientWrapper

# Create a custom HTTP client with no proxy settings
http_client = httpx.Client(
    base_url="https://api.openai.com/v1",
    follow_redirects=True,
    # No proxies or other settings
)

# Initialize OpenAI client with custom HTTP client to avoid proxy issues
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY"),
    http_client=http_client
)

st.title("AI-Powered Document Intake Form")

st.write("""
This application allows you to upload multiple documents at once:
- **Driver License (NYS Driver License)**
- **TLC Hack License**
- **Vehicle Certificate of Title**
- **Radio Base Certification Letter**

All documents are processed together by GPT‑4o to extract structured data. Once processed, you can review and edit the extracted data before submitting your application.
""")

def detect_document_type(file_name: str) -> str:
    """
    Attempt to detect document type from the file name
    """
    file_name = file_name.lower()
    
    if any(term in file_name for term in ["nys", "driver", "license", "dl"]):
        return "nys_license"
    elif any(term in file_name for term in ["tlc", "hack", "hack_license"]):
        return "tlc_license"
    elif any(term in file_name for term in ["vehicle", "title", "cert", "certificate"]):
        return "vehicle_title"
    elif any(term in file_name for term in ["radio", "base", "certification", "letter"]):
        return "radio_base_cert"
    else:
        return "unknown"

def display_field_groups(doc_type, address_fields, owner_fields, other_fields, idx=None):
    """Helper function to display field groups in a consistent layout"""
    # Generate a unique key suffix
    key_suffix = f"_{doc_type}" + (f"_{idx}" if idx is not None else "")
    
    # Display address fields if present
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
    
    # Display owner fields if present
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
    
    # Display other fields
    if other_fields:
        # Display contact information first if present
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
        
        # Display additional information (yes/no questions)
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
        
        # Display remaining fields
        remaining_fields = {k: v for k, v in other_fields.items() 
                          if not k.startswith(("Contact -", "Additional -"))}
        if remaining_fields:
            if address_fields or owner_fields:
                st.write("**Other Information:**")
            
            cols = st.columns(2)
            col_idx = 0
            for field, value in sorted(remaining_fields.items()):
                if isinstance(value, dict):
                    # Handle any other nested structures
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

async def process_documents_with_gpt4o(files) -> Dict[str, Any]:
    """
    Process multiple documents at once with GPT-4o using chat completions
    """
    try:
        # Prepare system message
        system_message = """You are a document processing assistant that extracts information from multiple documents.
        Extract information from each document and categorize them properly.
        
        For NYS Driver License: extract license_number, first_name, middle_name (if present), last_name, address, city, state, zip_code.
        For TLC Hack License: extract license_number, first_name, last_name.
        For Vehicle Certificate of Title: extract VIN, vehicle_make, vehicle_model, vehicle_year, owner_name.
        For Radio Base Certification Letter: extract radio_base_name.
        For Uber Affiliation Letter: extract license_number, first_name, last_name, company_name, address, city, state, zip_code.
        
        Return a single combined JSON with the following structure:
        {
          "documents": [
            {
              "document_type": "NYS Driver License",
              "data": {
                "license_number": "123456789",
                "first_name": "John",
                "last_name": "Doe",
                ...
              }
            },
            ...
          ]
        }
        
        Always use consistent field names like license_number, first_name, last_name, address, city, state, zip_code.
        For address information, return individual fields (address, city, state, zip_code) instead of a combined string."""
        
        # Prepare messages list
        messages = [
            {"role": "system", "content": system_message},
        ]
        
        # Prepare user message content
        user_message_content = [
            {"type": "text", "text": "Process these documents and extract all relevant information. Return the data in a single combined JSON format."}
        ]
        
        # Add each document as an image
        for file in files:
            file_bytes = file.read()
            file.seek(0)  # Reset file pointer for potential reuse
            base64_image = base64.b64encode(file_bytes).decode("utf-8")
            
            # Try to detect document type from filename
            doc_type = detect_document_type(file.name)
            doc_desc = f"Document type (if detectable): {doc_type}, Filename: {file.name}"
            
            user_message_content.append(
                {"type": "text", "text": doc_desc}
            )
            
            user_message_content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}", "detail": "high"}}
            )
        
        # Add user message with content
        messages.append({"role": "user", "content": user_message_content})
        
        # Call OpenAI API with all documents using chat completions
        import asyncio
        from functools import partial
        
        # Create a partial function and run it in the executor
        create_completion = partial(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        # Run the synchronous function in the default executor to make it async
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, create_completion)
        
        # Parse the JSON response
        extracted_data = json.loads(response.choices[0].message.content)
        return extracted_data
    except Exception as e:
        # Log the error or handle it as necessary
        st.error(f"Exception details: {type(e).__name__} - {str(e)}")
        import traceback
        st.code(traceback.format_exc(), language="python")
        return {"error": f"Failed to process documents: {str(e)}"}

st.header("Document Upload")

# Add contact information section first
st.subheader("📞 Contact Information")
contact_col1, contact_col2 = st.columns(2)
email = contact_col1.text_input("Email Address", key="email")
phone = contact_col2.text_input("Phone Number", key="phone")

# Add yes/no questions section
st.subheader("📋 Additional Information")
questions_col1, questions_col2 = st.columns(2)

owned_by_self = questions_col1.radio(
    "Is this vehicle owned and operated only by yourself or spouse?",
    options=["Yes", "No"],
    key="owned_by_self"
)

named_drivers = questions_col2.radio(
    "Is this vehicle operated by approved Named Drivers?",
    options=["Yes", "No"],
    key="named_drivers"
)

workers_comp = questions_col1.radio(
    "Do you currently carry workers compensation?",
    options=["Yes", "No"],
    key="workers_comp"
)

radio_base = questions_col2.radio(
    "Do you obtain fares via Radio Base?",
    options=["Yes", "No"],
    key="radio_base"
)

# Store user input in session state to persist it
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

# Create a single multi-file uploader widget
uploaded_files = st.file_uploader("Upload all documents", type=["jpg", "jpeg", "png", "pdf"], accept_multiple_files=True)

if uploaded_files:
    st.write(f"Uploaded {len(uploaded_files)} documents:")
    for file in uploaded_files:
        st.write(f"- {file.name} ({detect_document_type(file.name)})")
    
    if st.button("Process All Documents"):
        with st.spinner("Processing all documents... This may take a minute."):
            # Process all documents together
            import asyncio
            results = asyncio.run(process_documents_with_gpt4o(uploaded_files))
            
            # Create an editable view of the data if successful
            if "error" not in results:
                st.success("✅ Documents processed successfully!")
                
                # Optional: Show raw JSON in an expandable section for debugging
                with st.expander("View Raw Extracted Data (JSON)", expanded=False):
                    st.json(results)
                
                st.subheader("📝 Review and Edit Extracted Information")
                st.info("Please review the extracted information below. You can edit any field if needed.")
                
                # Create a flattened DataFrame for editing
                flat_data = {}
                
                # Add user input data first
                flat_data.update(st.session_state.user_input)
                
                # Handle any JSON structure that might come back from the API
                try:
                    # Standardize the response format for consistency
                    standardized_documents = []
                    
                    # Structure 1: "documents" array with type/document_type and data fields
                    if "documents" in results and isinstance(results["documents"], list):
                        for doc in results["documents"]:
                            # Skip invalid documents
                            if not isinstance(doc, dict):
                                continue
                                
                            # Get document type (handle different field names)
                            doc_type_field = next((f for f in ["document_type", "type", "doc_type"] 
                                                 if f in doc), None)
                            if not doc_type_field:
                                continue
                                
                            doc_type = doc[doc_type_field].lower().replace(" ", "_")
                            
                            # Check both field name and value for better matching
                            doc_type_value = doc[doc_type_field].lower()
                            
                            # Standardize document type based on content
                            if ("tlc" in doc_type_value or "hack" in doc_type_value):
                                doc_type = "tlc_hack_license"
                            elif ("driver" in doc_type_value or "nys" in doc_type_value):
                                doc_type = "nys_license"
                            elif ("vehicle" in doc_type_value or "title" in doc_type_value or "certificate" in doc_type_value):
                                doc_type = "vehicle_title"
                            elif ("uber" in doc_type_value or "affiliation" in doc_type_value):
                                doc_type = "uber_affiliation_letter"
                            elif ("radio" in doc_type_value or "base" in doc_type_value):
                                doc_type = "radio_base_cert"
                            
                            # Get document data
                            if "data" in doc and isinstance(doc["data"], dict):
                                doc_data = doc["data"]
                            else:
                                # If no data field, use all fields except type/document_type
                                doc_data = {k: v for k, v in doc.items() 
                                           if k not in ["document_type", "type", "doc_type"]}
                                
                            # Standardize address fields if they're not already nested
                            standardized_data = {}
                            
                            # Create address object if it doesn't exist but address fields do
                            if ("address" not in doc_data or not isinstance(doc_data["address"], dict)) and \
                               any(k in ["address", "street", "city", "state", "zip", "zip_code"] for k in doc_data):
                                # Create a nested address structure
                                standardized_data["address"] = {}
                                
                                # Map address fields
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
                                        # Remove the original field to avoid duplication
                                        if src_field != "address":  # Keep address for backward compatibility
                                            doc_data.pop(src_field, None)
                            
                            # Add all remaining fields
                            for key, value in doc_data.items():
                                standardized_data[key] = value
                                
                            standardized_documents.append({
                                "document_type": doc_type,
                                "data": standardized_data
                            })
                    
                    # Structure 2: Top-level document types as keys
                    else:
                        for doc_type, content in results.items():
                            # Skip non-dictionary, non-list values or keys that look like metadata
                            if (not isinstance(content, (dict, list))) or doc_type.startswith("_"):
                                continue
                                
                            # Format document type for display
                            display_doc_type = doc_type.replace("_", " ").title()
                            
                            # Handle content
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
                    
                    # Process the standardized documents
                    with st.expander("View Standardized Data Structure", expanded=False):
                        st.json({"documents": standardized_documents})
                        
                    for doc in standardized_documents:
                        doc_type = doc["document_type"]
                        doc_data = doc["data"]
                        
                        for field_name, field_value in doc_data.items():
                            if isinstance(field_value, dict):
                                # Process nested fields (like address)
                                for nested_key, nested_value in field_value.items():
                                    label = f"{doc_type.title()} - {field_name.title()} {nested_key.title()}"
                                    flat_data[label] = nested_value
                            else:
                                # Process direct fields
                                label = f"{doc_type.title()} - {field_name.title()}"
                                flat_data[label] = field_value
                except Exception as e:
                    st.error(f"Error processing JSON data: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc(), language="python")
                
                # Create DataFrame for editing
                if flat_data:
                    # Group fields by document type for better organization
                    grouped_data = {}
                    for key, value in flat_data.items():
                        doc_type, field_name = key.split(' - ', 1)
                        if doc_type not in grouped_data:
                            grouped_data[doc_type] = {}
                        grouped_data[doc_type][field_name] = value
                    
                    # Track all edited values
                    edited_values = {}
                    
                    # Display each document type in its own section
                    for doc_type, fields in grouped_data.items():
                        with st.expander(f"📄 {doc_type} Information", expanded=True):
                            # Group fields by parent (e.g., group address fields together)
                            field_groups = {}
                            for field_name, field_value in fields.items():
                                # Check if this is a nested field (like "Address Street")
                                parts = field_name.split(' ', 1)
                                if len(parts) > 1 and parts[0] in ['Address', 'Owner']:
                                    parent = parts[0]
                                    if parent not in field_groups:
                                        field_groups[parent] = {}
                                    field_groups[parent][parts[1]] = field_value
                                else:
                                    # Regular field
                                    if 'Other' not in field_groups:
                                        field_groups['Other'] = {}
                                    field_groups['Other'][field_name] = field_value
                            
                            # Process each field group
                            for group_name, group_fields in field_groups.items():
                                if group_name != 'Other':
                                    # Display group header
                                    st.subheader(f"{group_name}")
                                
                                # For address and other nested structures, use individual fields
                                if group_name in ['Address', 'Owner']:
                                    # Create columns for better layout
                                    cols = st.columns(2)
                                    col_idx = 0
                                    
                                    for field_name, field_value in group_fields.items():
                                        # Use text inputs for better layout control
                                        edited_field = cols[col_idx].text_input(
                                            field_name,
                                            value=field_value,
                                            key=f"{doc_type}_{group_name}_{field_name}"
                                        )
                                        # Store the edited value
                                        full_key = f"{doc_type} - {group_name} {field_name}"
                                        edited_values[full_key] = edited_field
                                        
                                        # Alternate columns
                                        col_idx = (col_idx + 1) % 2
                                else:
                                    # Display all fields vertically but use columns for better space utilization
                                    cols = st.columns(2)
                                    col_idx = 0
                                    
                                    # Sort fields alphabetically for consistency
                                    for field_name, field_value in sorted(group_fields.items()):
                                        # Use text inputs in columns
                                        edited_field = cols[col_idx].text_input(
                                            field_name,
                                            value=field_value,
                                            key=f"{doc_type}_Other_{field_name}"
                                        )
                                        # Store the edited value
                                        full_key = f"{doc_type} - {field_name}"
                                        edited_values[full_key] = edited_field
                                        
                                        # Alternate columns
                                        col_idx = (col_idx + 1) % 2
                    
                    # Create a centered, more visible submit button
                    st.write("")  # Add some spacing
                    col1, col2, col3 = st.columns([1, 2, 1])
                    with col2:
                        submit_button = st.button("📤 Submit Application", type="primary", use_container_width=True)
                    
                    if submit_button:
                        with st.spinner("Processing your submission..."):
                            # Add a small delay for visual feedback
                            import time
                            time.sleep(0.5)
                            
                            # Convert to final data format
                            final_data = edited_values
                            
                            # Add the user input data to the final data
                            final_data.update(st.session_state.user_input)
                            
                            # Reorganize data back into document types
                            organized_data = {}
                            
                            # Add contact and additional info as a separate section
                            contact_data = {
                                "document_type": "Contact Information",
                                "data": {
                                    "email": st.session_state.user_input["Contact - Email"],
                                    "phone": st.session_state.user_input["Contact - Phone"]
                                }
                            }
                            
                            additional_data = {
                                "document_type": "Additional Information",
                                "data": {
                                    "vehicle_owned_by_self": st.session_state.user_input["Additional - Vehicle Owned By Self/Spouse"],
                                    "has_named_drivers": st.session_state.user_input["Additional - Has Named Drivers"],
                                    "has_workers_compensation": st.session_state.user_input["Additional - Has Workers Compensation"],
                                    "obtains_fares_via_radio_base": st.session_state.user_input["Additional - Obtains Fares via Radio Base"]
                                }
                            }
                            
                            # Remember original data structure
                            original_structure = {}
                            
                            # Determine which document types used arrays in the original data
                            for doc_type, content in results.items():
                                if isinstance(content, list):
                                    original_structure[doc_type.lower().replace(" ", "_")] = "array"
                                elif isinstance(content, dict):
                                    original_structure[doc_type.lower().replace(" ", "_")] = "object"
                            
                            # Create a map to track document types and their fields
                            doc_fields = {}
                            
                            for key, value in final_data.items():
                                # Parse the readable key to determine document type and field
                                parts = key.split(' - ', 1)
                                if len(parts) == 2:
                                    doc_type = parts[0].lower().replace(' ', '_')
                                    field = parts[1].lower().replace(' ', '_')
                                    
                                    # Handle nested fields (e.g., "Address Street")
                                    field_parts = field.split('_')
                                    
                                    # Initialize document type if not exists
                                    if doc_type not in doc_fields:
                                        doc_fields[doc_type] = set()
                                    
                                    # Track this field
                                    if len(field_parts) > 1 and field_parts[0] in ['address', 'owner']:
                                        # This is a nested field
                                        parent_field = field_parts[0]
                                        child_field = '_'.join(field_parts[1:])
                                        doc_fields[doc_type].add(parent_field)
                                    else:
                                        doc_fields[doc_type].add(field)
                            
                            # Now build the organized data structure
                            for doc_type in doc_fields:
                                doc_data = {}
                                
                                # Process each field for this document type
                                for field in doc_fields[doc_type]:
                                    if field in ['address', 'owner']:
                                        # Create nested object
                                        doc_data[field] = {}
                                
                                # Fill in the values
                                for key, value in final_data.items():
                                    parts = key.split(' - ', 1)
                                    if len(parts) == 2:
                                        key_doc_type = parts[0].lower().replace(' ', '_')
                                        field = parts[1].lower().replace(' ', '_')
                                        
                                        if key_doc_type == doc_type:
                                            field_parts = field.split('_')
                                            
                                            if len(field_parts) > 1 and field_parts[0] in ['address', 'owner']:
                                                # This is a nested field
                                                parent_field = field_parts[0]
                                                child_field = '_'.join(field_parts[1:])
                                                doc_data[parent_field][child_field] = value
                                            else:
                                                doc_data[field] = value
                                
                                # Use the original structure format (array or direct object)
                                if doc_type in original_structure and original_structure[doc_type] == "array":
                                    organized_data[doc_type] = [doc_data]
                                else:
                                    organized_data[doc_type] = doc_data
                            
                            # Convert to documents array format if needed
                            if "documents" in results:
                                final_organized_data = {"documents": []}
                                # Add contact and additional info first
                                final_organized_data["documents"].append(contact_data)
                                final_organized_data["documents"].append(additional_data)
                                
                                # Add the rest of the documents
                                for doc_type, data in organized_data.items():
                                    if isinstance(data, list):
                                        # If it's already a list, handle each item
                                        for item in data:
                                            final_organized_data["documents"].append({
                                                "document_type": doc_type.replace('_', ' ').title(),
                                                "data": item
                                            })
                                    else:
                                        # It's a single object
                                        final_organized_data["documents"].append({
                                            "document_type": doc_type.replace('_', ' ').title(),
                                            "data": data
                                        })
                                organized_data = final_organized_data
                            else:
                                # If not using documents array format, add contact and additional info as top-level keys
                                organized_data["contact_information"] = contact_data["data"]
                                organized_data["additional_information"] = additional_data["data"]
                            
                            st.success("✅ Application submitted successfully!")
                            
                            # Show confirmed data in a clean format
                            st.subheader("Submitted Information")
                            
                            if "documents" in organized_data:
                                # Display in documents array format
                                for doc_index, doc in enumerate(organized_data["documents"]):
                                    with st.expander(f"{doc['document_type']} Information", expanded=True):
                                        # Organize fields by category
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
                                        
                                        # Use helper function for consistent display
                                        display_field_groups(doc['document_type'], address_fields, owner_fields, other_fields, doc_index)
                            else:
                                # Display in original format
                                for doc_type, content in organized_data.items():
                                    display_title = doc_type.replace('_', ' ').title()
                                    
                                    # Handle both array and direct object formats
                                    if isinstance(content, list):
                                        # Array format - display each item with an index
                                        for idx, item in enumerate(content):
                                            with st.expander(f"{display_title} #{idx+1}", expanded=True):
                                                if isinstance(item, dict):
                                                    # Group fields by category
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
                                                    
                                                    # Display each category
                                                    display_field_groups(display_title, address_fields, owner_fields, other_fields, idx)
                                    else:
                                        # Direct object format
                                        with st.expander(f"{display_title} Information", expanded=True):
                                            if isinstance(content, dict):
                                                # Group fields by category
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
                                                
                                                # Display each category
                                                display_field_groups(display_title, address_fields, owner_fields, other_fields)
