import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import io
import threading

class PDFRotatorGridApp:
    MINIATURA_ANCHO = 140
    MINIATURA_ALTO = 190
    COLUMNAS = 5
    MARGEN = 5
    COLOR_SELECCIONADO = "blue"
    COLOR_NO_SELECCIONADO = "gray"

    def __init__(self, root):
        self.root = root
        self.root.title("SpinPDF_AR_vr.0001")
        self.root.geometry("900x600")

        # Variables PDF
        self.doc = None
        self.ruta_pdf = None
        self.num_paginas = 0
        self.rotaciones = []
        self.imagenes_originales = []
        self.imagenes_tk = []
        self.labels_imagen = []
        self.labels_num = []
        self.seleccionadas = []

        # Para selección múltiple
        self.ctrl_pressed = False
        self.last_clicked_index = None

        # ---------- UI ----------
        top_frame = tk.Frame(root)
        top_frame.pack(fill="x", pady=5)

        instrucciones = "Ctrl + ← (90° izq) | Ctrl + → (90° der)| Ctrl + ↑ (180°)"
        tk.Label(top_frame, text=instrucciones, font=("Arial", 10), fg="darkgreen").pack(pady=2)

        tk.Button(top_frame, text="Abrir PDF", command=self.seleccionar_pdf).pack(side="left", padx=5)
        self.btn_guardar = tk.Button(top_frame, text="Guardar como...", command=self.guardar_pdf_como, state="disabled")
        self.btn_guardar.pack(side="right", padx=5)

        # --- Frame selección rápida ---
        sel_frame = tk.Frame(root)
        sel_frame.pack(fill="x", pady=2)
        tk.Button(sel_frame, text="Seleccionar todo", command=self.seleccionar_todo).pack(side="left", padx=2)
        tk.Button(sel_frame, text="Deseleccionar todo", command=self.deseleccionar_todo).pack(side="left", padx=2)
        tk.Button(sel_frame, text="Seleccionar pares", command=self.seleccionar_pares).pack(side="left", padx=2)
        tk.Button(sel_frame, text="Seleccionar impares", command=self.seleccionar_impares).pack(side="left", padx=2)

        # Canvas y scroll
        self.canvas = tk.Canvas(root)
        self.scroll_y = tk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.frame = tk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scroll_y.set)
        self.canvas.pack(fill="both", expand=True, side="left")
        self.scroll_y.pack(fill="y", side="right")
        self.frame.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Scroll Windows
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        # Scroll Linux/macOS
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # Bind de teclas
        self.root.bind("<Control-Right>", lambda e: self.rotar_seleccionadas(90))
        self.root.bind("<Control-Left>", lambda e: self.rotar_seleccionadas(-90))
        self.root.bind("<Control-Up>", lambda e: self.rotar_seleccionadas(180))
        self.root.bind("<Control_L>", self.ctrl_down)
        self.root.bind("<KeyRelease-Control_L>", self.ctrl_up)

    # ---------- Ctrl pressed ----------
    def ctrl_down(self, event):
        self.ctrl_pressed = True

    def ctrl_up(self, event):
        self.ctrl_pressed = False

    # ---------- Cargar PDF ----------
    def cargar_pdf(self, ruta):
        try:
            if self.doc:
                self.doc.close()
            self.doc = fitz.open(ruta)
            self.ruta_pdf = ruta
            self.num_paginas = self.doc.page_count
            self.rotaciones = [0] * self.num_paginas
            self.imagenes_originales.clear()
            self.imagenes_tk.clear()
            self.labels_imagen.clear()
            self.labels_num.clear()
            self.seleccionadas = [False]*self.num_paginas
            self.last_clicked_index = None

            # Hilo para crear miniaturas y mostrar barra de progreso
            threading.Thread(target=self.crear_preview, daemon=True).start()
            self.btn_guardar.config(state="normal")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo abrir el PDF:\n{e}")

    # ---------- Crear miniaturas con ventana de progreso ----------
    def crear_preview(self):
        # Limpiar widgets antiguos
        for widget in self.frame.winfo_children():
            widget.destroy()

        # Ventana de progreso
        progress_window = tk.Toplevel(self.root)
        progress_window.title("Cargando PDF...")
        progress_window.geometry("400x70")
        progress_window.resizable(False, False)
        tk.Label(progress_window, text="Cargando páginas, por favor espere...").pack(pady=5)
        progress = ttk.Progressbar(progress_window, orient="horizontal", length=350, mode="determinate")
        progress.pack(pady=10)
        progress["maximum"] = self.num_paginas
        progress["value"] = 0
        progress_window.update()

        # Crear miniaturas
        for i in range(self.num_paginas):
            pagina = self.doc[i]
            pix = pagina.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            self.imagenes_originales.append(img)

            miniatura = img.resize((self.MINIATURA_ANCHO, self.MINIATURA_ALTO))
            img_tk = ImageTk.PhotoImage(miniatura)
            self.imagenes_tk.append(img_tk)

            # Crear miniatura en hilo principal
            self.root.after(0, self.agregar_miniatura, i, img_tk)

            # Actualizar barra de progreso
            progress["value"] = i + 1
            progress_window.update()

        progress_window.destroy()

    def agregar_miniatura(self, i, img_tk):
        contenedor = tk.Frame(self.frame)
        contenedor.grid(row=i // self.COLUMNAS, column=i % self.COLUMNAS, padx=self.MARGEN, pady=self.MARGEN)

        lbl_img = tk.Label(contenedor, image=img_tk, borderwidth=2, relief="solid", highlightthickness=2)
        lbl_img.pack()
        lbl_img.bind("<Button-1>", lambda e, idx=i: self.seleccionar_pagina(idx, e))
        self.labels_imagen.append(lbl_img)

        lbl_num = tk.Label(contenedor, text=f"Pág. {i+1} (rot: {self.rotaciones[i]}°)")
        lbl_num.pack(pady=2)
        self.labels_num.append(lbl_num)

    # ---------- Selección de páginas ----------
    def seleccionar_pagina(self, indice, event):
        shift_pressed = (event.state & 0x0001) != 0
        if shift_pressed and self.last_clicked_index is not None:
            start = min(self.last_clicked_index, indice)
            end = max(self.last_clicked_index, indice)
            for i in range(start, end+1):
                self.seleccionadas[i] = True
        elif self.ctrl_pressed:
            self.seleccionadas[indice] = not self.seleccionadas[indice]
        else:
            self.seleccionadas = [False]*self.num_paginas
            self.seleccionadas[indice] = True

        self.last_clicked_index = indice
        self.actualizar_ui()

    def actualizar_ui(self):
        for i, lbl in enumerate(self.labels_imagen):
            color = self.COLOR_SELECCIONADO if self.seleccionadas[i] else self.COLOR_NO_SELECCIONADO
            lbl.config(highlightbackground=color, highlightcolor=color)
        for i, lbl_num in enumerate(self.labels_num):
            lbl_num.config(text=f"Pág. {i+1} (rot: {self.rotaciones[i]}°)")

    # ---------- Rotar páginas seleccionadas ----------
    def rotar_seleccionadas(self, grados):
        for i, sel in enumerate(self.seleccionadas):
            if sel:
                self.rotaciones[i] = (self.rotaciones[i] + grados) % 360
                img = self.imagenes_originales[i].rotate(self.rotaciones[i], expand=True)
                img = img.resize((self.MINIATURA_ANCHO, self.MINIATURA_ALTO))
                img_tk = ImageTk.PhotoImage(img)
                self.imagenes_tk[i] = img_tk
                self.labels_imagen[i].config(image=img_tk)
        self.actualizar_ui()

    # ---------- Guardar PDF con ventana de progreso ----------
    def guardar_pdf_como(self):
        ruta_guardado = filedialog.asksaveasfilename(
            title="Guardar PDF",
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not ruta_guardado:
            return

        progress_window = tk.Toplevel(self.root)
        progress_window.title("Guardando PDF...")
        progress_window.geometry("400x70")
        progress_window.resizable(False, False)
        tk.Label(progress_window, text="Guardando páginas, por favor espere...").pack(pady=5)
        progress = ttk.Progressbar(progress_window, orient="horizontal", length=350, mode="determinate")
        progress.pack(pady=10)
        progress["maximum"] = self.num_paginas
        progress["value"] = 0
        progress_window.update()

        try:
            nuevo_pdf = fitz.open()
            for i, pagina in enumerate(self.doc):
                nueva_pagina = nuevo_pdf.new_page(width=pagina.rect.width, height=pagina.rect.height)
                nueva_pagina.show_pdf_page(pagina.rect, self.doc, i, rotate=self.rotaciones[i])

                progress["value"] = i + 1
                progress_window.update()

            nuevo_pdf.save(ruta_guardado)
            nuevo_pdf.close()
            progress_window.destroy()
            messagebox.showinfo("Listo", f"PDF guardado en:\n{ruta_guardado}")
        except Exception as e:
            progress_window.destroy()
            messagebox.showerror("Error", f"No se pudo guardar el PDF:\n{e}")

    # ---------- Seleccionar PDF ----------
    def seleccionar_pdf(self):
        ruta = filedialog.askopenfilename(title="Seleccionar PDF", filetypes=[("PDF Files", "*.pdf")])
        if ruta:
            self.cargar_pdf(ruta)

    # ---------- Selección rápida ----------
    def seleccionar_todo(self):
        self.seleccionadas = [True]*self.num_paginas
        self.actualizar_ui()

    def deseleccionar_todo(self):
        self.seleccionadas = [False]*self.num_paginas
        self.actualizar_ui()

    def seleccionar_pares(self):
        self.seleccionadas = [(i % 2 == 1) for i in range(self.num_paginas)]
        self.actualizar_ui()

    def seleccionar_impares(self):
        self.seleccionadas = [(i % 2 == 0) for i in range(self.num_paginas)]
        self.actualizar_ui()


# # ---------- Inicializar ----------
# if __name__ == "__main__":
#     root = tk.Tk()
#     app = PDFRotatorGridApp(root)
#     root.mainloop()
