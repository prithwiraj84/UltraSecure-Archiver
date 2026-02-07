import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import sys  # <--- REQUIRED FOR PYINSTALLER
import threading
from core.backend import SecureCompressor

# --- HELPER FOR PYINSTALLER RESOURCE PATHS ---
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("UltraSecure Archiver")
        self.geometry("750x550")
        self.resizable(False, False)

        # --- SAFE ICON LOADING ---
        # This prevents the "bitmap not defined" crash
        try:
            icon_path = resource_path("icon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass # Use default icon if custom one fails

        self.engine = SecureCompressor()
        self.selected_file = None
        self.current_mode = "compress"

        # Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, width=140, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")
        self.logo = ctk.CTkLabel(self.sidebar_frame, text="ULTRA\nARCHIVER", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo.grid(row=0, column=0, padx=20, pady=20)
        
        self.btn_compress = ctk.CTkButton(self.sidebar_frame, text="Compress", command=self.mode_compress)
        self.btn_compress.grid(row=1, column=0, padx=20, pady=10)
        self.btn_extract = ctk.CTkButton(self.sidebar_frame, text="Extract", command=self.mode_extract)
        self.btn_extract.grid(row=2, column=0, padx=20, pady=10)

        # Main Frame
        self.main_frame = ctk.CTkFrame(self, corner_radius=10)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.lbl_title = ctk.CTkLabel(self.main_frame, text="Compress File", font=ctk.CTkFont(size=24))
        self.lbl_title.pack(pady=20)

        self.btn_browse = ctk.CTkButton(self.main_frame, text="Select File", command=self.browse_file)
        self.btn_browse.pack(pady=10)
        
        self.lbl_file = ctk.CTkLabel(self.main_frame, text="No file selected", text_color="gray")
        self.lbl_file.pack(pady=5)

        self.entry_pass = ctk.CTkEntry(self.main_frame, placeholder_text="Password", show="*", width=300)
        self.entry_pass.pack(pady=20)

        self.progress = ctk.CTkProgressBar(self.main_frame, width=400)
        self.progress.pack(pady=10)
        self.progress.set(0)

        self.lbl_status = ctk.CTkLabel(self.main_frame, text="Ready", text_color="gray")
        self.lbl_status.pack(pady=5)

        self.btn_start = ctk.CTkButton(self.main_frame, text="START", fg_color="green", height=50, command=self.start_process)
        self.btn_start.pack(pady=20)

    def mode_compress(self):
        self.current_mode = "compress"
        self.lbl_title.configure(text="Compress File (Ultra)")
        self.btn_start.configure(fg_color="green", text="START COMPRESSION")
        self.reset_ui()

    def mode_extract(self):
        self.current_mode = "decompress"
        self.lbl_title.configure(text="Extract File")
        self.btn_start.configure(fg_color="#D35B58", text="START EXTRACTION")
        self.reset_ui()

    def reset_ui(self):
        self.selected_file = None
        self.lbl_file.configure(text="No file selected")
        self.entry_pass.delete(0, "end")
        self.progress.set(0)
        self.lbl_status.configure(text="Ready")

    def browse_file(self):
        ft = [("My Encrypted", "*.myc")] if self.current_mode == "decompress" else []
        p = filedialog.askopenfilename(filetypes=ft)
        if p:
            self.selected_file = p
            self.lbl_file.configure(text=os.path.basename(p))

    def start_process(self):
        if not self.selected_file or not self.entry_pass.get():
            return messagebox.showwarning("Error", "File and Password required!")
        
        # Determine output path logic
        if self.current_mode == "compress":
             out = self.selected_file + ".myc"
        else:
             out = self.selected_file.replace(".myc", "") + ".extracted"

        self.btn_start.configure(state="disabled")
        self.progress.set(0)
        threading.Thread(target=self.run_thread, args=(self.selected_file, out, self.entry_pass.get())).start()

    def update_ui(self, val, msg):
        self.progress.set(val)
        self.lbl_status.configure(text=f"{msg} ({int(val*100)}%)")

    def run_thread(self, inp, out, pwd):
        try:
            # THIS CALL MUST MATCH YOUR BACKEND FUNCTION NAME
            self.engine.process_file(inp, out, pwd, self.current_mode, self.update_ui)
            
            self.lbl_status.configure(text="Success!", text_color="green")
            messagebox.showinfo("Done", "Operation Successful!")
        except Exception as e:
            self.lbl_status.configure(text="Error", text_color="red")
            messagebox.showerror("Error", str(e))
        finally:
            self.btn_start.configure(state="normal")
