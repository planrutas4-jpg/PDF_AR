# -*- coding: utf-8 -*-
"""
PDF Rotator Grid - Multi-PDF con Rotación Manual, Auto (geom/heurística sin OCR) y Lote Smart en segundo plano
- Carga múltiples PDFs (sesiones) y los muestra como miniaturas con selección múltiple.
- Rotación manual por selección (↶90 / ↷90 / 180).
- Autodetección:
    * "Auto (geom)" -> sólo geometría (ancho>alto => 90°, vertical => 0°).
    * "Auto (sin OCR)" -> texto rawdict (líneas H vs V); si no hay texto, cae a geometría.
- Guardado por archivo:
    * Por defecto mantiene /Rotate original (no aplica rotaciones).
    * Checkbox para aplicar rotaciones al exportar.
- Lote Smart (botón):
    * Selecciona muchos PDFs, una carpeta destino.
    * Aplica autodetección sin OCR (texto+geometría) a cada página y guarda SIEMPRE como *_smart.pdf.
    * Corre en segundo plano (thread) para no congelar la UI, con barra de progreso.

Requisitos:
    pip install pymupdf pillow
"""

import os
import io
import sys
import fitz  # PyMuPDF
import tkinter as tk
from tkinter import filedialog, ttk
from PIL import Image, ImageTk
from dataclasses import dataclass, field
from typing import Optional, List
import threading

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")


@dataclass
class DocumentSession:
    ruta_pdf: str
    doc: fitz.Document
    num_paginas: int
    rotaciones: List[int] = field(default_factory=list)
    tk_thumbs: List[Optional[ImageTk.PhotoImage]] = field(default_factory=list)
    cards: List[Optional[tk.Frame]] = field(default_factory=list)
    labels_imagen: List[Optional[tk.Label]] = field(default_factory=list)
    labels_num: List[Optional[tk.Label]] = field(default_factory=list)
    seleccionadas: List[bool] = field(default_factory=list)
    last_clicked_index: Optional[int] = None


