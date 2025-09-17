# main_app.py
import tkinter as tk
from Parte_01 import PDFSelectorApp
from Parte_02 import PDFRotatorGridApp
from Parte_03 import PDFPageReorderApp

def abrir_ventana(app_class):
    """Abre una nueva ventana para la app seleccionada y oculta la ventana principal."""
    root.withdraw()
    ventana = tk.Toplevel(root)
    
    def al_cerrar():
        root.deiconify()
        ventana.destroy()
    
    ventana.protocol("WM_DELETE_WINDOW", al_cerrar)
    app_class(ventana)

# Configuración de la ventana principal
root = tk.Tk()
root.title("PDF_Manager_AR_vr.0001")
root.geometry("350x125")
root.resizable(False, False)

# Centrar la ventana en la pantalla
root.update_idletasks()
x = (root.winfo_screenwidth() - root.winfo_width()) // 2
y = (root.winfo_screenheight() - root.winfo_height()) // 2
root.geometry(f"+{x}+{y}")

# Botones de la ventana principal
btn1 = tk.Button(root, text="Seleccionar PDF", width=20, command=lambda: abrir_ventana(PDFSelectorApp))
btn1.pack(pady=5)

btn2 = tk.Button(root, text="Rotar PDF", width=20, command=lambda: abrir_ventana(PDFRotatorGridApp))
btn2.pack(pady=5)

btn3 = tk.Button(root, text="Reordenar PDF", width=20, command=lambda: abrir_ventana(PDFPageReorderApp))
btn3.pack(pady=5)

# Iniciar la aplicación
root.mainloop()
