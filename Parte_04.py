# main_app.py
import tkinter as tk
from Parte_01 import PDFSelectorApp
from Parte_02 import PDFRotatorGridApp
from Parte_03 import PDFPageReorderApp

def abrir_pdf_selector():
    root.withdraw()
    ventana = tk.Toplevel(root)
    def al_cerrar():
        root.deiconify()
        ventana.destroy()
    ventana.protocol("WM_DELETE_WINDOW", al_cerrar)
    app = PDFSelectorApp(ventana)

def abrir_pdf_rotator():
    root.withdraw()
    ventana = tk.Toplevel(root)
    def al_cerrar():
        root.deiconify()
        ventana.destroy()
    ventana.protocol("WM_DELETE_WINDOW", al_cerrar)
    app = PDFRotatorGridApp(ventana)

def abrir_pdf_reorder():
    root.withdraw()
    ventana = tk.Toplevel(root)
    def al_cerrar():
        root.deiconify()
        ventana.destroy()
    ventana.protocol("WM_DELETE_WINDOW", al_cerrar)
    app = PDFPageReorderApp(ventana)

root = tk.Tk()
root.title("Ventana principal")
root.geometry("300x150")

btn1 = tk.Button(root, text="1", command=abrir_pdf_selector)
btn1.pack(pady=5)
btn2 = tk.Button(root, text="2", command=abrir_pdf_rotator)
btn2.pack(pady=5)
btn3 = tk.Button(root, text="3", command=abrir_pdf_reorder)
btn3.pack(pady=5)

root.mainloop()