class PDFRotatorGridApp:
    MINI_W_MAX = 140
    MINI_H_MAX = 190
    COLUMNAS_INICIAL = 8
    MARGEN = 6
    PREVIEW_CHUNK = 6

    COLOR_SELECCIONADO = "blue"
    COLOR_NO_SELECCIONADO = "gray"

    def __init__(self, root):
        self.root = root
        self.root.title("SpinPDF_AR_vr.0014_multi_geom_lote")
        self.root.geometry("1300x720+20+20")

        # Icono (Windows)
        try:
            ico = os.path.join(os.path.dirname(__file__), "Mi_icon_01.ico")
            if IS_WIN and os.path.exists(ico):
                self.root.iconbitmap(ico)
        except Exception:
            pass

        # ---------- Estado (multi-documento) ----------
        self.sessions: List[DocumentSession] = []
        self.current_session_idx: Optional[int] = None
        self.columnas_actuales = self.COLUMNAS_INICIAL
        self._notice_after_id = None

        # ---------- Barra superior ----------
        top = tk.Frame(root); top.pack(fill="x", pady=5)

        # Barra de notificaciones (invisible hasta usar _notify)
        self.notice = tk.Label(
            top, text="", anchor="w", fg="#084ebd", bg="#e6f0ff",
            font=("Arial", 10), padx=10, pady=4, relief="groove", bd=1
        )
        self.notice.pack_forget()

        left = tk.Frame(top); left.pack(side="left", padx=5)
        tk.Button(left, text="Abrir PDF", command=self.seleccionar_pdf).pack(side="left", padx=2)
        tk.Button(left, text="Abrir Varios", command=self.seleccionar_varios_pdfs).pack(side="left", padx=2)
        tk.Button(left, text="Quitar PDF", command=self.quitar_pdf_actual).pack(side="left", padx=6)
        tk.Button(left, text="Lote Smart Guardar…", command=self.lote_smart_guardar).pack(side="left", padx=6)

        # Rotación global (sobre selección del PDF activo)
        rot = tk.Frame(top); rot.pack(side="left", padx=12)
        tk.Label(rot, text="Rotar selección:").pack(side="left", padx=(0, 6))
        tk.Button(rot, text="↶ 90°", command=lambda: self.rotar_seleccionadas(-90)).pack(side="left", padx=2)
        tk.Button(rot, text="↷ 90°", command=lambda: self.rotar_seleccionadas(90)).pack(side="left", padx=2)
        tk.Button(rot, text="180°", command=lambda: self.rotar_seleccionadas(180)).pack(side="left", padx=2)

        # Autodetección (sin OCR)
        auto = tk.Frame(top); auto.pack(side="left", padx=12)
        tk.Label(auto, text="Autodetectar:").pack(side="left", padx=(0, 6))
        tk.Button(auto, text="Auto (geom) selección", command=self.auto_rotate_por_geometria_seleccion)\
            .pack(side="left", padx=2)
        tk.Button(auto, text="Auto (geom) todo", command=self.auto_rotate_por_geometria_todo)\
            .pack(side="left", padx=2)
        tk.Button(auto, text="Auto (sin OCR)", command=self.auto_rotate_fast_selected).pack(side="left", padx=2)

        # Guardado por archivo: checkbox aplicar rotaciones
        self.var_aplicar_rot = tk.BooleanVar(value=False)  # False = mantener /Rotate original
        tk.Checkbutton(top, text="Aplicar rotaciones al exportar", variable=self.var_aplicar_rot)\
            .pack(side="right", padx=8)

        self.btn_guardar = tk.Button(top, text="Guardar como…", command=self.guardar_pdf_como, state="disabled")
        self.btn_guardar.pack(side="right", padx=5)

        # Etiqueta de ruta
        self.lbl_ruta = tk.Label(top, text="Archivo activo: Ninguno", font=("Arial", 9))
        self.lbl_ruta.pack(side="bottom", fill="x", pady=2)

        # ---------- Selección rápida ----------
        sel = tk.Frame(root); sel.pack(fill="x", pady=2)
        for txt, cmd in [("Seleccionar todo", self.seleccionar_todo),
                         ("Deseleccionar todo", self.deseleccionar_todo),
                         ("Pares", self.seleccionar_pares),
                         ("Impares", self.seleccionar_impares),
                         ("Invertir", self.invertir_seleccion)]:
            tk.Button(sel, text=txt, command=cmd).pack(side="left", padx=2)

        # ---------- Principal con lateral ----------
        main = tk.Frame(root); main.pack(fill="both", expand=True)

        side = tk.Frame(main, width=220); side.pack(side="left", fill="y")
        tk.Label(side, text="Archivos cargados:", anchor="w").pack(fill="x", padx=6, pady=(6, 2))
        self.listbox = tk.Listbox(side, height=8, exportselection=False)
        self.listbox.pack(fill="y", expand=True, padx=6, pady=(0, 6))
        self.listbox.bind("<<ListboxSelect>>", self._on_listbox_select)

        cont = tk.Frame(main); cont.pack(fill="both", expand=True, side="left")
        self.canvas = tk.Canvas(cont)
        self.scroll_y = tk.Scrollbar(cont, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scroll_y.set)
        self.inner = tk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.pack(fill="both", expand=True, side="left")
        self.scroll_y.pack(fill="y", side="right")

        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self._bind_scroll(self.canvas)

    # ===================== Notificaciones =====================
    def _notify(self, text, kind="info", duration_ms=5000):
        if kind == "info":
            fg, bg = "#084ebd", "#e6f0ff"
        elif kind == "error":
            fg, bg = "#8b0000", "#ffe6e6"
        else:
            fg, bg = "#333", "#eee"
        self.notice.config(text=text, fg=fg, bg=bg)
        try:
            self.notice.pack_info()
        except Exception:
            self.notice.pack(fill="x")
        if self._notice_after_id:
            self.root.after_cancel(self._notice_after_id)
        self._notice_after_id = self.root.after(duration_ms, self._hide_notice)

    def _hide_notice(self):
        try:
            self.notice.pack_forget()
        except Exception:
            pass
        self._notice_after_id = None

    # ===================== Scroll / Progreso =====================
    def _bind_scroll(self, widget):
        widget.bind("<Enter>", lambda e: widget.bind_all("<MouseWheel>", self._on_mousewheel))
        widget.bind("<Leave>", lambda e: widget.unbind_all("<MouseWheel>"))

    def _on_mousewheel(self, event):
        if IS_MAC:
            self.canvas.yview_scroll(int(-1 * event.delta), "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _barra_progreso(self, titulo, max_val):
        win = tk.Toplevel(self.root); win.title(titulo); win.geometry("420x90"); win.resizable(False, False)
        try:
            ico = os.path.join(os.path.dirname(__file__), "Mi_icon_01.ico")
            if IS_WIN and os.path.exists(ico): win.iconbitmap(ico)
        except Exception:
            pass
        tk.Label(win, text=titulo).pack(pady=5)
        bar = ttk.Progressbar(win, orient="horizontal", length=360, mode="determinate", maximum=max_val)
        bar.pack(pady=5); win.update()
        return win, bar

    # ===================== Helpers de sesión =====================
    def _sess(self) -> Optional[DocumentSession]:
        if self.current_session_idx is None:
            return None
        if not (0 <= self.current_session_idx < len(self.sessions)):
            return None
        return self.sessions[self.current_session_idx]

    def _set_current_session(self, idx: int):
        if 0 <= idx < len(self.sessions):
            self.current_session_idx = idx
            self._pintar_sesion_en_ui()

    def _on_listbox_select(self, _evt=None):
        if not self.listbox.curselection():
            return
        self._set_current_session(self.listbox.curselection()[0])

    # ===================== Apertura / Cierre de PDFs =====================
    def seleccionar_pdf(self):
        ruta = filedialog.askopenfilename(title="Seleccionar PDF", filetypes=[("PDF Files", "*.pdf")])
        if ruta:
            self._agregar_pdf(ruta)

    def seleccionar_varios_pdfs(self):
        rutas = filedialog.askopenfilenames(title="Seleccionar PDFs", filetypes=[("PDF Files", "*.pdf")])
        if not rutas:
            return
        for r in rutas:
            self._agregar_pdf(r)

    def _agregar_pdf(self, ruta):
        try:
            doc = fitz.open(ruta)
            if doc.needs_pass:
                raise RuntimeError("Archivo encriptado (requiere contraseña).")
            ses = DocumentSession(
                ruta_pdf=ruta,
                doc=doc,
                num_paginas=doc.page_count,
                rotaciones=[0] * doc.page_count,
                tk_thumbs=[None] * doc.page_count,
                cards=[None] * doc.page_count,
                labels_imagen=[None] * doc.page_count,
                labels_num=[None] * doc.page_count,
                seleccionadas=[False] * doc.page_count,
                last_clicked_index=None
            )
            self.sessions.append(ses)
            self.listbox.insert("end", os.path.basename(ruta))
            if self.current_session_idx is None:
                self._set_current_session(0)
            else:
                self._notify(f"Cargado: {ruta}", "info", 1800)
        except Exception as e:
            self._notify(f"Error abriendo {ruta}: {e}", "error", 6000)

    def quitar_pdf_actual(self):
        ses = self._sess()
        if not ses:
            return
        try:
            ses.doc.close()
        except Exception:
            pass
        idx = self.current_session_idx
        del self.sessions[idx]
        self.listbox.delete(idx)
        self.current_session_idx = None if not self.sessions else min(idx, len(self.sessions) - 1)
        if self.current_session_idx is not None:
            self._set_current_session(self.current_session_idx)
        else:
            for w in self.inner.winfo_children(): w.destroy()
            self.lbl_ruta.config(text="Archivo activo: Ninguno")
            self.btn_guardar.config(state="disabled")

    # ===================== Pintar/repintar la sesión activa =====================
    def _pintar_sesion_en_ui(self):
        ses = self._sess()
        if not ses:
            self.lbl_ruta.config(text="Archivo activo: Ninguno")
            self.btn_guardar.config(state="disabled")
            return

        # Limpia el contenedor visible (de la sesión anterior)
        for w in self.inner.winfo_children():
            w.destroy()

        self.lbl_ruta.config(text=f"Archivo activo: {ses.ruta_pdf}")
        self.btn_guardar.config(state="normal")

        # ¿Ya existen todas las miniaturas?
        faltan = [i for i, t in enumerate(ses.tk_thumbs) if t is None]
        if not faltan:
            # Las cards/labels antiguos ya no existen; reconstruye desde thumbs
            ses.cards = [None] * ses.num_paginas
            ses.labels_imagen = [None] * ses.num_paginas
            ses.labels_num = [None] * ses.num_paginas
            for i, img_tk in enumerate(ses.tk_thumbs):
                self._agregar_miniatura_sesion(i, img_tk)
            self._reflow_grid()
            self.actualizar_ui()
            return

        # Si faltan, carga en lotes
        self.prog_win, self.prog_bar = self._barra_progreso("Cargando PDF...", ses.num_paginas)
        self._preview_index = 0
        self._preview_chunk_sesion()

    def _preview_chunk_sesion(self):
        ses = self._sess()
        if not ses:
            return
        s = self._preview_index
        e = min(self._preview_index + self.PREVIEW_CHUNK, ses.num_paginas)
        for i in range(s, e):
            try:
                self._render_preview_into_slot_sesion(i)
            except Exception:
                from PIL import Image as PILImage
                dummy = PILImage.new("RGB", (self.MINI_W_MAX, self.MINI_H_MAX), "lightgray")
                img_tk = ImageTk.PhotoImage(dummy)
                ses.tk_thumbs[i] = img_tk
                self._agregar_miniatura_sesion(i, img_tk)
            self.prog_bar["value"] = i + 1
            self.prog_bar.update()
        self._preview_index = e
        if self._preview_index < ses.num_paginas:
            self.root.after(10, self._preview_chunk_sesion)
        else:
            self.prog_win.destroy()
            self._reflow_grid()
            self._notify("PDF cargado", "info", 1500)

    # ===================== Miniaturas / tarjetas =====================
    def _render_preview_into_slot_sesion(self, i):
        ses = self._sess()
        if not ses:
            return
        page = ses.doc[i]
        try:
            orig = page.rotation
        except Exception:
            orig = 0
        rot = int((orig + ses.rotaciones[i]) % 360)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5).prerotate(rot), alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img.thumbnail((self.MINI_W_MAX, self.MINI_H_MAX), Image.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        ses.tk_thumbs[i] = img_tk
        self._agregar_miniatura_sesion(i, img_tk)

    def _agregar_miniatura_sesion(self, i, img_tk):
        ses = self._sess()
        if not ses or not self.inner or not self.inner.winfo_exists():
            return
        cont = tk.Frame(self.inner)
        ses.cards[i] = cont
        r = i // self.columnas_actuales
        c = i % self.columnas_actuales
        cont.grid(row=r, column=c, padx=self.MARGEN, pady=self.MARGEN)

        img_lbl = tk.Label(cont, image=img_tk, borderwidth=2, relief="solid", highlightthickness=2)
        img_lbl.pack()
        img_lbl.bind("<Button-1>", lambda e, idx=i: self.seleccionar_pagina_sesion(idx, e))
        ses.labels_imagen[i] = img_lbl

        txt = tk.Label(cont, text=f"Pág. {i + 1} (rot: {ses.rotaciones[i]}°)")
        txt.pack(pady=2)
        ses.labels_num[i] = txt

    # ===================== Responsive =====================
    def _on_canvas_resize(self, event):
        card_w = self.MINI_W_MAX + self.MARGEN * 2 + 4
        if card_w <= 0:
            return
        cols = max(1, min(16, event.width // card_w))
        if cols != self.columnas_actuales:
            self.columnas_actuales = cols
            self._reflow_grid()

    def _reflow_grid(self):
        ses = self._sess()
        if not ses:
            return
        for i, cont in enumerate(ses.cards):
            if not cont:
                continue
            try:
                if not cont.winfo_exists():
                    continue
            except Exception:
                continue
            r = i // self.columnas_actuales
            c = i % self.columnas_actuales
            cont.grid_configure(row=r, column=c, padx=self.MARGEN, pady=self.MARGEN)

    # ===================== Selección de páginas =====================
    def seleccionar_pagina_sesion(self, i, e):
        ses = self._sess()
        if not ses:
            return
        shift = bool(e.state & 0x0001)
        ctrl = bool(e.state & 0x0004)
        cmd = IS_MAC and bool(e.state & 0x0008)
        mod = ctrl or cmd

        if shift and ses.last_clicked_index is not None:
            a, b = sorted([ses.last_clicked_index, i])
            for j in range(a, b + 1):
                ses.seleccionadas[j] = True
        elif mod:
            ses.seleccionadas[i] = not ses.seleccionadas[i]
        else:
            ses.seleccionadas = [False] * ses.num_paginas
            ses.seleccionadas[i] = True

        ses.last_clicked_index = i
        self.actualizar_ui()

    def actualizar_ui(self):
        ses = self._sess()
        if not ses:
            return
        for i in range(ses.num_paginas):
            lbl = ses.labels_imagen[i]
            if not lbl:
                continue
            try:
                if not lbl.winfo_exists():
                    continue
            except Exception:
                continue
            color = self.COLOR_SELECCIONADO if ses.seleccionadas[i] else self.COLOR_NO_SELECCIONADO
            lbl.config(highlightbackground=color, highlightcolor=color)
            txt = ses.labels_num[i]
            if txt:
                try:
                    if not txt.winfo_exists():
                        continue
                except Exception:
                    continue
                txt.config(
                    text=f"Pág. {i + 1} (rot: {ses.rotaciones[i]}°)",
                    fg=("blue" if ses.seleccionadas[i] else "black")
                )

    # ===================== Autodetección SIN OCR =====================
    def infer_orient_sin_ocr(self, page) -> int:
        """
        Devuelve orientación sugerida (0 o 90) basada en texto bruto.
        - Cuenta líneas horizontales vs verticales (rawdict).
        - Si no hay texto, usa geometría de la página.
        """
        try:
            raw = page.get_text("rawdict")
            h_like = 0
            v_like = 0
            for b in raw.get("blocks", []):
                if b.get("type") != 0:  # solo texto
                    continue
                for l in b.get("lines", []):
                    x0, y0, x1, y1 = l["bbox"]
                    w, h = (x1 - x0), (y1 - y0)
                    if w >= h:
                        h_like += 1
                    else:
                        v_like += 1
            if h_like == v_like == 0:
                r = page.rect
                return 90 if r.width > r.height else 0
            return 0 if h_like >= v_like else 90
        except Exception:
            r = page.rect
            return 90 if r.width > r.height else 0

    # ===== Auto (geom) – SOLO geometría ancho/alto =====
    def auto_rotate_por_geometria_seleccion(self):
        """Detecta orientación por geometría (ancho>alto => 90°, si no 0°) en páginas seleccionadas."""
        ses = self._sess()
        if not ses:
            self._notify("Abre un PDF", "error", 3000); return
        if not any(ses.seleccionadas):
            self._notify("Selecciona páginas para autodetectar", "info", 3000); return

        cambios = 0
        for i, sel in enumerate(ses.seleccionadas):
            if not sel:
                continue
            page = ses.doc[i]
            try:
                orig = page.rotation
            except Exception:
                orig = 0

            w, h = page.rect.width, page.rect.height
            target = 90 if w > h else 0  # apaisado -> 90°, vertical -> 0°
            eff_rot = (orig + ses.rotaciones[i]) % 360
            delta = (target - eff_rot) % 360
            if delta != 0:
                self._apply_rotation_sesion(i, (ses.rotaciones[i] + delta) % 360)
                cambios += 1

        self.actualizar_ui()
        self._notify(f"Auto (geom): {'ajustadas ' + str(cambios) if cambios else 'sin cambios.'}", "info", 3000)

    def auto_rotate_por_geometria_todo(self):
        """Detecta orientación por geometría (ancho>alto => 90°, si no 0°) en TODAS las páginas del documento."""
        ses = self._sess()
        if not ses:
            self._notify("Abre un PDF", "error", 3000); return

        cambios = 0
        for i in range(ses.num_paginas):
            page = ses.doc[i]
            try:
                orig = page.rotation
            except Exception:
                orig = 0

            w, h = page.rect.width, page.rect.height
            target = 90 if w > h else 0
            eff_rot = (orig + ses.rotaciones[i]) % 360
            delta = (target - eff_rot) % 360
            if delta != 0:
                self._apply_rotation_sesion(i, (ses.rotaciones[i] + delta) % 360)
                cambios += 1

        self.actualizar_ui()
        self._notify(f"Auto (geom) todo: {'ajustadas ' + str(cambios) if cambios else 'sin cambios.'}", "info", 3000)

    # ===== Auto (sin OCR) – texto rawdict + geometría =====
    def auto_rotate_fast_selected(self):
        """Autodetección sin OCR: texto rawdict + geometría (respeta /Rotate original)."""
        ses = self._sess()
        if not ses:
            self._notify("Abre un PDF", "error", 3000); return
        if not any(ses.seleccionadas):
            self._notify("Selecciona páginas para autodetectar", "info", 3000); return

        cambios = 0
        for i, sel in enumerate(ses.seleccionadas):
            if not sel:
                continue
            page = ses.doc[i]
            try:
                orig = page.rotation
            except Exception:
                orig = 0

            target = self.infer_orient_sin_ocr(page)  # 0 o 90
            eff_rot = (orig + ses.rotaciones[i]) % 360
            delta = (target - eff_rot) % 360
            if delta != 0:
                self._apply_rotation_sesion(i, (ses.rotaciones[i] + delta) % 360)
                cambios += 1

        self.actualizar_ui()
        self._notify(f"Auto (sin OCR): {'ajustadas ' + str(cambios) if cambios else 'sin cambios.'}", "info", 3000)

    # ===================== Rotación manual y previews =====================
    def rotar_seleccionadas(self, grados):
        ses = self._sess()
        if not ses:
            self._notify("Abre un PDF", "error", 3000); return
        if not any(ses.seleccionadas):
            self._notify("Selecciona páginas", "info", 2500); return
        for i, sel in enumerate(ses.seleccionadas):
            if not sel:
                continue
            self._apply_rotation_sesion(i, (ses.rotaciones[i] + grados) % 360)
        self.actualizar_ui()

    def _apply_rotation_sesion(self, i, new_rot):
        ses = self._sess()
        if not ses:
            return
        ses.rotaciones[i] = new_rot
        try:
            page = ses.doc[i]
            try:
                orig = page.rotation
            except Exception:
                orig = 0
            eff = int((orig + new_rot) % 360)
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5).prerotate(eff), alpha=False)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            img.thumbnail((self.MINI_W_MAX, self.MINI_H_MAX), Image.LANCZOS)
            ses.tk_thumbs[i] = ImageTk.PhotoImage(img)
            ses.labels_imagen[i].config(image=ses.tk_thumbs[i])
        except Exception as e:
            print(f"Re-preview pág {i + 1} falló: {e}", file=sys.stderr)

    # ===================== Guardado por archivo =====================
    def guardar_pdf_como(self):
        ses = self._sess()
        if not ses:
            self._notify("No hay PDF activo", "error", 3500); return

        ruta = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if not ruta:
            self._notify("Guardado cancelado", "info", 2500); return

        aplicar = self.var_aplicar_rot.get()
        win, bar = self._barra_progreso("Guardando PDF...", ses.num_paginas)
        try:
            nuevo = fitz.open()
            nuevo.insert_pdf(ses.doc, from_page=0, to_page=ses.num_paginas - 1)

            if aplicar:
                for i, ang in enumerate(ses.rotaciones):
                    page = nuevo[i]
                    try:
                        orig = page.rotation
                    except Exception:
                        orig = 0
                    page.set_rotation(int((orig + ang) % 360))
                    bar["value"] = i + 1; bar.update()
            else:
                for i in range(ses.num_paginas):
                    bar["value"] = i + 1; bar.update()

            nuevo.save(ruta); nuevo.close()
            win.destroy()
            self._notify(
                f"PDF guardado en: {ruta}  ·  {'(con rotaciones)' if aplicar else '(manteniendo originales)'}",
                "info", 5500
            )
            self._open_folder(ruta)
        except Exception as e:
            win.destroy()
            self._notify(f"Error al guardar: {e}", "error", 7000)

    # ===================== Utilidades =====================
    def _open_folder(self, any_path):
        try:
            folder = os.path.dirname(any_path)
            if IS_WIN:
                os.startfile(folder)
            elif sys.platform == "darwin":
                os.system(f'open "{folder}"')
            else:
                os.system(f'xdg-open "{folder}"')
        except Exception:
            pass

    def _safe_out(self, outdir, base, sufijo="_smart", ext=".pdf"):
        path = os.path.join(outdir, f"{base}{sufijo}{ext}")
        if not os.path.exists(path):
            return path
        k = 1
        while True:
            p2 = os.path.join(outdir, f"{base}{sufijo}_{k}{ext}")
            if not os.path.exists(p2):
                return p2
            k += 1

    # ===================== Lote Smart (en segundo plano) =====================
    def lote_smart_guardar(self):
        """
        Selecciona múltiples PDFs, carpeta de destino y:
          - Aplica smart-rotado sin OCR (texto+geometría) a cada página (respeta /Rotate original).
          - Guarda SIEMPRE como *_smart.pdf (aunque no haya cambios).
          - Se ejecuta en un hilo y actualiza una barra de progreso sin congelar la UI.
        """
        rutas = filedialog.askopenfilenames(
            title="Seleccionar PDFs para Lote Smart",
            filetypes=[("PDF Files", "*.pdf")]
        )
        if not rutas:
            self._notify("Lote cancelado: no se seleccionaron archivos", "info", 3000)
            return

        outdir = filedialog.askdirectory(title="Seleccionar carpeta de destino")
        if not outdir:
            self._notify("Lote cancelado: no se eligió carpeta de destino", "info", 3000)
            return

        # Pre-conteo de páginas (en UI) y crea barra
        total_paginas = 0
        for r in rutas:
            try:
                with fitz.open(r) as tmpdoc:
                    if tmpdoc.needs_pass:
                        continue
                    total_paginas += tmpdoc.page_count
            except Exception:
                pass
        if total_paginas == 0:
            self._notify("No se pudieron leer páginas de los PDFs seleccionados", "error", 5000)
            return

        win, bar = self._barra_progreso("Procesando lote (smart)…", total_paginas)

        def worker():
            procesadas = 0
            guardados = 0
            errores = 0
            for ruta in rutas:
                try:
                    doc = fitz.open(ruta)
                    if doc.needs_pass:
                        raise RuntimeError("Archivo encriptado (requiere contraseña).")
                except Exception as e:
                    errores += 1
                    print(f"[LOTE] Error abriendo {ruta}: {e}", file=sys.stderr)
                    continue

                try:
                    nuevo = fitz.open()
                    nuevo.insert_pdf(doc, from_page=0, to_page=doc.page_count - 1)

                    for i in range(doc.page_count):
                        page = nuevo[i]
                        try:
                            orig = page.rotation
                        except Exception:
                            orig = 0

                        # Primero intentamos inferir por texto; si no hay, cae a geometría
                        target = self.infer_orient_sin_ocr(page)  # 0 o 90
                        delta = (target - orig) % 360
                        if delta != 0:
                            page.set_rotation(int((orig + delta) % 360))

                        procesadas += 1
                        self.root.after(0, lambda v=procesadas: (bar.config(value=v), bar.update()))

                    base = os.path.splitext(os.path.basename(ruta))[0]
                    salida = self._safe_out(outdir, base, "_smart", ".pdf")
                    nuevo.save(salida)
                    nuevo.close()
                    doc.close()
                    guardados += 1

                except Exception as e:
                    errores += 1
                    try:
                        nuevo.close()
                    except Exception:
                        pass
                    try:
                        doc.close()
                    except Exception:
                        pass
                    print(f"[LOTE] Error procesando {ruta}: {e}", file=sys.stderr)

            self.root.after(0, lambda: (win.destroy(),
                                        self._notify(
                                            f"Lote terminado · Guardados: {guardados}  · Errores: {errores}  · Carpeta: {outdir}",
                                            "info", 8000)))

        threading.Thread(target=worker, daemon=True).start()

    # ===================== Selección rápida =====================
    def seleccionar_todo(self):
        ses = self._sess()
        if ses and ses.num_paginas:
            ses.seleccionadas = [True] * ses.num_paginas
            self.actualizar_ui()

    def deseleccionar_todo(self):
        ses = self._sess()
        if ses and ses.num_paginas:
            ses.seleccionadas = [False] * ses.num_paginas
            self.actualizar_ui()

    def seleccionar_pares(self):
        ses = self._sess()
        if ses and ses.num_paginas:
            ses.seleccionadas = [((i + 1) % 2 == 0) for i in range(ses.num_paginas)]
            self.actualizar_ui()

    def seleccionar_impares(self):
        ses = self._sess()
        if ses and ses.num_paginas:
            ses.seleccionadas = [((i + 1) % 2 == 1) for i in range(ses.num_paginas)]
            self.actualizar_ui()

    def invertir_seleccion(self):
        ses = self._sess()
        if ses and ses.num_paginas:
            ses.seleccionadas = [not v for v in ses.seleccionadas]
            self.actualizar_ui()


if __name__ == "__main__":
    root = tk.Tk()
    app = PDFRotatorGridApp(root)
    root.mainloop()
