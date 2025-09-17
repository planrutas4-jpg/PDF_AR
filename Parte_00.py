import os
from pypdf import PdfReader, PdfWriter

# Ruta del archivo PDF original
input_path = r"D:\Alex_User\Descargas\Documents\PDF_Practica\Trabajo.pdf"

# Carpeta de salida
output_folder = r"D:\Alex_User\Descargas\Documents\PDF_Practica\Paginas"
os.makedirs(output_folder, exist_ok=True)
# Leer el PDF
reader = PdfReader(input_path)
total_pages = len(reader.pages)
print(f"El PDF tiene {total_pages} páginas.")
    
    
def separar_pdf(start_page=1,end_page=total_pages,extraer_impar=False,un_archivo=True):
    # Definir rango de páginas a extraer
    # start_page = 6
    # end_page = 10
    # extraer_impar = True  # True = extraer cada otra página empezando desde la primera del rango
    # un_archivo = True      # True = guardar todas las páginas en un solo PDF

    # Validar rango
    if start_page < 1 or end_page > total_pages or start_page > end_page:
        raise ValueError("Rango de páginas inválido.")

    if un_archivo:
        # Crear un solo PdfWriter para todas las páginas seleccionadas
        writer = PdfWriter()

    # Recorrer el rango seleccionado
    for idx, page_num in enumerate(range(start_page, end_page + 1), start=1):
        if extraer_impar and idx % 2 == 0:
            continue  # saltar cada segunda página dentro del rango

        if un_archivo:
            # Agregar página al PDF único
            writer.add_page(reader.pages[page_num - 1])
        else:
            # Guardar cada página en un archivo separado
            writer_temp = PdfWriter()
            writer_temp.add_page(reader.pages[page_num - 1])
            output_file = os.path.join(output_folder, f"pagina_{page_num}.pdf")
            with open(output_file, "wb") as f:
                writer_temp.write(f)

    # Guardar todas las páginas en un solo PDF
    if un_archivo:
        output_file = os.path.join(output_folder, f"rango_{start_page}_a_{end_page}.pdf")
        with open(output_file, "wb") as f:
            writer.write(f)

    print(f"✅ Se extrajeron las páginas {start_page} a {end_page} en la carpeta: {output_folder}")


# Unir hojas deacuerdo a la hoja dada

import re
def unir_pdfs (carpeta):
    # Carpeta con los PDFs
    # Crear objeto PdfWriter
    writer = PdfWriter()

    # Listar todos los PDFs en la carpeta
    pdfs = [f for f in os.listdir(carpeta) if f.lower().endswith(".pdf")]

    # Función para extraer el número del nombre del archivo
    def extraer_numero(nombre):
        match = re.search(r'(\d+)', nombre)
        return int(match.group(1)) if match else float('inf')  # Archivos sin número van al final

    # Ordenar los PDFs según el número en el nombre
    pdfs.sort(key=extraer_numero)

    # Leer cada PDF y agregar todas sus páginas
    for pdf in pdfs:
        ruta_pdf = os.path.join(carpeta, pdf)
        reader = PdfReader(ruta_pdf)
        for page in reader.pages:
            writer.add_page(page)

    # Guardar PDF final
    ruta_salida = os.path.join(carpeta, "PDF_Unido.pdf")
    with open(ruta_salida, "wb") as f:
        writer.write(f)

    print(f"Todos los PDFs se han unido en: {ruta_salida}")



