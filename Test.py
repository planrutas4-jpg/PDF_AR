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
        self.root.title("FlipPDF_AR_vr.0001")
        self.root.geometry("800x600")

        self.doc = None
        self.orden_paginas = []
        self.miniaturas = []
        self.labels = []
        self.seleccion_indices = set()  # Soporta selección múltiple
        self.last_selected_index = None  # Para Shift+Click

        # Botones
        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=5)
        for text, cmd in [("Cargar PDF", self.cargar_pdf_thread),
                          ("Guardar PDF", self.guardar_pdf_thread),
                          ("Subir Página", lambda: self.mover_pagina(True)),
                          ("Bajar Página", lambda: self.mover_pagina(False)),
                          ("Eliminar Página", self.eliminar_pagina)]:
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

    # Scroll region
    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

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

        self._mostrar_cargando("Cargando PDF...")
        doc = fitz.open(ruta)
        self.doc = doc
        self.orden_paginas = list(range(len(self.doc)))
        self.seleccion_indices.clear()
        self.miniaturas.clear()
        self.labels.clear()
        self.last_selected_index = None

        # Barra de progreso
        progress = ttk.Progressbar(self.loading_win, orient="horizontal", length=300, mode="determinate")
        progress.pack(pady=10)
        progress["maximum"] = len(self.doc)
        progress["value"] = 0
        self.loading_win.update()

        for i, idx in enumerate(self.orden_paginas):
            page = self.doc[idx]
            scale_x = self.MINIATURA_ANCHO / page.rect.width
            scale_y = self.MINIATURA_ALTO / page.rect.height
            pix = page.get_pixmap(matrix=fitz.Matrix(scale_x, scale_y))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            photo = ImageTk.PhotoImage(img)
            self.miniaturas.append(photo)

            # Crear miniatura
            self.root.after(0, self._agregar_miniatura, i, photo)

            progress["value"] = i + 1
            self.loading_win.update()

        self._cerrar_cargando()

    def _agregar_miniatura(self, i, photo):
        border_width = self.BORDES if i in self.seleccion_indices else 1
        highlight_color = self.COLOR_SELECCIONADO if i in self.seleccion_indices else self.COLOR_NO_SELECCIONADO

        lbl = tk.Label(self.frame, image=photo, borderwidth=border_width,
                       relief="solid", highlightbackground=highlight_color,
                       highlightthickness=border_width)
        lbl.grid(row=i // self.COLUMNAS, column=i % self.COLUMNAS,
                 padx=self.MARGEN, pady=self.MARGEN)
        lbl.bind("<Button-1>", lambda e, index=i: self.seleccionar_pagina(index, e))
        self.labels.append(lbl)

    # ---------- Guardar PDF ----------
    def guardar_pdf(self):
        if not self.doc:
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
        messagebox.showinfo("Guardado", "PDF guardado exitosamente.")

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

    # ---------- Miniaturas y selección ----------
    def mostrar_miniaturas(self):
        for i, lbl in enumerate(self.labels):
            lbl.grid_forget()

        for i, idx in enumerate(self.orden_paginas):
            lbl = self.labels[idx]
            border_width = self.BORDES if idx in self.seleccion_indices else 1
            highlight_color = self.COLOR_SELECCIONADO if idx in self.seleccion_indices else self.COLOR_NO_SELECCIONADO
            lbl.config(borderwidth=border_width, highlightbackground=highlight_color, highlightthickness=border_width)
            lbl.grid(row=i // self.COLUMNAS, column=i % self.COLUMNAS, padx=self.MARGEN, pady=self.MARGEN)

    def seleccionar_pagina(self, index, event=None):
        ctrl = event.state & 0x0004 if event else False
        shift = event.state & 0x0001 if event else False

        if shift and self.last_selected_index is not None:
            start = min(self.last_selected_index, index)
            end = max(self.last_selected_index, index)
            for i in range(start, end + 1):
                self.seleccion_indices.add(i)
        elif ctrl:
            if index in self.seleccion_indices:
                self.seleccion_indices.remove(index)
            else:
                self.seleccion_indices.add(index)
        else:
            self.seleccion_indices = {index}

        self.last_selected_index = index
        self.mostrar_miniaturas()

    # ---------- Mover páginas ----------
    def mover_pagina(self, subir=True):
        if not self.seleccion_indices:
            messagebox.showinfo("Info", "Selecciona al menos una página")
            return

        seleccion_sorted = sorted(self.seleccion_indices)

        if subir:
            while seleccion_sorted[0] > 0:
                for idx in seleccion_sorted:
                    i = self.orden_paginas.index(idx)
                    self.orden_paginas[i], self.orden_paginas[i-1] = self.orden_paginas[i-1], self.orden_paginas[i]
                seleccion_sorted = [i-1 for i in seleccion_sorted]
        else:
            while seleccion_sorted[-1] < len(self.orden_paginas)-1:
                for idx in reversed(seleccion_sorted):
                    i = self.orden_paginas.index(idx)
                    self.orden_paginas[i], self.orden_paginas[i+1] = self.orden_paginas[i+1], self.orden_paginas[i]
                seleccion_sorted = [i+1 for i in seleccion_sorted]

        self.mostrar_miniaturas()

    # ---------- Eliminar páginas ----------
    def eliminar_pagina(self):
        if not self.seleccion_indices:
            messagebox.showinfo("Info", "Selecciona al menos una página")
            return

        respuesta = messagebox.askyesno("Eliminar", "¿Deseas eliminar las páginas seleccionadas?")
        if not respuesta:
            return

        for idx in sorted(self.seleccion_indices, reverse=True):
            self.orden_paginas.remove(idx)

        self.seleccion_indices = set()
        self.last_selected_index = None
        self.mostrar_miniaturas()


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFPageReorderApp(root)
    root.mainloop()
