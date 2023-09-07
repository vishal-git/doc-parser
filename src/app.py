from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from dotenv import load_dotenv
from pytesseract import image_to_string
from PIL import Image
from io import BytesIO
import pypdfium2 as pdfium
import streamlit as st
import multiprocessing
from tempfile import NamedTemporaryFile
import pandas as pd
import json
import requests

load_dotenv("./")


def convert_pdf_to_images(file_path, scale=300 / 72):
    """Converts PDF file into images via pypdfium2"""
    pdf_file = pdfium.PdfDocument(file_path)

    page_indices = [i for i in range(len(pdf_file))]

    renderer = pdf_file.render(
        pdfium.PdfBitmap.to_pil,
        page_indices=page_indices,
        scale=scale,
    )

    final_images = []

    for i, image in zip(page_indices, renderer):
        image_byte_array = BytesIO()
        image.save(image_byte_array, format="jpeg", optimize=True)
        image_byte_array = image_byte_array.getvalue()
        final_images.append(dict({i: image_byte_array}))

    return final_images


def extract_text_from_images(list_dict_final_images):
    """Extracts text from images via pytesseract"""

    image_list = [list(data.values())[0] for data in list_dict_final_images]
    image_content = []

    for i, image_bytes in enumerate(image_list):
        image = Image.open(BytesIO(image_bytes))
        raw_text = str(image_to_string(image))
        image_content.append(raw_text)

    return "\n".join(image_content)


def extract_content_from_url(url: str):
    images_list = convert_pdf_to_images(url)
    text_with_pytesseract = extract_text_from_images(images_list)
    return text_with_pytesseract


def extract_structured_data(content: str, data_elements):
    llm = ChatOpenAI(temperature=0, model="gpt-3.5-turbo-0613")
    template = """
    You are an expert data entry person who can extract useful information from documents.

    {content}
    
    From the content provided above, please try to extract all available data points from this list: {data_elements}

    Convert the extracted data points in a JSON array format and return only the JSON array.
    """

    prompt = PromptTemplate(
        input_variables=["content", "data_elements"],
        template=template,
    )

    chain = LLMChain(llm=llm, prompt=prompt)

    results = chain.run(content=content, data_elements=data_elements)

    return results


def main():

    default_data_elements = """{
    'DATE': 'The date when the invoice was issued',
    'ITEM': 'The purchased item listed in the invoice',
    'AMOUNT': 'The invoice amount',
    'VENDOR': 'The name of the company that issued the invoice',
    }"""

    st.set_page_config(page_title="Document Detail Extractor", page_icon=":receipt:")
    st.header("Extract Details from Documents :receipt:")

    data_points = st.text_area("Data Elements", value=default_data_elements, height=160)

    uploaded_files = st.file_uploader("Upload PDFs:", accept_multiple_files=True)

    if uploaded_files is not None and data_points is not None:
        results = []
        for file in uploaded_files:
            with NamedTemporaryFile(dir=".", suffix=".csv") as f:
                f.write(file.getbuffer())
                content = extract_content_from_url(f.name)
                data = extract_structured_data(content, default_data_elements)
                json_data = json.loads(data)
                if isinstance(json_data, list):
                    results.extend(json_data)
                else:
                    results.append(json_data)

        if len(results) > 0:
            try:
                df = pd.DataFrame(results)
                st.subheader("Results")
                st.data_editor(df)

                csv = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    "Click to download",
                    csv,
                    "receipts_data.csv",
                    "text/csv",
                    key="download-csv",
                )
            except Exception as e:
                st.error(f"An error has occurred while creating the dataframe {e}")
                st.write(results)  # print


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
