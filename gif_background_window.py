import tkinter as tk
from PIL import Image, ImageTk, ImageSequence

class GIFBackgroundWindow:
    def __init__(self, gif_path,icon_path, width=350, height=200, title="GIF de fondo animado"):
        # Crear ventana principal
        self.ventana = tk.Tk()
        self.ventana.title(title)
        self.width = width
        self.height = height
        self.ventana.geometry(f"{width}x{height}+700+500")
        self.ventana.resizable(False, False)
        self.ventana.iconbitmap(icon_path)

        # --- Cargar GIF ---
        self.gif = Image.open(gif_path)
        self.frames = [ImageTk.PhotoImage(frame.copy().resize((width, height))) for frame in ImageSequence.Iterator(self.gif)]

        # --- Label que mostrará el GIF ---
        self.label_fondo = tk.Label(self.ventana)
        self.label_fondo.place(x=0, y=30, relwidth=1, relheight=1)# cubre toda la ventana

        # Iniciar animación
        self._animar(0)

    def _animar(self, indice):
        frame = self.frames[indice]
        self.label_fondo.config(image=frame)
        self.ventana.after(100, self._animar, (indice + 1) % len(self.frames))

    def show(self):
        self.ventana.mainloop()
