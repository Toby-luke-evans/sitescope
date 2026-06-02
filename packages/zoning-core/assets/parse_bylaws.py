import os
from unstructured.partition.pdf import partition_pdf
from unstructured.staging.base import elements_to_json
import pytesseract

# Point this to exactly where you installed Tesseract
pytesseract.pytesseract.tesseract_cmd = r'A:\Program Files\Tesseract\tesseract.exe'

# Path to your PDF (e.g., 'Chapter_10_Residential.pdf')
input_file = r"A:\AI\HB-YOU 2026\assets\97ec-City-Planning-Zoning-Zoning-By-law-Part-1.pdf"
output_file = r"A:\AI\HB-YOU 2026\assets\zoning_elements.json"

print(f"Starting extraction on {input_file}... this might take a few minutes.")

elements = partition_pdf(
    filename=input_file,
    # 'hi_res' is crucial for bylaws with tables and complex layouts
    strategy="hi_res", 
    # This specifically looks for table borders and cells
    infer_table_structure=True, 
    # Extracts the text within the tables as HTML for easy LLM reading
    extract_images_in_pdf=False,
)

# Save the messy output to JSON
elements_to_json(elements, filename=output_file)

print(f"Done! Check {output_file} for the raw structured data.")