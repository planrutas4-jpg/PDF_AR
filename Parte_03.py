import fitz
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
import threading

class PDFPageReorderApp:
    MINIATURA_ANCHO = 120
    MINIATURA_ALTO = 160
    COLUMNAS = 6
    MARGEN = 5
    COLOR_SELECCIONADO = "blue"
    COLOR_NO_SELECCIONADO = "gray"
    BORDES = 3

    def __init__(self, root):
        self.root = root
        self.root.title("FlipPDF_AR_vr.0001")
        self.root.geometry("800x650")

        self.doc = None
        self.orden_paginas = []
        self.miniaturas = []
        self.labels = []
        self.grid_map = {}  # Label -> índice real de página
        self.seleccion_index = None

        # Barra de estado
        self.status_var = tk.StringVar()
        self.status_var.set("Cargue un PDF para habilitar acciones")
        self.status_bar = tk.Label(root, textvariable=self.status_var, bd=1, relief="sunken", anchor="w")
        self.status_bar.pack(side="bottom", fill="x")

        # Botones
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)

        self.btn_cargar = tk.Button(btn_frame, text="Cargar PDF", command=self.cargar_pdf_thread)
        self.btn_cargar.pack(side="left", padx=5)

        self.btn_guardar = tk.Button(btn_frame, text="Guardar PDF", command=self.guardar_pdf_thread, state="disabled")
        self.btn_guardar.pack(side="left", padx=5)

        self.btn_subir = tk.Button(btn_frame, text="Subir Página", command=lambda: self.mover_pagina(True), state="disabled")
        self.btn_subir.pack(side="left", padx=5)

        self.btn_bajar = tk.Button(btn_frame, text="Bajar Página", command=lambda: self.mover_pagina(False), state="disabled")
        self.btn_bajar.pack(side="left", padx=5)

        self.btn_eliminar = tk.Button(btn_frame, text="Eliminar Página", command=self.eliminar_pagina, state="disabled")
        self.btn_eliminar.pack(side="left", padx=5)

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

        # Scroll con rueda del mouse
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)  # Windows
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)    # Linux scroll arriba
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)    # Linux scroll abajo

    # Scroll region
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def _on_mousewheel(self, event):
        if event.num == 5 or event.delta < 0:
            self.canvas.yview_scroll(1, "units")
        elif event.num == 4 or event.delta > 0:
            self.canvas.yview_scroll(-1, "units")

    # Thread wrappers
    def cargar_pdf_thread(self):
        threading.Thread(target=self.cargar_pdf, daemon=True).start()

    def guardar_pdf_thread(self):
        threading.Thread(target=self.guardar_pdf, daemon=True).start()

    # ---------- Cargar PDF ----------
    def cargar_pdf(self):
        ruta = filedialog.askopenfilename(filetypes=[("PDF Files", "*.pdf")])
        if not ruta:
            return

        self._mostrar_cargando("Cargando páginas, por favor espere...")
        doc = fitz.open(ruta)
        self.doc = doc
        self.orden_paginas = list(range(len(self.doc)))
        self.seleccion_index = None
        self.miniaturas.clear()
        self.labels.clear()
        for widget in self.frame.winfo_children():
            widget.destroy()

        # Habilitar botones necesarios
        self.btn_guardar.config(state="normal")
        self.btn_subir.config(state="disabled")
        self.btn_bajar.config(state="disabled")
        self.btn_eliminar.config(state="disabled")

        progress = ttk.Progressbar(self.loading_win, orient="horizontal", length=300, mode="determinate")
        progress.pack(pady=10)
        progress["maximum"] = len(self.doc)
        progress["value"] = 0
        self.loading_win.update()

        for i, idx in enumerate(self.orden_paginas):
            page = self.doc[idx]
            scale = min(self.MINIATURA_ANCHO / page.rect.width, self.MINIATURA_ALTO / page.rect.height)
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
            self.miniaturas.append(photo)
            self.root.after(0, self._agregar_miniatura, idx, photo)
            progress["value"] = i + 1
            self.loading_win.update()

        self._cerrar_cargando()
        self._update_status("PDF cargado correctamente", 5)

    def _agregar_miniatura(self, page_idx, photo):
        lbl = tk.Label(self.frame, image=photo, borderwidth=1,
                       relief="solid", highlightbackground=self.COLOR_NO_SELECCIONADO,
                       highlightthickness=1)
        lbl.grid(row=page_idx // self.COLUMNAS, column=page_idx % self.COLUMNAS,
                 padx=self.MARGEN, pady=self.MARGEN)
        lbl.bind("<Button-1>", lambda e, l=lbl: self.seleccionar_pagina(l))
        self.labels.append(lbl)
        self.mostrar_miniaturas()

    # ---------- Guardar PDF ----------
    def guardar_pdf(self):
        if not self.doc or not self.orden_paginas:
            self._update_status("No hay PDF cargado o páginas para guardar", 5)
            return
        ruta = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not ruta:
            return

        self._mostrar_cargando("Guardando PDF...")
        progress = ttk.Progressbar(self.loading_win, orient="horizontal", length=300, mode="determinate")
        progress.pack(pady=10)
        progress["maximum"] = len(self.orden_paginas)
        progress["value"] = 0
        self.loading_win.update()

        nuevo_doc = fitz.open()
        for i, idx in enumerate(self.orden_paginas):
            nuevo_doc.insert_pdf(self.doc, from_page=idx, to_page=idx)
            progress["value"] = i + 1
            self.loading_win.update()

        nuevo_doc.save(ruta)
        self._cerrar_cargando()
        self._update_status("PDF guardado exitosamente", 5)

    # ---------- Ventana de carga ----------
    def _mostrar_cargando(self, texto):
        self.loading_win = tk.Toplevel(self.root)
        self.loading_win.title(texto)
        self.loading_win.geometry("350x100")
        self.loading_win.transient(self.root)
        self.loading_win.grab_set()
        tk.Label(self.loading_win, text=texto).pack(expand=True)

    def _cerrar_cargando(self):
        if hasattr(self, "loading_win") and self.loading_win.winfo_exists():
            self.loading_win.destroy()

    # ---------- Miniaturas ----------
    def mostrar_miniaturas(self):
        self.grid_map.clear()
        for widget in self.frame.winfo_children():
            widget.grid_forget()

        for pos, page_idx in enumerate(self.orden_paginas):
            lbl = self.labels[page_idx]
            self.grid_map[lbl] = page_idx
            if page_idx == self.seleccion_index:
                lbl.config(borderwidth=self.BORDES, highlightbackground=self.COLOR_SELECCIONADO,
                           highlightthickness=self.BORDES)
            else:
                lbl.config(borderwidth=1, highlightbackground=self.COLOR_NO_SELECCIONADO, highlightthickness=1)
            lbl.grid(row=pos // self.COLUMNAS, column=pos % self.COLUMNAS, padx=self.MARGEN, pady=self.MARGEN)

    def seleccionar_pagina(self, label):
        self.seleccion_index = self.grid_map[label]
        self.mostrar_miniaturas()
        self.actualizar_botones_navegacion()

    # ---------- Mover páginas ----------
    def mover_pagina(self, subir=True):
        if self.seleccion_index is None:
            self._update_status("Selecciona una página primero", 5)
            return

        i = self.orden_paginas.index(self.seleccion_index)
        if subir and i == 0 or not subir and i == len(self.orden_paginas) - 1:
            return
        nueva_pos = i - 1 if subir else i + 1
        self.orden_paginas[i], self.orden_paginas[nueva_pos] = self.orden_paginas[nueva_pos], self.orden_paginas[i]
        self.mostrar_miniaturas()
        self.actualizar_botones_navegacion()

    # ---------- Eliminar página ----------
    def eliminar_pagina(self):
        if self.seleccion_index is None:
            self._update_status("Selecciona una página para eliminar", 5)
            return
        if len(self.orden_paginas) == 0:
            self._update_status("No hay páginas para eliminar", 5)
            return

        idx = self.orden_paginas.index(self.seleccion_index)
        eliminado = self.orden_paginas.pop(idx)
        self.seleccion_index = None
        self.mostrar_miniaturas()
        self._update_status(f"Página {eliminado + 1} eliminada", 5)
        self.actualizar_botones_navegacion()

    # ---------- Actualizar botones subir/bajar/eliminar ----------
    def actualizar_botones_navegacion(self):
        if self.seleccion_index is None or len(self.orden_paginas) == 0:
            self.btn_subir.config(state="disabled")
            self.btn_bajar.config(state="disabled")
            self.btn_eliminar.config(state="disabled")
            return

        i = self.orden_paginas.index(self.seleccion_index)
        # Botones subir/bajar
        self.btn_subir.config(state="normal" if i > 0 else "disabled")
        self.btn_bajar.config(state="normal" if i < len(self.orden_paginas) - 1 else "disabled")
        # Botón eliminar
        self.btn_eliminar.config(state="normal")

    # ---------- Barra de estado ----------
    def _update_status(self, mensaje, segundos=5):
        self.status_var.set(mensaje)
        self.root.after(segundos*1000, lambda: self.status_var.set(""))

# if __name__ == "__main__":
#     root = tk.Tk()
#     app = PDFPageReorderApp(root)
#     root.mainloop()
