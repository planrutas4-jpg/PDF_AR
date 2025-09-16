import fitz
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import threading

class PDFPageReorderApp:
    MINIATURA_ANCHO = 120
    MINIATURA_ALTO = 160
    COLUMNAS = 5
    MARGEN = 5
    COLOR_SELECCIONADO = "blue"
    COLOR_NO_SELECCIONADO = "gray"
    BORDES = 3

    def __init__(self, root):
        self.root = root
        self.root.title("Reordenar Páginas PDF")
        self.root.geometry("800x600")
        self.doc = None
        self.orden_paginas = []
        self.miniaturas = []
        self.labels = []
        self.seleccion_index = None

        # Botones
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)
        for text, cmd in [("Cargar PDF", self.cargar_pdf_thread),
                          ("Guardar PDF", self.guardar_pdf_thread),
                          ("Subir Página", lambda: self.mover_pagina(True)),
                          ("Bajar Página", lambda: self.mover_pagina(False))]:
            tk.Button(btn_frame, text=text, command=cmd).pack(side="left", padx=5)

        # Canvas con scrollbar
        self.canvas = tk.Canvas(root)
        self.scroll_y = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.scroll_y.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.canvas.configure(yscrollcommand=self.scroll_y.set)

        self.frame = tk.Frame(self.canvas)
        self.canvas_frame = self.canvas.create_window((0,0), window=self.frame, anchor="nw")
        self.frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    # Ajustar scroll region
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    # Thread wrapper para cargar PDF
    def cargar_pdf_thread(self):
        threading.Thread(target=self.cargar_pdf).start()

    def guardar_pdf_thread(self):
        threading.Thread(target=self.guardar_pdf).start()

    def cargar_pdf(self):
        ruta = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not ruta:
            return
        self._mostrar_cargando("Cargando PDF...")
        doc = fitz.open(ruta)
        self.doc = doc
        self.orden_paginas = list(range(len(self.doc)))
        self.seleccion_index = None
        self.mostrar_miniaturas()
        self._cerrar_cargando()

    def guardar_pdf(self):
        if not self.doc:
            return
        ruta = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not ruta:
            return
        self._mostrar_cargando("Guardando PDF...")
        nuevo_doc = fitz.open()
        for idx in self.orden_paginas:
            nuevo_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
        nuevo_doc.save(ruta)
        self._cerrar_cargando()
        messagebox.showinfo("Guardado", "PDF guardado exitosamente.")

    # Ventana cargando
    def _mostrar_cargando(self, texto):
        self.loading_win = tk.Toplevel(self.root)
        self.loading_win.title(texto)
        self.loading_win.geometry("200x100")
        self.loading_win.transient(self.root)
        self.loading_win.grab_set()
        tk.Label(self.loading_win, text=texto).pack(expand=True)

    def _cerrar_cargando(self):
        if hasattr(self, "loading_win") and self.loading_win.winfo_exists():
            self.loading_win.destroy()

    # Miniaturas
    def mostrar_miniaturas(self):
        for lbl in self.labels:
            lbl.destroy()
        self.miniaturas.clear()
        self.labels.clear()

        for i, idx in enumerate(self.orden_paginas):
            page = self.doc[idx]
            scale_x = self.MINIATURA_ANCHO / page.rect.width
            scale_y = self.MINIATURA_ALTO / page.rect.height
            pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
            self.miniaturas.append(photo)

            border_width = self.BORDES if i == self.seleccion_index else 1
            highlight_color = self.COLOR_SELECCIONADO if i == self.seleccion_index else self.COLOR_NO_SELECCIONADO

            lbl = tk.Label(self.frame, image=photo, borderwidth=border_width,
                           relief="solid", highlightbackground=highlight_color,
                           highlightthickness=border_width)
            lbl.grid(row=i // self.COLUMNAS, column=i % self.COLUMNAS,
                     padx=self.MARGEN, pady=self.MARGEN)
            lbl.bind("<Button-1>", lambda e, index=i: self.seleccionar_pagina(index))
            self.labels.append(lbl)

    def seleccionar_pagina(self, index):
        self.seleccion_index = index
        self.mostrar_miniaturas()

    def mover_pagina(self, subir=True):
        if self.seleccion_index is None:
            messagebox.showinfo("Info", "Selecciona una página primero")
            return
        i = self.seleccion_index
        if subir and i == 0 or not subir and i == len(self.orden_paginas) - 1:
            return
        nueva_pos = i - 1 if subir else i + 1
        self.orden_paginas[i], self.orden_paginas[nueva_pos] = self.orden_paginas[nueva_pos], self.orden_paginas[i]
        self.seleccion_index = nueva_pos
        self.mostrar_miniaturas()

# if __name__ == "__main__":
#     root = tk.Tk()
#     app = PDFPageReorderApp(root)
#     root.mainloop()
