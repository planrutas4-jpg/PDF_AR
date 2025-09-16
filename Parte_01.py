import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import io
import os
import threading
from Proyecto_Tv_AE.Proyecto_PDF import unir_pdfs  # Función externa para unir PDFs

class PDFSelectorApp:
    MINIATURA_ANCHO = 140
    MINIATURA_ALTO = 190
    COLUMNAS = 5
    MARGEN = 5
    COLOR_SELECCIONADO = "blue"
    COLOR_NO_SELECCIONADO = "gray"

    def __init__(self, root):
        self.root = root
        self.root.title("AR_PDF-Nova_vr.0001")
        self.root.geometry("900x650")

        # Variables PDF
        self.doc = None
        self.num_paginas = 0
        self.seleccionadas = []
        self.labels = []
        self.labels_num = []
        self.imagenes_tk = []

        # Ruta de guardado inicial vacía
        self.ruta_nuevo_pdf = ""

        # Variables selección
        self.last_clicked_index = None
        self.dragging = False
        self.indices_visitados = set()

        # ON/OFF
        self.modo_separado = tk.BooleanVar(value=False)

        # Hilo para carga de miniaturas
        self.cargando_thread = None

        self._crear_interface()
        self._crear_preview_inicial()

    # ------------------------- UI -------------------------
    def _crear_interface(self):
        self.main_frame = tk.Frame(self.root)
        self.main_frame.pack(fill="both", expand=True)

        # ---------- Fila 1 ----------
        self.top_frame1 = tk.Frame(self.main_frame)
        self.top_frame1.pack(fill="x", pady=5, padx=5)

        tk.Button(self.top_frame1, text="Abrir PDF", command=self.seleccionar_archivo_pdf).pack(side="left", padx=5)

        self.menubutton = tk.Menubutton(self.top_frame1, text="Selección...", relief="raised")
        self.menu = tk.Menu(self.menubutton, tearoff=0)
        self.menu.add_command(label="Seleccionar/Deseleccionar (Todas)", command=self.toggle_todas_paginas)
        self.menu.add_command(label="Seleccionar pares", command=lambda: self.seleccionar_por_paridad(par=True))
        self.menu.add_command(label="Seleccionar impares", command=lambda: self.seleccionar_por_paridad(par=False))
        self.menubutton.config(menu=self.menu)
        self.menubutton.pack(side="left", padx=5)

        self.contador_label = tk.Label(self.top_frame1, text="Pág. seleccionadas: 0", font=("Arial", 12))
        self.contador_label.pack(side="left", padx=10)

        # Botones deshabilitados al inicio
        self.btn_guardar_en = tk.Button(self.top_frame1, text="Guardar en…", command=self.seleccionar_ruta_guardado, state="disabled")
        self.btn_guardar_en.pack(side="right", padx=5)
        self.btn_guardar_pdf = tk.Button(self.top_frame1, text="Guardar como PDF", command=self.guardar_pdf, state="disabled")
        self.btn_guardar_pdf.pack(side="right", padx=5)

        # ---------- Fila 2 ----------
        self.top_frame2 = tk.Frame(self.main_frame)
        self.top_frame2.pack(fill="x", pady=5, padx=5)

        self.btn_onoff = tk.Checkbutton(self.top_frame2, variable=self.modo_separado, command=self._actualizar_texto_onoff)
        self.btn_onoff.pack(side="left", padx=5)
        self._actualizar_texto_onoff()

        tk.Button(self.top_frame2, text="Unir PDFs de carpeta", command=self.unir_pdfs_carpeta).pack(side="left", padx=5)

        # ---------- Canvas y Scrollbar ----------
        self.canvas = tk.Canvas(self.main_frame)
        self.scroll_y = tk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.frame = tk.Frame(self.canvas)
        self.canvas.create_window((0,0), window=self.frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)
        self.canvas.pack(fill="both", expand=True, side="left")
        self.scroll_y.pack(fill="y", side="right")
        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    # ------------------------- Ventana de progreso -------------------------
    def _crear_ventana_progreso(self, texto="Procesando...", max_val=100):
        self.progreso_win = tk.Toplevel(self.root)
        self.progreso_win.title("Progreso")
        self.progreso_win.geometry("400x80")
        self.progreso_win.resizable(False, False)
        self.progreso_win.transient(self.root)
        self.progreso_win.grab_set()  # Bloquea la ventana principal

        tk.Label(self.progreso_win, text=texto, font=("Arial", 12)).pack(pady=5)
        self.progress = ttk.Progressbar(self.progreso_win, orient="horizontal", length=350, mode="determinate")
        self.progress.pack(pady=5)
        self.progress["maximum"] = max_val
        self.progress["value"] = 0

    # ------------------------- Reset PDF -------------------------
    def resetear_pdf(self):
        if self.doc:
            self.doc.close()
        self.doc = None
        self.num_paginas = 0
        self.seleccionadas.clear()
        self.labels.clear()
        self.labels_num.clear()
        self.imagenes_tk.clear()
        self.last_clicked_index = None
        self.dragging = False
        self.indices_visitados.clear()
        for widget in self.frame.winfo_children():
            widget.destroy()
        tk.Label(self.frame, text="No hay PDF cargado.", font=("Arial", 14)).pack(pady=20)
        self.actualizar_ui()

        # Deshabilitar botones
        self.btn_guardar_en.config(state="disabled")
        self.btn_guardar_pdf.config(state="disabled")

    # ------------------------- PDF -------------------------
    def cargar_pdf(self, ruta):
        try:
            self.resetear_pdf()
            lbl_cargando = tk.Label(self.frame, text="Cargando PDF…", font=("Arial", 16))
            lbl_cargando.pack(pady=20)
            self.root.update()

            self.doc = fitz.open(ruta)
            self.num_paginas = self.doc.page_count
            self.seleccionadas = [False] * self.num_paginas

            # ------------------- NUEVO: Definir ruta por defecto -------------------
            carpeta_pdf = os.path.dirname(ruta)  # Carpeta donde está el PDF
            carpeta_padre = os.path.dirname(carpeta_pdf)  # Subir un nivel
            carpeta_salida = os.path.join(carpeta_padre, "AR_PDF-NOVA")
            os.makedirs(carpeta_salida, exist_ok=True)
            self.ruta_nuevo_pdf = os.path.join(carpeta_salida, "PDF_todo.pdf")
            # ---------------------------------------------------------------------

            lbl_cargando.destroy()
            self.crear_preview_hilo()

            # Habilitar botones al cargar PDF
            self.btn_guardar_en.config(state="normal")
            self.btn_guardar_pdf.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el PDF:\n{e}")

    # ------------------------- Guardar PDF -------------------------
    def guardar_pdf(self):
        if not self.doc:
            messagebox.showwarning("Aviso", "No hay PDF cargado...")
            return

        if sum(self.seleccionadas) == 0:
            messagebox.showwarning("Aviso", "No hay páginas seleccionadas para guardar.")
            return

        if not self.ruta_nuevo_pdf or not os.path.isdir(os.path.dirname(self.ruta_nuevo_pdf)):
            self.seleccionar_ruta_guardado()
        try:
            if self.modo_separado.get():
                self._guardar_pdf_individual_hilo()
            else:
                self._guardar_pdf_unico_hilo()
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar el PDF:\n{e}")

    # ------------------------- Guardar PDF en hilo -------------------------
    def _guardar_pdf_unico_hilo(self):
        threading.Thread(target=self._guardar_pdf_unico_thread, daemon=True).start()

    def _guardar_pdf_unico_thread(self):
        writer = fitz.open()
        paginas_a_guardar = sum(self.seleccionadas)
        self._crear_ventana_progreso(texto="Guardando PDF único...", max_val=paginas_a_guardar)

        for i, sel in enumerate(self.seleccionadas):
            if sel:
                writer.insert_pdf(self.doc, from_page=i, to_page=i)
                self.root.after(0, lambda: self.progress.step(1))

        writer.save(self.ruta_nuevo_pdf)
        writer.close()
        self.root.after(0, lambda: self.progreso_win.destroy())

        carpeta = os.path.dirname(self.ruta_nuevo_pdf)
        os.startfile(carpeta)  # Abrir carpeta automáticamente
        messagebox.showinfo("Listo", f"PDF guardado en:\n{self.ruta_nuevo_pdf}")

    def _guardar_pdf_individual_hilo(self):
        threading.Thread(target=self._guardar_pdf_individual_thread, daemon=True).start()

    def _guardar_pdf_individual_thread(self):
        carpeta = os.path.dirname(self.ruta_nuevo_pdf)
        base = os.path.splitext(os.path.basename(self.ruta_nuevo_pdf))[0]
        paginas_a_guardar = sum(self.seleccionadas)
        self._crear_ventana_progreso(texto="Guardando PDFs individuales...", max_val=paginas_a_guardar)

        for i, sel in enumerate(self.seleccionadas):
            if sel:
                writer = fitz.open()
                writer.insert_pdf(self.doc, from_page=i, to_page=i)
                ruta_individual = os.path.join(carpeta, f"{base}_Pag{i+1}.pdf")
                writer.save(ruta_individual)
                writer.close()
                self.root.after(0, lambda: self.progress.step(1))

        self.root.after(0, lambda: self.progreso_win.destroy())
        os.startfile(carpeta)  # Abrir carpeta automáticamente
        messagebox.showinfo("Listo", f"PDFs individuales guardados en:\n{carpeta}")

    # ------------------------- Preview con multithread -------------------------
    def crear_preview_hilo(self):
        if not self.doc:
            return
        self._crear_ventana_progreso(texto="Cargando miniaturas...", max_val=self.num_paginas)
        threading.Thread(target=self._crear_preview_thread, daemon=True).start()

    def _crear_preview_thread(self):
        self.labels.clear()
        self.labels_num.clear()
        self.imagenes_tk.clear()
        for widget in self.frame.winfo_children():
            widget.destroy()

        for i in range(self.num_paginas):
            pagina = self.doc[i]
            pix = pagina.get_pixmap(matrix=fitz.Matrix(2,2))
            img = Image.open(io.BytesIO(pix.tobytes("png"))).resize(
                (self.MINIATURA_ANCHO, self.MINIATURA_ALTO)
            )
            img_tk = ImageTk.PhotoImage(img)
            self.imagenes_tk.append(img_tk)
            self.root.after(0, self._crear_miniatura_ui, i, img_tk)
            self.root.after(0, lambda: self.progress.step(1))

        self.root.after(0, self._finalizar_carga_preview)

    def _crear_miniatura_ui(self, i, img_tk):
        contenedor = tk.Frame(self.frame)
        contenedor.grid(row=i//self.COLUMNAS, column=i%self.COLUMNAS, padx=self.MARGEN, pady=self.MARGEN)

        lbl_img = tk.Label(contenedor, image=img_tk, borderwidth=2, relief="solid")
        lbl_img.pack()
        lbl_img.bind("<Button-1>", lambda e, idx=i: self.seleccion_click(idx, e))
        lbl_img.bind("<B1-Motion>", lambda e, idx=i: self.arrastre_toggle(idx))
        lbl_img.bind("<ButtonRelease-1>", lambda e: self.terminar_drag())
        self.labels.append(lbl_img)

        lbl_num = tk.Label(contenedor, text=f"Pág. {i+1}", font=("Arial", 10))
        lbl_num.pack(pady=2)
        self.labels_num.append(lbl_num)

    def _finalizar_carga_preview(self):
        if hasattr(self, "progreso_win") and self.progreso_win:
            self.progreso_win.destroy()
        self.actualizar_ui()

    # ------------------------- Selección -------------------------
    def seleccion_click(self, index, event):
        shift = (event.state & 0x0001) != 0
        ctrl = (event.state & 0x0004) != 0
        self.dragging = True
        self.indices_visitados = set()

        if shift and self.last_clicked_index is not None:
            for i in range(min(self.last_clicked_index, index), max(self.last_clicked_index, index)+1):
                self.seleccionadas[i] = True
        elif ctrl:
            self.seleccionadas[index] = not self.seleccionadas[index]
        else:
            self.seleccionadas = [False]*self.num_paginas
            self.seleccionadas[index] = True

        self.last_clicked_index = index
        self.indices_visitados.add(index)
        self.actualizar_ui()

    def arrastre_toggle(self, index):
        if self.dragging and index not in self.indices_visitados:
            self.seleccionadas[index] = not self.seleccionadas[index]
            self.indices_visitados.add(index)
            self.actualizar_ui()

    def terminar_drag(self):
        self.dragging = False
        self.indices_visitados.clear()

    # ------------------------- Menú selección -------------------------
    def toggle_todas_paginas(self):
        estado = not all(self.seleccionadas)
        self.seleccionadas = [estado]*self.num_paginas
        self.actualizar_ui()

    def seleccionar_por_paridad(self, par=True):
        self.seleccionadas = [(i%2==0) if par else (i%2!=0) for i in range(self.num_paginas)]
        self.actualizar_ui()

    # ------------------------- UI helper -------------------------
    def actualizar_ui(self):
        for i, lbl in enumerate(self.labels):
            seleccionado = self.seleccionadas[i]
            color = self.COLOR_SELECCIONADO if seleccionado else self.COLOR_NO_SELECCIONADO
            lbl.config(borderwidth=4 if seleccionado else 2, relief="solid",
                       highlightbackground=color, highlightcolor=color)
            self.labels_num[i].config(fg=color if seleccionado else "black")
        self.contador_label.config(text=f"Pág. seleccionadas: {sum(self.seleccionadas)}")

    def seleccionar_archivo_pdf(self):
        ruta = filedialog.askopenfilename(title="Seleccionar archivo PDF", filetypes=[("PDF Files", "*.pdf")])
        if ruta:
            self.cargar_pdf(ruta)

    def seleccionar_ruta_guardado(self):
        nombre_defecto = os.path.basename(self.ruta_nuevo_pdf) if self.ruta_nuevo_pdf else "PDF_Separado.pdf"
        ruta = filedialog.asksaveasfilename(
            title="Guardar como PDF",
            initialfile=nombre_defecto,
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if ruta:
            self.ruta_nuevo_pdf = ruta

    def _crear_preview_inicial(self):
        tk.Label(self.frame, text="No hay PDF cargado.", font=("Arial", 14)).pack(pady=20)

    def _actualizar_texto_onoff(self):
        self.btn_onoff.config(text="Hojas separadas (ON)" if self.modo_separado.get() else "Todo en un PDF (ON)")

    # ------------------------- Botón unir PDFs -------------------------
    def unir_pdfs_carpeta(self):
        carpeta = filedialog.askdirectory(title="Seleccionar carpeta con PDFs")
        if carpeta:
            try:
                unir_pdfs(carpeta=carpeta)
                messagebox.showinfo("Éxito", f"Se unieron los PDFs de la carpeta:\n{carpeta}")
            except Exception as e:
                messagebox.showerror("Error", f"No se pudieron unir los PDFs:\n{e}")

# # ------------------------- Inicializar -------------------------
# if __name__ == "__main__":
#     root = tk.Tk()
#     app = PDFSelectorApp(root)
#     root.mainloop()
