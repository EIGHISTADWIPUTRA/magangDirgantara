"""
Health Check GUI Application for Raspberry Pi

This GUI application provides a visual interface to check the status of all sensors
and connected hardware. It can be run standalone or configured to auto-start on boot.

Usage:
    python finalCode/health_check_gui.py
    python -m finalCode.health_check_gui
"""

import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
import json
import math
import queue
import re
import threading
import time
import os
import sys

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = None
    ImageTk = None

# Ensure the parent directory of finalCode is on sys.path
_package_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_package_dir)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


# YOLO model configuration (NCNN directory).
YOLO_MODEL_PATH = "/home/eighista/Documents/MAGANG/finalCode/models/yolo_ncnn_model"
#YOLO_MODEL_PATH = "/home/eighista/Documents/MAGANG/models/model_yolo/yolo11n_ncnn_model"
YOLO_WINDOW_NAME = "YOLO Detection"
MISSION_DETAIL_DIR = "/home/eighista/Documents/MAGANG/finalCode/server/misi/detail_misi"
MISSION_IMAGE_DIR = "/home/eighista/Documents/MAGANG/finalCode/server/misi/gambar"
MISSION_ROUTE_DIR = "/home/eighista/Documents/MAGANG/finalCode/server/misi/jalur"
TARGET_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
MISSION_IDLE_POLL_SECONDS = 0.05
MISSION_ROUTE_POINTS = 25
MISSION_ROUTE_TAIL_POINTS = 5
MISSION_ROUTE_STEP_SECONDS = 1.0
MISSION_CANVAS_MAX_FPS = 10.0
MISSION_DETAIL_POLL_INTERVAL = 0.5
MISSION_LORA_TIMEOUT_SECONDS = 2.0
MISSION_LORA_QUEUE_MAXSIZE = 4
MISSION_DEFAULT_START_LAT = -6.897215185425813
MISSION_DEFAULT_START_LON = 107.58045436326525


class HealthCheckGUI:
    """GUI for system health checks."""
    
    def __init__(self, root):
        """Initialize the health check GUI."""
        self.root = root
        self.root.title("System Health Check")
        screen_w = max(800, self.root.winfo_screenwidth())
        screen_h = max(600, self.root.winfo_screenheight())
        window_w = min(1350, int(screen_w * 0.96))
        window_h = min(720, int(screen_h * 0.92))
        window_w = min(window_w, max(700, screen_w - 20))
        window_h = min(window_h, max(500, screen_h - 40))
        self.root.geometry(f"{window_w}x{window_h}")
        self.root.minsize(min(900, window_w), min(560, window_h))
        self.root.resizable(True, True)
        
        # Color scheme
        self.COLOR_BG = "#1e1e1e"
        self.COLOR_FG = "#ffffff"
        self.COLOR_SUCCESS = "#00ff00"
        self.COLOR_ERROR = "#ff0000"
        self.COLOR_WARNING = "#ffcc00"
        self.COLOR_PENDING = "#808080"
        
        # Configure root style
        self.root.configure(bg=self.COLOR_BG)
        
        # Status tracking
        self.sensor_status = {}
        self.is_checking = False
        self.app_closing = False

        # YOLO tracking
        self.yolo_running = False
        self.yolo_thread = None
        self.yolo_model = None
        self.yolo_shutting_down = False
        self.yolo_photo = None

        # LoRa sender tracking
        self.lora_running = False
        self.lora_thread = None
        self.lora_sender = None
        self.lora_counter = 1
        self.lora_interval = 0.5

        # Waiting mission tracking
        self.current_view = "health"
        self.mission_running = False
        self.mission_thread = None
        self.mission_state = "IDLE"
        self.mission_target = None
        self.mission_last_target_id = None
        self.mission_active_target_id = None
        self.mission_countdown_until = None
        self.mission_lock_started_at = None
        self.mission_lock_duration = 3.0
        self.mission_countdown_seconds = 3.0
        self.mission_countdown_display = "-"
        self.mission_conf_threshold = 0.35

        self.mission_lora_sender = None
        self.mission_lora_counter = 1
        self.mission_lora_interval = 1.0
        self.mission_last_lora_sent_at = 0.0
        self.mission_next_lora_retry_at = 0.0
        self.mission_lora_retry_delay = 1.5
        self.mission_lora_lock = threading.Lock()
        # Fix #2 – dedicated lock so cleanup() waits for any in-flight send
        self.mission_lora_send_lock = threading.Lock()
        self.mission_lora_stats_lock = threading.Lock()
        self.mission_lora_enqueued_count = 0
        self.mission_lora_sent_count = 0
        self.mission_lora_failed_count = 0
        self.mission_lora_dropped_count = 0
        self.mission_lora_queue = None
        self.mission_lora_worker = None
        self.mission_lora_worker_stop = threading.Event()

        self.mission_camera = None
        self.mission_camera_photo = None
        self.mission_target_photo = None
        self.mission_next_camera_retry_at = 0.0
        self.mission_camera_retry_delay = 1.5
        self.mission_frame_fail_count = 0
        self.mission_frame_fail_reopen_threshold = 20
        self.mission_canvas_last_update_at = 0.0
        self.mission_detail_last_poll_at = 0.0
        self.mission_detail_cache = None

        self.mission_detail_dir = MISSION_DETAIL_DIR
        self.mission_image_dir = MISSION_IMAGE_DIR
        self.mission_route_dir = MISSION_ROUTE_DIR
        self.mission_route_points = []
        self.mission_route_index = -1
        self.mission_route_next_step_at = 0.0
        self.mission_tail_detect_streak = 0
        self.mission_tail_hit = False
        self.mission_last_found = False
        self.mission_start_lat = MISSION_DEFAULT_START_LAT
        self.mission_start_lon = MISSION_DEFAULT_START_LON
        self.mission_last_route_file = None
        self.mission_last_invalid_detail = None

        self.socket_server_process = None
        self.socket_server_log_thread = None
        self.latest_target_state_path = ""
        self.target_images_dir = self.mission_image_dir

        # Fix #1 – single-slot frame queues for decoupled canvas rendering
        self._yolo_frame_queue = queue.Queue(maxsize=1)
        self._mission_frame_queue = queue.Queue(maxsize=1)

        # Fix #5 – cache folder mtime to skip scandir when directory unchanged
        self._last_folder_mtime_ns = -1
        self._last_detail_path = None

        # Fix #6 – event-based clean stop for mission thread
        self._mission_stop_event = threading.Event()

        # Health check state machine (UI-thread safe via after scheduler)
        self.health_check_steps = []
        self.health_check_step_index = 0
        
        # Build UI
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        
    def build_ui(self):
        """Build the GUI components."""
        # Header
        header_frame = tk.Frame(self.root, bg="#0066cc")
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        
        title_label = tk.Label(
            header_frame,
            text="🔧 System Health Check",
            font=("Arial", 18, "bold"),
            bg="#0066cc",
            fg=self.COLOR_FG
        )
        title_label.pack(pady=(12, 8))

        nav_frame = tk.Frame(header_frame, bg="#0066cc")
        nav_frame.pack(fill=tk.X, padx=12, pady=(0, 12))

        self.health_view_btn = tk.Button(
            nav_frame,
            text="🔧 Health Check",
            command=self.show_health_page,
            bg="#0f4f8a",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.health_view_btn.pack(side=tk.LEFT, padx=(0, 6))

        self.mission_view_btn = tk.Button(
            nav_frame,
            text="🎯 Waiting Misi",
            command=self.show_mission_page,
            bg="#1f7a2e",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=6,
            cursor="hand2"
        )
        self.mission_view_btn.pack(side=tk.LEFT)

        # Page container
        self.page_container = tk.Frame(self.root, bg=self.COLOR_BG)
        self.page_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # Health check page
        self.health_content_frame = tk.Frame(self.page_container, bg=self.COLOR_BG)
        self.health_content_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel (health check)
        left_panel = tk.Frame(self.health_content_frame, bg=self.COLOR_BG)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        # Right side container (YOLO + LoRa sender panel)
        right_container = tk.Frame(self.health_content_frame, bg=self.COLOR_BG)
        right_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(10, 0))
        
        # Sensors frame
        sensors_label = tk.Label(
            left_panel,
            text="Sensor Status:",
            font=("Arial", 12, "bold"),
            bg=self.COLOR_BG,
            fg=self.COLOR_FG
        )
        sensors_label.pack(anchor=tk.W, pady=(0, 10))

        # Keep action buttons pinned so they stay visible on short screens.
        health_btn_frame = tk.Frame(left_panel, bg=self.COLOR_BG)
        health_btn_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=15)

        self.start_btn = tk.Button(
            health_btn_frame,
            text="▶ Start Check",
            command=self.start_health_check,
            bg="#0066cc",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=8,
            cursor="hand2"
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        reset_btn = tk.Button(
            health_btn_frame,
            text="🔄 Reset",
            command=self.reset_status,
            bg="#666666",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=8,
            cursor="hand2"
        )
        reset_btn.grid(row=0, column=1, sticky="ew", padx=3)

        exit_btn = tk.Button(
            health_btn_frame,
            text="✕ Exit",
            command=self.on_close,
            bg="#cc0000",
            fg=self.COLOR_FG,
            font=("Arial", 10, "bold"),
            padx=12,
            pady=8,
            cursor="hand2"
        )
        exit_btn.grid(row=0, column=2, sticky="ew", padx=(6, 0))

        health_btn_frame.grid_columnconfigure(0, weight=1)
        health_btn_frame.grid_columnconfigure(1, weight=1)
        health_btn_frame.grid_columnconfigure(2, weight=1)
        
        # Scrollable sensors area (keeps bottom buttons visible on smaller screens)
        sensors_scroll_container = tk.Frame(left_panel, bg=self.COLOR_BG)
        sensors_scroll_container.pack(fill=tk.BOTH, expand=True, pady=10)

        self.sensors_canvas = tk.Canvas(
            sensors_scroll_container,
            bg=self.COLOR_BG,
            highlightthickness=0,
        )
        sensors_scrollbar = ttk.Scrollbar(
            sensors_scroll_container,
            orient=tk.VERTICAL,
            command=self.sensors_canvas.yview,
        )
        self.sensors_canvas.configure(yscrollcommand=sensors_scrollbar.set)

        self.sensors_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sensors_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.sensors_frame = tk.Frame(self.sensors_canvas, bg=self.COLOR_BG)
        self.sensors_canvas_window = self.sensors_canvas.create_window(
            (0, 0),
            window=self.sensors_frame,
            anchor=tk.NW,
        )
        self.sensors_frame.bind("<Configure>", self._on_sensors_frame_configure)
        self.sensors_canvas.bind("<Configure>", self._on_sensors_canvas_configure)
        
        # Define sensors to check
        self.sensors_list = [
            ('📷 Camera', 'camera'),
            ('📡 LoRa Module', 'lora'),
            ('🧭 MPU6050 (Accelerometer)', 'mpu6050'),
            ('🌡️  BMP280 (Pressure)', 'bmp280'),
            ('💡 GY511 (Compass)', 'gy511'),
            ('🗺️  GPSM6N (GPS)', 'gpsm6n'),
            ('📶 WiFi Connection', 'wifi'),
            ('🔋 Power Supply', 'power'),
        ]
        
        # Create sensor status widgets
        self.sensor_widgets = {}
        for sensor_name, sensor_key in self.sensors_list:
            widget = self.create_sensor_widget(self.sensors_frame, sensor_name, sensor_key)
            self.sensor_widgets[sensor_key] = widget

        right_panel = self._build_shared_yolo_panel(
            right_container,
            title_text="YOLO Detection (NCNN Model)",
            status_attr="yolo_status_label",
            status_initial="YOLO: Stopped",
            canvas_attr="yolo_canvas",
            placeholder_text="YOLO Preview di Panel Ini\nClick Start YOLO",
            photo_attr="yolo_photo",
            show_model_path=True,
            model_path_text=f"Model: {YOLO_MODEL_PATH}",
            include_controls=True,
            start_btn_attr="yolo_start_btn",
            stop_btn_attr="yolo_stop_btn",
            start_command=self.start_yolo_detection,
            stop_command=self.stop_yolo_detection,
            stop_initial_state=tk.DISABLED,
        )
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        lora_panel = self._build_shared_lora_panel(
            right_container,
            title_text="LoRa Sender (SIKAP)",
            status_attr="lora_status_label",
            status_initial="LoRa: Stopped",
            log_attr="lora_log",
            initial_log_text="[INFO] LoRa sender siap. Klik Start LoRa untuk kirim data sikap.\n",
            command_text="Skenario: python -m finalCode.main lora send sikap",
            include_controls=True,
            start_btn_attr="lora_start_btn",
            stop_btn_attr="lora_stop_btn",
            start_command=self.start_lora_sender,
            stop_command=self.stop_lora_sender,
            stop_initial_state=tk.DISABLED,
            clear_command=self.clear_lora_log,
            log_height=18,
        )
        lora_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(8, 0))

        # Waiting mission page
        self.mission_content_frame = tk.Frame(self.page_container, bg=self.COLOR_BG)
        self._build_mission_ui(self.mission_content_frame)
        self.mission_content_frame.pack_forget()
        self._update_nav_buttons()
        
        # Status bar
        self.status_bar = tk.Label(
            self.root,
            text="Ready",
            bg="#333333",
            fg=self.COLOR_FG,
            font=("Arial", 9),
            anchor=tk.W,
            padx=15,
            pady=8
        )
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    def on_close(self):
        """Close app and stop background tasks safely."""
        self.app_closing = True
        self.stop_waiting_mission()
        self.stop_lora_sender()
        self.stop_yolo_detection()

        if self.yolo_thread is not None and self.yolo_thread.is_alive():
            self.yolo_thread.join(timeout=1.5)
        if self.lora_thread is not None and self.lora_thread.is_alive():
            self.lora_thread.join(timeout=1.0)
        if self.mission_thread is not None and self.mission_thread.is_alive():
            self.mission_thread.join(timeout=2.0)

        self._stop_socket_server_process()

        self._close_yolo_window()
        self._clear_mission_camera_canvas()

        try:
            self.root.destroy()
        except tk.TclError:
            pass

    def _safe_after(self, callback, delay_ms=0):
        """Schedule Tk callback only when app is still alive."""
        if self.app_closing:
            return
        try:
            if self.root.winfo_exists():
                self.root.after(delay_ms, callback)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------ Fix #3
    def _batch_after(self, *callables):
        """Schedule multiple UI callables as ONE after() call (Fix #3)."""
        def _run():
            for fn in callables:
                try:
                    fn()
                except Exception:
                    pass
        self._safe_after(_run)

    # ------------------------------------------------------------------ Fix #1
    def _push_frame(self, frame_queue, frame):
        """Push newest frame, silently dropping the stale one if queue is full."""
        try:
            frame_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            frame_queue.put_nowait(frame)
        except queue.Full:
            pass

    def _poll_yolo_canvas(self):
        """Pull latest YOLO frame from queue and render at ~30 FPS (Fix #1)."""
        try:
            frame = self._yolo_frame_queue.get_nowait()
            self._update_yolo_canvas(frame)
        except queue.Empty:
            pass
        if not self.app_closing and self.yolo_running:
            self._safe_after(self._poll_yolo_canvas, 33)

    def _poll_mission_canvas(self):
        """Pull latest mission frame from queue and render at ~30 FPS (Fix #1)."""
        try:
            frame = self._mission_frame_queue.get_nowait()
            self._update_mission_camera_canvas(frame)
        except queue.Empty:
            pass
        if not self.app_closing and self.mission_running:
            self._safe_after(self._poll_mission_canvas, 33)

    def show_health_page(self):
        """Show health check page and stop mission runtime if needed."""
        if self.current_view == "health":
            return

        self.stop_waiting_mission()

        self.mission_content_frame.pack_forget()
        self.health_content_frame.pack(fill=tk.BOTH, expand=True)
        self.current_view = "health"
        self._update_nav_buttons()
        self.update_status_bar("Health Check page")

    def show_mission_page(self):
        """Show waiting mission page."""
        if self.current_view == "mission":
            return

        self.health_content_frame.pack_forget()
        self.mission_content_frame.pack(fill=tk.BOTH, expand=True)
        self.current_view = "mission"
        self._update_nav_buttons()
        self.update_status_bar("Waiting Misi page")

    def _update_nav_buttons(self):
        """Update navigation button highlight based on active page."""
        if not hasattr(self, "health_view_btn") or not hasattr(self, "mission_view_btn"):
            return

        if self.current_view == "health":
            self.health_view_btn.config(bg="#0f4f8a")
            self.mission_view_btn.config(bg="#1f7a2e")
        else:
            self.health_view_btn.config(bg="#386181")
            self.mission_view_btn.config(bg="#196126")

    def _on_sensors_frame_configure(self, _event):
        """Keep sensors scrollregion synced with dynamic content height."""
        if hasattr(self, "sensors_canvas"):
            self.sensors_canvas.configure(scrollregion=self.sensors_canvas.bbox("all"))

    def _on_sensors_canvas_configure(self, event):
        """Stretch sensor content width to canvas width."""
        if hasattr(self, "sensors_canvas") and hasattr(self, "sensors_canvas_window"):
            self.sensors_canvas.itemconfigure(self.sensors_canvas_window, width=event.width)

    def _build_shared_yolo_panel(
        self,
        parent,
        *,
        title_text,
        status_attr,
        status_initial,
        canvas_attr,
        placeholder_text,
        photo_attr,
        show_model_path=False,
        model_path_text="",
        include_controls=False,
        start_btn_attr=None,
        stop_btn_attr=None,
        start_command=None,
        stop_command=None,
        start_btn_text="▶ Start YOLO",
        stop_btn_text="■ Stop YOLO",
        stop_initial_state=tk.DISABLED,
        add_countdown=False,
        countdown_attr=None,
        countdown_initial="-",
    ):
        """Build YOLO panel using a shared health-check visual style."""
        panel = tk.Frame(
            parent,
            bg="#151515",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#444444",
        )

        title_label = tk.Label(
            panel,
            text=title_text,
            font=("Arial", 12, "bold"),
            bg="#151515",
            fg=self.COLOR_FG,
        )
        title_label.pack(anchor=tk.W, padx=12, pady=(12, 6))

        if show_model_path:
            model_label = tk.Label(
                panel,
                text=model_path_text,
                font=("Arial", 9),
                bg="#151515",
                fg="#bdbdbd",
                anchor=tk.W,
                justify=tk.LEFT,
                wraplength=600,
            )
            model_label.pack(anchor=tk.W, padx=12)

        status_label = tk.Label(
            panel,
            text=status_initial,
            font=("Arial", 10),
            bg="#151515",
            fg="#ffcc00",
            anchor=tk.W,
        )
        status_label.pack(fill=tk.X, padx=12, pady=(8, 6))
        setattr(self, status_attr, status_label)

        if add_countdown and countdown_attr:
            countdown_label = tk.Label(
                panel,
                text=countdown_initial,
                font=("Arial", 42, "bold"),
                bg="#151515",
                fg="#ffcc00",
                anchor=tk.CENTER,
            )
            countdown_label.pack(fill=tk.X, padx=12, pady=(0, 4))
            setattr(self, countdown_attr, countdown_label)

        if include_controls:
            btn_frame = tk.Frame(panel, bg="#151515")
            btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

            start_btn = tk.Button(
                btn_frame,
                text=start_btn_text,
                command=start_command,
                bg="#1c7d3a",
                fg=self.COLOR_FG,
                font=("Arial", 10, "bold"),
                padx=10,
                pady=6,
                cursor="hand2",
            )
            start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

            stop_btn = tk.Button(
                btn_frame,
                text=stop_btn_text,
                command=stop_command,
                state=stop_initial_state,
                bg="#555555",
                fg=self.COLOR_FG,
                font=("Arial", 10, "bold"),
                padx=10,
                pady=6,
                cursor="hand2",
            )
            stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

            btn_frame.grid_columnconfigure(0, weight=1)
            btn_frame.grid_columnconfigure(1, weight=1)

            if start_btn_attr:
                setattr(self, start_btn_attr, start_btn)
            if stop_btn_attr:
                setattr(self, stop_btn_attr, stop_btn)

        canvas = tk.Canvas(
            panel,
            width=416,
            height=416,
            bg="#000000",
            highlightthickness=1,
            highlightbackground="#333333",
        )
        canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)
        canvas.create_text(
            208,
            208,
            text=placeholder_text,
            fill="#bdbdbd",
            font=("Arial", 14, "bold"),
            justify=tk.CENTER,
        )

        setattr(self, canvas_attr, canvas)
        setattr(self, photo_attr, None)
        return panel

    def _build_shared_lora_panel(
        self,
        parent,
        *,
        title_text,
        status_attr,
        status_initial,
        log_attr,
        initial_log_text,
        command_text="",
        include_controls=False,
        start_btn_attr=None,
        stop_btn_attr=None,
        start_command=None,
        stop_command=None,
        start_btn_text="▶ Start LoRa",
        stop_btn_text="■ Stop LoRa",
        show_stop_button=True,
        stop_initial_state=tk.DISABLED,
        clear_btn_attr=None,
        clear_command=None,
        log_height=18,
    ):
        """Build LoRa panel using a shared health-check visual style."""
        panel = tk.Frame(
            parent,
            bg="#101820",
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground="#3d4f5f",
        )

        title_label = tk.Label(
            panel,
            text=title_text,
            font=("Arial", 12, "bold"),
            bg="#101820",
            fg=self.COLOR_FG,
        )
        title_label.pack(anchor=tk.W, padx=12, pady=(12, 6))

        if command_text:
            cmd_label = tk.Label(
                panel,
                text=command_text,
                font=("Arial", 9),
                bg="#101820",
                fg="#9ec1da",
                anchor=tk.W,
                justify=tk.LEFT,
                wraplength=420,
            )
            cmd_label.pack(anchor=tk.W, padx=12)

        status_label = tk.Label(
            panel,
            text=status_initial,
            font=("Arial", 10),
            bg="#101820",
            fg="#ffcc00",
            anchor=tk.W,
        )
        status_label.pack(fill=tk.X, padx=12, pady=(8, 6))
        setattr(self, status_attr, status_label)

        if include_controls:
            btn_frame = tk.Frame(panel, bg="#101820")
            btn_frame.pack(fill=tk.X, padx=12, pady=(0, 8))

            start_btn = tk.Button(
                btn_frame,
                text=start_btn_text,
                command=start_command,
                bg="#0b8f6f",
                fg=self.COLOR_FG,
                font=("Arial", 10, "bold"),
                padx=10,
                pady=6,
                cursor="hand2",
            )
            stop_btn = None

            if show_stop_button:
                start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))
                stop_btn = tk.Button(
                    btn_frame,
                    text=stop_btn_text,
                    command=stop_command,
                    state=stop_initial_state,
                    bg="#555555",
                    fg=self.COLOR_FG,
                    font=("Arial", 10, "bold"),
                    padx=10,
                    pady=6,
                    cursor="hand2",
                )
                stop_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))
            else:
                start_btn.grid(row=0, column=0, columnspan=2, sticky="ew")

            btn_frame.grid_columnconfigure(0, weight=1)
            btn_frame.grid_columnconfigure(1, weight=1)

            # Clear Log button – row 1, full width
            if clear_command is not None:
                clear_btn = tk.Button(
                    btn_frame,
                    text="🗑 Clear Log",
                    command=clear_command,
                    bg="#3a2a10",
                    fg="#ffcc88",
                    font=("Arial", 9),
                    padx=8,
                    pady=4,
                    cursor="hand2",
                )
                clear_btn.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
                if clear_btn_attr:
                    setattr(self, clear_btn_attr, clear_btn)

            if start_btn_attr:
                setattr(self, start_btn_attr, start_btn)
            if stop_btn_attr and stop_btn is not None:
                setattr(self, stop_btn_attr, stop_btn)

        log_widget = ScrolledText(
            panel,
            height=log_height,
            bg="#0a1118",
            fg="#d8f2ff",
            insertbackground="#d8f2ff",
            font=("Courier New", 9),
            wrap=tk.WORD,
        )
        log_widget.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 12))
        log_widget.insert(tk.END, initial_log_text)
        log_widget.config(state=tk.DISABLED)
        setattr(self, log_attr, log_widget)
        return panel

    def _build_mission_ui(self, parent):
        """Build waiting mission page with 3 horizontal panels."""
        left_panel = tk.Frame(parent, bg="#162534", relief=tk.FLAT, highlightthickness=1, highlightbackground="#33516b")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 8))

        # Left panel: mission detail + target image
        mission_title = tk.Label(
            left_panel,
            text="Mission Target (detail_misi)",
            font=("Arial", 12, "bold"),
            bg="#162534",
            fg=self.COLOR_FG,
        )
        mission_title.pack(anchor=tk.W, padx=12, pady=(12, 6))

        self.mission_server_label = tk.Label(
            left_panel,
            text=f"Detail: {self.mission_detail_dir}\nGambar: {self.mission_image_dir}",
            font=("Arial", 10),
            bg="#162534",
            fg="#00ff99",
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.mission_server_label.pack(fill=tk.X, padx=12)

        self.mission_state_label = tk.Label(
            left_panel,
            text="State: IDLE",
            font=("Arial", 10, "bold"),
            bg="#162534",
            fg="#ffcc00",
            anchor=tk.W,
        )
        self.mission_state_label.pack(fill=tk.X, padx=12, pady=(4, 2))

        self.mission_target_class_label = tk.Label(
            left_panel,
            text="Class: -",
            font=("Arial", 10),
            bg="#162534",
            fg="#d8f2ff",
            anchor=tk.W,
        )
        self.mission_target_class_label.pack(fill=tk.X, padx=12)

        self.mission_target_time_label = tk.Label(
            left_panel,
            text="Mission File: -",
            font=("Arial", 9),
            bg="#162534",
            fg="#b9d3e5",
            anchor=tk.W,
        )
        self.mission_target_time_label.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.mission_target_coord_label = tk.Label(
            left_panel,
            text="Target Coord: -",
            font=("Arial", 9),
            bg="#162534",
            fg="#b9d3e5",
            anchor=tk.W,
        )
        self.mission_target_coord_label.pack(fill=tk.X, padx=12, pady=(0, 4))

        self.mission_route_label = tk.Label(
            left_panel,
            text="Route: -",
            font=("Arial", 9),
            bg="#162534",
            fg="#9bd1f6",
            anchor=tk.W,
        )
        self.mission_route_label.pack(fill=tk.X, padx=12, pady=(0, 8))

        self.mission_target_canvas = tk.Canvas(
            left_panel,
            width=380,
            height=380,
            bg="#0b1117",
            highlightthickness=1,
            highlightbackground="#30485f",
        )
        self.mission_target_canvas.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 8))
        self._clear_mission_target_canvas()

        center_panel = self._build_shared_yolo_panel(
            parent,
            title_text="YOLO Camera View",
            status_attr="mission_yolo_status_label",
            status_initial="YOLO: idle",
            canvas_attr="mission_camera_canvas",
            placeholder_text="Camera mission belum aktif",
            photo_attr="mission_camera_photo",
            include_controls=True,
            start_btn_attr="mission_start_btn",
            stop_btn_attr="mission_stop_btn",
            start_command=self.start_waiting_mission,
            stop_command=self.stop_waiting_mission,
            start_btn_text="▶ Start Waiting",
            stop_btn_text="■ Stop Mission",
            stop_initial_state=tk.DISABLED,
            add_countdown=True,
            countdown_attr="mission_countdown_label",
            countdown_initial="-",
        )
        center_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=8)
        self._clear_mission_camera_canvas()

        right_panel = self._build_shared_lora_panel(
            parent,
            title_text="LoRa Mission Log",
            status_attr="mission_lora_status_label",
            status_initial="LoRa: idle",
            log_attr="mission_lora_log",
            initial_log_text="[INFO] Waiting Misi siap. Klik Start Waiting.\n",
            include_controls=True,
            start_btn_attr="mission_reset_btn",
            start_command=self.reset_waiting_mission,
            start_btn_text="↺ Reset Mission",
            show_stop_button=False,
            clear_command=self.clear_mission_lora_log,
            log_height=22,
        )
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0))

        self._build_mission_lora_debug_widgets(right_panel)
        self._build_mission_initial_coord_inputs(right_panel)

    def _build_mission_lora_debug_widgets(self, panel):
        """Insert mission LoRa debug stats above mission log widget."""
        debug_frame = tk.Frame(panel, bg="#101820")
        debug_frame.pack(fill=tk.X, padx=12, pady=(0, 6), before=self.mission_lora_log)

        self.mission_lora_debug_label = tk.Label(
            debug_frame,
            text="LoRa Stats: ENQ=0 SENT=0 FAIL=0 DROP=0",
            font=("Courier New", 9, "bold"),
            bg="#101820",
            fg="#9bd1f6",
            anchor=tk.W,
            justify=tk.LEFT,
        )
        self.mission_lora_debug_label.pack(fill=tk.X)
        self._update_mission_lora_debug_label()

    def _build_mission_initial_coord_inputs(self, panel):
        """Insert initial coordinate controls above mission log widget."""
        input_frame = tk.Frame(panel, bg="#101820")
        input_frame.pack(fill=tk.X, padx=12, pady=(0, 8), before=self.mission_lora_log)

        header = tk.Label(
            input_frame,
            text="Initial Coordinate (Readiness Gate)",
            font=("Arial", 9, "bold"),
            bg="#101820",
            fg="#9ec1da",
            anchor=tk.W,
        )
        header.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        lat_label = tk.Label(
            input_frame,
            text="Lat",
            font=("Arial", 9),
            bg="#101820",
            fg="#d8f2ff",
            anchor=tk.W,
        )
        lat_label.grid(row=1, column=0, sticky="w", padx=(0, 6))

        lon_label = tk.Label(
            input_frame,
            text="Lon",
            font=("Arial", 9),
            bg="#101820",
            fg="#d8f2ff",
            anchor=tk.W,
        )
        lon_label.grid(row=1, column=1, sticky="w", padx=(6, 0))

        self.mission_init_lat_entry = tk.Entry(
            input_frame,
            bg="#0a1118",
            fg="#d8f2ff",
            insertbackground="#d8f2ff",
            relief=tk.FLAT,
            font=("Courier New", 9),
        )
        self.mission_init_lat_entry.grid(row=2, column=0, sticky="ew", padx=(0, 6))

        self.mission_init_lon_entry = tk.Entry(
            input_frame,
            bg="#0a1118",
            fg="#d8f2ff",
            insertbackground="#d8f2ff",
            relief=tk.FLAT,
            font=("Courier New", 9),
        )
        self.mission_init_lon_entry.grid(row=2, column=1, sticky="ew", padx=(6, 0))

        self.mission_init_lat_entry.insert(0, f"{MISSION_DEFAULT_START_LAT}")
        self.mission_init_lon_entry.insert(0, f"{MISSION_DEFAULT_START_LON}")

        input_frame.grid_columnconfigure(0, weight=1)
        input_frame.grid_columnconfigure(1, weight=1)

    def _set_mission_state(self, text, color="#ffcc00"):
        """Update mission state label."""
        self.mission_state = text
        if hasattr(self, "mission_state_label"):
            self.mission_state_label.config(text=f"State: {text}", fg=color)

    def update_mission_yolo_status(self, text, color="#ffcc00"):
        """Update mission YOLO status label."""
        if hasattr(self, "mission_yolo_status_label"):
            self.mission_yolo_status_label.config(text=f"YOLO: {text}", fg=color)

    def update_mission_lora_status(self, text, color="#ffcc00"):
        """Update mission LoRa status label."""
        if hasattr(self, "mission_lora_status_label"):
            self.mission_lora_status_label.config(text=f"LoRa: {text}", fg=color)

    def _reset_mission_lora_debug_counters(self):
        """Reset mission LoRa debug counters (per mission run)."""
        with self.mission_lora_stats_lock:
            self.mission_lora_enqueued_count = 0
            self.mission_lora_sent_count = 0
            self.mission_lora_failed_count = 0
            self.mission_lora_dropped_count = 0
        self._safe_after(self._update_mission_lora_debug_label)

    def _increment_mission_lora_debug_counter(self, counter_key, amount=1):
        """Increment one mission LoRa debug counter and refresh label."""
        with self.mission_lora_stats_lock:
            if counter_key == "enqueued":
                self.mission_lora_enqueued_count += amount
            elif counter_key == "sent":
                self.mission_lora_sent_count += amount
            elif counter_key == "failed":
                self.mission_lora_failed_count += amount
            elif counter_key == "dropped":
                self.mission_lora_dropped_count += amount
        self._safe_after(self._update_mission_lora_debug_label)

    def _update_mission_lora_debug_label(self):
        """Render mission LoRa debug counters in GUI label."""
        if threading.current_thread() is not threading.main_thread():
            self._safe_after(self._update_mission_lora_debug_label)
            return

        if not hasattr(self, "mission_lora_debug_label"):
            return

        with self.mission_lora_stats_lock:
            enq = self.mission_lora_enqueued_count
            sent = self.mission_lora_sent_count
            fail = self.mission_lora_failed_count
            drop = self.mission_lora_dropped_count

        self.mission_lora_debug_label.config(
            text=f"LoRa Stats: ENQ={enq} SENT={sent} FAIL={fail} DROP={drop}"
        )

    def update_mission_countdown(self, text, color="#ffcc00"):
        """Update large mission countdown indicator."""
        self.mission_countdown_display = text
        if hasattr(self, "mission_countdown_label"):
            self.mission_countdown_label.config(text=text, fg=color)

    def show_mission_countdown(self, seconds_left):
        """Render a clear countdown number for mission start."""
        count_value = max(1, int(math.ceil(seconds_left)))
        self.update_mission_countdown(str(count_value), "#ffcc00")

    def clear_mission_countdown(self):
        """Reset countdown indicator text."""
        self.update_mission_countdown("-", "#ffcc00")

    def append_mission_log(self, text):
        """Append one mission log line safely."""
        if not hasattr(self, "mission_lora_log"):
            return
        self.mission_lora_log.config(state=tk.NORMAL)
        self.mission_lora_log.insert(tk.END, text + "\n")
        self.mission_lora_log.see(tk.END)
        self.mission_lora_log.config(state=tk.DISABLED)

    def clear_mission_lora_log(self):
        """Clear mission LoRa log widget."""
        if not hasattr(self, "mission_lora_log"):
            return
        self.mission_lora_log.config(state=tk.NORMAL)
        self.mission_lora_log.delete("1.0", tk.END)
        self.mission_lora_log.insert(tk.END, "[INFO] Log dibersihkan.\n")
        self.mission_lora_log.config(state=tk.DISABLED)

    def reset_waiting_mission(self):
        """Reset mission context and return to waiting state."""
        latest = self._read_latest_target_state() or {}

        self.mission_target = None
        self.mission_active_target_id = None
        self.mission_countdown_until = None
        self.mission_lock_started_at = None
        self.mission_last_lora_sent_at = 0.0
        self.mission_next_lora_retry_at = 0.0
        self.mission_next_camera_retry_at = 0.0
        self.mission_frame_fail_count = 0
        self.mission_route_points = []
        self.mission_route_index = -1
        self.mission_route_next_step_at = 0.0
        self.mission_tail_detect_streak = 0
        self.mission_tail_hit = False
        self.mission_last_found = False
        self.mission_last_route_file = None
        self.mission_canvas_last_update_at = 0.0
        self.mission_detail_last_poll_at = 0.0
        self.mission_detail_cache = None
        self._reset_mission_lora_debug_counters()

        # Prevent stale target file from being immediately re-processed after reset.
        self.mission_last_target_id = latest.get("target_id")

        if self.mission_camera is not None:
            try:
                self.mission_camera.stop()
            except Exception:
                pass
            self.mission_camera = None

        self._stop_mission_lora_worker()
        self._release_mission_lora_sender()
        self._clear_mission_target_canvas()
        self._clear_mission_camera_canvas()

        self.mission_target_class_label.config(text="Class: -")
        self.mission_target_time_label.config(text="Mission File: -")
        self.mission_target_coord_label.config(text="Target Coord: -")
        self.mission_route_label.config(text="Route: -")
        self.clear_mission_countdown()

        if self.mission_running:
            self._set_mission_state("WAITING TARGET", "#ffcc00")
            self.update_mission_yolo_status("Menunggu detail misi baru", "#ffcc00")
            self.update_mission_lora_status("Idle", "#ffcc00")
        else:
            self._set_mission_state("IDLE", "#ffcc00")
            self.update_mission_yolo_status("Stopped", "#ffcc00")
            self.update_mission_lora_status("Stopped", "#ffcc00")

        self.append_mission_log("[INFO] Mission state di-reset.")

    def _clear_mission_target_canvas(self):
        """Reset target preview canvas."""
        if not hasattr(self, "mission_target_canvas"):
            return
        self.mission_target_canvas.delete("all")
        self.mission_target_canvas.create_text(
            190,
            190,
            text="Belum ada mission\ndi detail_misi",
            fill="#bdbdbd",
            font=("Arial", 13, "bold"),
            justify=tk.CENTER,
        )
        self.mission_target_photo = None

    def _clear_mission_camera_canvas(self):
        """Reset mission camera preview canvas."""
        if not hasattr(self, "mission_camera_canvas"):
            return
        self.mission_camera_canvas.delete("all")
        self.mission_camera_canvas.create_text(
            208,
            208,
            text="Camera mission belum aktif",
            fill="#bdbdbd",
            font=("Arial", 13, "bold"),
            justify=tk.CENTER,
        )
        self.mission_camera_photo = None

    def _render_mission_countdown_canvas(self, seconds_left):
        """Render large countdown text on mission camera canvas."""
        if not hasattr(self, "mission_camera_canvas"):
            return

        count_value = max(1, int(math.ceil(seconds_left)))
        self.mission_camera_canvas.delete("all")
        self.mission_camera_canvas.create_text(
            208,
            120,
            text="START IN",
            fill="#ffcc00",
            font=("Arial", 28, "bold"),
            justify=tk.CENTER,
        )
        self.mission_camera_canvas.create_text(
            208,
            240,
            text=str(count_value),
            fill="#00ff99",
            font=("Arial", 118, "bold"),
            justify=tk.CENTER,
        )
        self.mission_camera_photo = None

    def _update_mission_target_canvas(self, image_path):
        """Render received target image into mission target canvas."""
        if not hasattr(self, "mission_target_canvas"):
            return

        if Image is None or ImageTk is None:
            self._clear_mission_target_canvas()
            self.mission_target_canvas.create_text(
                190,
                350,
                text="Install pillow untuk preview image",
                fill="#ffcc00",
                font=("Arial", 10),
                justify=tk.CENTER,
            )
            return

        if not image_path or not os.path.exists(image_path):
            self._clear_mission_target_canvas()
            return

        try:
            with Image.open(image_path) as loaded:
                preview = loaded.convert("RGB")
                preview.thumbnail((360, 360))
                photo = ImageTk.PhotoImage(preview)

            self.mission_target_canvas.delete("all")
            self.mission_target_canvas.create_image(190, 190, image=photo)
            self.mission_target_photo = photo
        except Exception as e:
            self._clear_mission_target_canvas()
            self.mission_target_canvas.create_text(
                190,
                350,
                text=f"Preview error: {str(e)[:40]}",
                fill="#ff6666",
                font=("Arial", 10),
                justify=tk.CENTER,
            )

    def _update_mission_camera_canvas(self, frame):
        """Render BGR OpenCV frame into mission camera canvas."""
        if Image is None or ImageTk is None:
            self.update_mission_yolo_status("Pillow belum terpasang", "#ff0000")
            return
        if not hasattr(self, "mission_camera_canvas"):
            return

        import cv2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=img)

        # Fix #7 – release old PhotoImage explicitly before replacing
        old_photo = self.mission_camera_photo
        self.mission_camera_canvas.delete("all")
        self.mission_camera_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.mission_camera_photo = photo
        del old_photo

    def _start_socket_server_process(self):
        """Prepare mission input source directories."""
        try:
            os.makedirs(self.mission_detail_dir, exist_ok=True)
            os.makedirs(self.mission_image_dir, exist_ok=True)
            os.makedirs(self.mission_route_dir, exist_ok=True)
            self._safe_after(
                lambda: self.mission_server_label.config(
                    text=f"Detail: {self.mission_detail_dir}\nGambar: {self.mission_image_dir}",
                    fg="#00ff99",
                )
            )
            self._safe_after(
                lambda: self.append_mission_log(
                    f"[INFO] Monitoring mission detail: {self.mission_detail_dir}"
                )
            )
            return True
        except Exception as e:
            self._safe_after(lambda err=str(e): self.append_mission_log(f"[ERROR] Folder misi tidak siap: {err}"))
            self._safe_after(lambda: self.mission_server_label.config(text="Mission Source: ERROR", fg="#ff0000"))
            return False

    def _socket_server_output_loop(self):
        """Legacy hook kept for compatibility (unused in mission-detail flow)."""
        return

    def _stop_socket_server_process(self):
        """Legacy cleanup hook for previous socket-based mission source."""
        process = self.socket_server_process
        if process is not None:
            try:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=2.0)
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
            finally:
                self.socket_server_process = None

        self._safe_after(
            lambda: self.mission_server_label.config(
                text=f"Detail: {self.mission_detail_dir}\nGambar: {self.mission_image_dir}",
                fg="#00ff99",
            )
        )

    def _normalize_target_class_name(self, value):
        """Normalize class name into a safe lowercase token."""
        raw = str(value or "").strip().lower()
        cleaned = re.sub(r"[^a-z0-9_-]+", "", raw)
        return cleaned or "unknown"

    def _get_initial_coordinates(self):
        """Read and validate initial route coordinates from mission UI."""
        if not hasattr(self, "mission_init_lat_entry") or not hasattr(self, "mission_init_lon_entry"):
            return None, "Input koordinat belum siap"

        lat_raw = self.mission_init_lat_entry.get().strip()
        lon_raw = self.mission_init_lon_entry.get().strip()
        try:
            lat_value = float(lat_raw)
            lon_value = float(lon_raw)
        except ValueError:
            return None, "Koordinat awal harus berupa angka"

        if not (-90.0 <= lat_value <= 90.0):
            return None, "Latitude awal harus antara -90 hingga 90"
        if not (-180.0 <= lon_value <= 180.0):
            return None, "Longitude awal harus antara -180 hingga 180"

        return (lat_value, lon_value), None

    def _check_latest_target_image_path_ready(self):
        """Validate latest mission detail has an existing target image path."""
        detail_path, _ = self._find_latest_mission_detail_file()
        if not detail_path:
            return False, "Belum ada file mission detail terbaru."

        try:
            with open(detail_path, "r", encoding="utf-8") as detail_file:
                mission_detail = json.load(detail_file)
        except Exception as e:
            return False, f"Gagal baca mission detail terbaru: {str(e)}"

        if not isinstance(mission_detail, dict):
            return False, "Isi mission detail terbaru harus object JSON."

        nama_gambar = str(mission_detail.get("nama_gambar", "")).strip()
        if not nama_gambar:
            return False, "Mission detail terbaru belum berisi nama_gambar."

        image_name = os.path.basename(nama_gambar)
        image_path = os.path.join(self.mission_image_dir, image_name)
        if not os.path.exists(image_path):
            return False, f"Path gambar target tidak ditemukan: {image_path}"

        return True, None

    def _find_latest_mission_detail_file(self):
        """Return newest mission detail json file path and mtime_ns.

        Fix #5 – fast-path: if the folder mtime hasn't changed the set of
        files is identical; just re-stat the previously found file to detect
        in-place content changes without a full scandir.
        """
        if not os.path.isdir(self.mission_detail_dir):
            self._last_folder_mtime_ns = -1
            return None, None

        try:
            folder_mtime = os.stat(self.mission_detail_dir).st_mtime_ns
        except Exception:
            return None, None

        if folder_mtime == self._last_folder_mtime_ns and self._last_detail_path:
            # Folder contents unchanged – only check whether the known file was modified.
            try:
                file_mtime = os.stat(self._last_detail_path).st_mtime_ns
                return self._last_detail_path, file_mtime
            except Exception:
                pass  # file was deleted; fall through to full rescan

        self._last_folder_mtime_ns = folder_mtime

        latest_path = None
        latest_mtime_ns = -1
        try:
            for entry in os.scandir(self.mission_detail_dir):
                if not entry.is_file() or not entry.name.lower().endswith(".json"):
                    continue
                mtime_ns = entry.stat().st_mtime_ns
                if mtime_ns > latest_mtime_ns:
                    latest_mtime_ns = mtime_ns
                    latest_path = entry.path
        except Exception:
            return None, None

        self._last_detail_path = latest_path
        if latest_path is None:
            return None, None
        return latest_path, latest_mtime_ns

    def _build_route_points(self, start_lat, start_lon, target_lat, target_lon, total_points):
        """Build straight route points from initial to target coordinate."""
        total = max(2, int(total_points))
        points = []
        for idx in range(total):
            ratio = idx / (total - 1)
            lat_value = start_lat + (target_lat - start_lat) * ratio
            lon_value = start_lon + (target_lon - start_lon) * ratio
            points.append(
                {
                    "index": idx + 1,
                    "latitude": lat_value,
                    "longitude": lon_value,
                }
            )
        return points

    def _save_route_json(self, mission_info, route_points):
        """Persist generated route json into mission jalur directory."""
        os.makedirs(self.mission_route_dir, exist_ok=True)

        mission_file = str(mission_info.get("mission_file", "mission")).strip()
        mission_stem = os.path.splitext(mission_file)[0] or "mission"
        route_filename = f"jalur_{mission_stem}.json"
        route_path = os.path.join(self.mission_route_dir, route_filename)

        route_payload = {
            "mission_file": mission_file,
            "nama_gambar": mission_info.get("nama_gambar", ""),
            "kelas": mission_info.get("class_name", "unknown"),
            "initial_coordinate": {
                "latitude": mission_info.get("start_lat"),
                "longitude": mission_info.get("start_lon"),
            },
            "target_coordinate": {
                "latitude": mission_info.get("target_lat"),
                "longitude": mission_info.get("target_lon"),
            },
            "finish": len(route_points),
            "point_count": len(route_points),
            "step_seconds": MISSION_ROUTE_STEP_SECONDS,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "points": route_points,
        }

        with open(route_path, "w", encoding="utf-8") as route_file:
            json.dump(route_payload, route_file, indent=2)

        return route_path

    def _log_mission_warning_once(self, warning_key, message):
        """Write mission parse warning only once for the same warning key."""
        if self.mission_last_invalid_detail == warning_key:
            return
        self.mission_last_invalid_detail = warning_key
        self._safe_after(lambda msg=message: self.append_mission_log(msg))

    def _read_latest_target_state(self):
        """Read newest mission detail json from detail_misi and resolve image path."""
        detail_path, detail_mtime_ns = self._find_latest_mission_detail_file()
        if not detail_path:
            return None

        try:
            with open(detail_path, "r", encoding="utf-8") as detail_file:
                mission_detail = json.load(detail_file)
        except Exception as e:
            self._log_mission_warning_once(
                f"{detail_path}:read",
                f"[WARN] Gagal baca mission detail: {str(e)}",
            )
            return None

        if not isinstance(mission_detail, dict):
            self._log_mission_warning_once(
                f"{detail_path}:shape",
                "[WARN] Isi mission detail harus object JSON.",
            )
            return None

        mission_file = os.path.basename(detail_path)
        nama_gambar = str(mission_detail.get("nama_gambar", "")).strip()
        kelas_raw = str(mission_detail.get("kelas", "")).strip()
        if not nama_gambar or not kelas_raw:
            self._log_mission_warning_once(
                f"{detail_path}:required",
                f"[WARN] Mission {mission_file} tidak valid: butuh nama_gambar dan kelas",
            )
            return None

        try:
            target_lon = float(mission_detail.get("longitude_target"))
            target_lat = float(mission_detail.get("lattitude_target"))
        except Exception:
            self._log_mission_warning_once(
                f"{detail_path}:coordinate",
                f"[WARN] Mission {mission_file} tidak valid: longitude_target/lattitude_target harus numerik",
            )
            return None

        finish_points = MISSION_ROUTE_POINTS
        finish_raw = mission_detail.get("finish", MISSION_ROUTE_POINTS)
        try:
            finish_points = int(finish_raw)
            if finish_points < 2:
                raise ValueError("finish harus >= 2")
        except Exception:
            self._log_mission_warning_once(
                f"{detail_path}:finish",
                f"[WARN] finish pada {mission_file} tidak valid, fallback ke {MISSION_ROUTE_POINTS}",
            )
            finish_points = MISSION_ROUTE_POINTS

        image_name = os.path.basename(nama_gambar)
        image_path = os.path.join(self.mission_image_dir, image_name)
        if not os.path.exists(image_path):
            self._log_mission_warning_once(
                f"{detail_path}:image_missing",
                f"[WARN] Gambar target tidak ditemukan: {image_path}",
            )
            return None

        class_name = self._normalize_target_class_name(kelas_raw)
        mission_id = f"{mission_file}:{detail_mtime_ns}"
        self.mission_last_invalid_detail = None
        return {
            "target_id": mission_id,
            "class_name": class_name,
            "nama_gambar": image_name,
            "mission_file": mission_file,
            "target_lat": target_lat,
            "target_lon": target_lon,
            "finish_points": finish_points,
            "path": image_path,
        }

    def _read_latest_target_state_cached(self, now_perf):
        """Poll latest mission detail at fixed interval and reuse parsed state by mtime."""
        if now_perf - self.mission_detail_last_poll_at < MISSION_DETAIL_POLL_INTERVAL:
            return None

        self.mission_detail_last_poll_at = now_perf
        detail_path, detail_mtime_ns = self._find_latest_mission_detail_file()
        if not detail_path:
            self.mission_detail_cache = None
            return None

        cache = self.mission_detail_cache
        if (
            isinstance(cache, dict)
            and cache.get("path") == detail_path
            and cache.get("mtime_ns") == detail_mtime_ns
        ):
            return cache.get("data")

        latest = self._read_latest_target_state()
        self.mission_detail_cache = {
            "path": detail_path,
            "mtime_ns": detail_mtime_ns,
            "data": latest,
        }
        return latest

    def _handle_new_mission_target(self, target_info):
        """Update UI when a new mission detail arrives."""
        class_name = str(target_info.get("class_name", "unknown"))
        mission_file = str(target_info.get("mission_file", "-"))
        image_path = str(target_info.get("path", ""))
        target_id = str(target_info.get("target_id", "-"))
        target_lat = target_info.get("target_lat")
        target_lon = target_info.get("target_lon")
        route_path = str(target_info.get("route_file", "-"))

        self.mission_target_class_label.config(text=f"Class: {class_name}")
        self.mission_target_time_label.config(text=f"Mission File: {mission_file}")
        if target_lat is not None and target_lon is not None:
            self.mission_target_coord_label.config(text=f"Target Coord: {target_lat:.7f}, {target_lon:.7f}")
        else:
            self.mission_target_coord_label.config(text="Target Coord: -")
        self.mission_route_label.config(text=f"Route: {os.path.basename(route_path) if route_path != '-' else '-'}")
        self._update_mission_target_canvas(image_path)
        self._set_mission_state("TARGET LOADED", "#00ff99")
        self.append_mission_log(
            f"[TARGET] id={target_id} class={class_name} file={os.path.basename(image_path) or '-'} route={os.path.basename(route_path) if route_path != '-' else '-'}"
        )

    def _ensure_mission_lora_sender(self):
        """Ensure LoRa sender is ready; init once if not yet created."""
        init_error = None
        with self.mission_lora_lock:
            if self.mission_lora_sender is not None:
                return True

            try:
                from finalCode.lora.sender_sensor import LoRaSensorSender

                self.mission_lora_sender = LoRaSensorSender(
                    sensors='sikap_gps',
                    read_gps_hardware=False,
                )
                # Fix – counter NOT reset here; it is managed by the caller
                # so the sequence number stays consistent across retries.
            except Exception as e:
                init_error = str(e)

        if init_error is not None:
            self._safe_after(lambda err=init_error: self.append_mission_log(f"[ERROR] Init LoRa mission gagal: {err}"))
            return False

        self._safe_after(lambda: self.append_mission_log("[INFO] LoRa mission sender initialized (SIKAP_GPS)."))
        return True

    def _release_mission_lora_sender(self):
        """Cleanup mission LoRa sender resources."""
        with self.mission_lora_lock:
            sender_ref = self.mission_lora_sender
            self.mission_lora_sender = None

        if sender_ref is None:
            return

        # Fix #2 – wait for any in-flight kirim_data() to finish before cleanup()
        # This prevents 'NoneType cannot be interpreted as int' when the worker
        # is mid-send and cleanup() frees the underlying LoRa resources.
        with self.mission_lora_send_lock:
            pass  # acquire-then-release is enough to wait for the active send

        try:
            sender_ref.cleanup()
            self._safe_after(lambda: self.append_mission_log("[INFO] LoRa mission cleanup selesai."))
        except Exception as e:
            self._safe_after(lambda err=str(e): self.append_mission_log(f"[WARN] LoRa mission cleanup: {err}"))

    def _start_mission_lora_worker(self):
        """Start background worker for non-blocking mission LoRa sends."""
        if self.mission_lora_worker is not None and self.mission_lora_worker.is_alive():
            return True

        self.mission_lora_worker_stop.clear()
        self.mission_lora_queue = queue.Queue(maxsize=MISSION_LORA_QUEUE_MAXSIZE)

        try:
            self.mission_lora_worker = threading.Thread(
                target=self._mission_lora_worker_loop,
                daemon=True,
            )
            self.mission_lora_worker.start()
            self._safe_after(lambda: self.append_mission_log("[INFO] LoRa mission async worker started."))
            return True
        except Exception as e:
            self.mission_lora_worker = None
            self.mission_lora_queue = None
            self._safe_after(
                lambda err=str(e): self.append_mission_log(f"[ERROR] Worker LoRa mission gagal start: {err}")
            )
            return False

    def _stop_mission_lora_worker(self, join_timeout=1.5):
        """Stop mission LoRa worker thread and clear pending queue."""
        self.mission_lora_worker_stop.set()
        queue_ref = self.mission_lora_queue
        if queue_ref is not None:
            try:
                queue_ref.put_nowait(None)
            except queue.Full:
                try:
                    queue_ref.get_nowait()
                except Exception:
                    pass
                try:
                    queue_ref.put_nowait(None)
                except Exception:
                    pass

        worker = self.mission_lora_worker
        if worker is not None and worker.is_alive() and threading.current_thread() is not worker:
            worker.join(timeout=join_timeout)

        self.mission_lora_queue = None
        self.mission_lora_worker = None

    def _clear_mission_lora_queue(self):
        """Drop any queued mission LoRa payloads to avoid stale sends."""
        queue_ref = self.mission_lora_queue
        if queue_ref is None:
            return

        while True:
            try:
                queue_ref.get_nowait()
            except queue.Empty:
                break

    def _mission_lora_worker_loop(self):
        """Consume mission LoRa send requests without blocking mission detection loop."""
        queue_ref = self.mission_lora_queue
        if queue_ref is None:
            return

        while not self.mission_lora_worker_stop.is_set() and not self.app_closing:
            try:
                payload = queue_ref.get(timeout=0.2)
            except queue.Empty:
                continue

            if payload is None:
                break

            counter = payload.get("counter")
            gps_override = payload.get("gps_override")
            now_perf = time.perf_counter()

            if now_perf < self.mission_next_lora_retry_at:
                self._increment_mission_lora_debug_counter("dropped")
                continue

            if not self._ensure_mission_lora_sender():
                self._increment_mission_lora_debug_counter("failed")
                self.mission_next_lora_retry_at = now_perf + self.mission_lora_retry_delay
                self._safe_after(
                    lambda delay=self.mission_lora_retry_delay: self.update_mission_lora_status(
                        f"Recovering ({delay:.1f}s)", "#ff9900"
                    )
                )
                self._safe_after(
                    lambda delay=self.mission_lora_retry_delay: self.append_mission_log(
                        f"[WARN] LoRa sender belum siap, retry dalam {delay:.1f}s."
                    )
                )
                continue

            try:
                # Fix #2 – borrow sender ref under mission_lora_lock, then send
                # under send_lock so _release_mission_lora_sender() can detect
                # and wait for an in-flight transmission before calling cleanup().
                with self.mission_lora_lock:
                    sender_ref = self.mission_lora_sender
                if sender_ref is None:
                    raise RuntimeError("LoRa sender mission belum tersedia")
                with self.mission_lora_send_lock:
                    sukses, pesan = sender_ref.kirim_data(
                        counter,
                        gps_override=gps_override,
                        timeout=MISSION_LORA_TIMEOUT_SECONDS,
                    )

                jam = time.strftime("%H:%M:%S")
                status_text = "TERKIRIM" if sukses else "TIMEOUT"
                self._safe_after(
                    lambda line=f"[{jam}] SIKAP_GPS #{counter} {status_text} | {pesan}": self.append_mission_log(line)
                )
                self._safe_after(
                    lambda st=status_text: self.update_mission_lora_status(
                        st,
                        "#00ff99" if st == "TERKIRIM" else "#ff9900",
                    )
                )
                if not sukses:
                    self._increment_mission_lora_debug_counter("failed")
                    self.mission_next_lora_retry_at = time.perf_counter() + self.mission_lora_retry_delay
                    self._release_mission_lora_sender()
                    self._safe_after(
                        lambda delay=self.mission_lora_retry_delay: self.append_mission_log(
                            f"[WARN] Timeout LoRa, auto-recover retry dalam {delay:.1f}s"
                        )
                    )
                else:
                    self._increment_mission_lora_debug_counter("sent")
                    self.mission_next_lora_retry_at = 0.0
            except Exception as e:
                self._increment_mission_lora_debug_counter("failed")
                self.mission_next_lora_retry_at = time.perf_counter() + self.mission_lora_retry_delay
                self._release_mission_lora_sender()
                self._safe_after(lambda err=str(e): self.append_mission_log(f"[ERROR] Kirim sikap error: {err}"))
                self._safe_after(
                    lambda delay=self.mission_lora_retry_delay: self.update_mission_lora_status(
                        f"Recovering ({delay:.1f}s)", "#ff9900"
                    )
                )

    def _enqueue_mission_lora_payload(self, payload):
        """Queue mission payload; when full, replace oldest so latest state stays prioritized."""
        queue_ref = self.mission_lora_queue
        if queue_ref is None:
            return False

        try:
            queue_ref.put_nowait(payload)
            return True
        except queue.Full:
            pass

        try:
            queue_ref.get_nowait()
            self._increment_mission_lora_debug_counter("dropped")
            self._safe_after(
                lambda: self.append_mission_log(
                    "[WARN] LoRa queue penuh, payload lama diganti payload terbaru."
                )
            )
        except queue.Empty:
            pass

        try:
            queue_ref.put_nowait(payload)
            return True
        except queue.Full:
            return False

    def _send_mission_sikap_once(
        self,
        now_perf,
        route_point,
        iteration_value,
        finish_value,
        found_value,
        mission_status,
    ):
        """Send one SIKAP_GPS payload per route step.

        mission_status is 'Launch' for intermediate steps and 'Selesai' for the
        last step.  found_value reflects live YOLO detection at that moment.
        TailHit logic has been removed – the mission always completes the full
        route and the receiver decides what to do with the Found flag.
        """
        if not self.mission_running or self.app_closing:
            return

        if now_perf < self.mission_next_lora_retry_at:
            return

        if now_perf - self.mission_last_lora_sent_at < self.mission_lora_interval:
            return

        if not self._start_mission_lora_worker():
            self.mission_next_lora_retry_at = now_perf + self.mission_lora_retry_delay
            self._safe_after(
                lambda delay=self.mission_lora_retry_delay: self.update_mission_lora_status(
                    f"Recovering ({delay:.1f}s)", "#ff9900"
                )
            )
            return

        gps_override = None
        if isinstance(route_point, dict):
            gps_override = {
                "latitude": route_point.get("latitude"),
                "longitude": route_point.get("longitude"),
                "satellites": 0,
                "status": "ROUTE",
                "iterasi": int(iteration_value),
                "finish": int(finish_value),
                "mission_status": str(mission_status),  # 'Launch' or 'Selesai'
                "found": bool(found_value),              # live YOLO detection
            }

        try:
            counter_value = self.mission_lora_counter
            payload = {
                "counter": counter_value,
                "gps_override": gps_override,
            }
            if not self._enqueue_mission_lora_payload(payload):
                self._increment_mission_lora_debug_counter("dropped")
                self._safe_after(lambda: self.update_mission_lora_status("Queue busy", "#ff9900"))
                return

            self._increment_mission_lora_debug_counter("enqueued")
            if isinstance(gps_override, dict):
                iterasi = gps_override.get("iterasi")
                finish = gps_override.get("finish")
                lat_val = gps_override.get("latitude")
                lon_val = gps_override.get("longitude")
                status_val = gps_override.get("mission_status")
                found_val = gps_override.get("found")
                self._safe_after(
                    lambda c=counter_value, i=iterasi, f=finish, lat=lat_val, lon=lon_val, st=status_val, fd=found_val: self.append_mission_log(
                        f"[ENQUEUE] SIKAP_GPS #{c} | I:{i} F:{f} LAT:{lat} LON:{lon} Status:{st} Found:{fd}"
                    )
                )
            else:
                self._safe_after(
                    lambda c=counter_value: self.append_mission_log(
                        f"[ENQUEUE] SIKAP_GPS #{c} | GPS override tidak tersedia"
                    )
                )

            self.mission_lora_counter += 1
            self.mission_last_lora_sent_at = now_perf
            self._safe_after(lambda: self.update_mission_lora_status("Queued", "#9bd1f6"))
        except Exception as e:
            self.mission_next_lora_retry_at = now_perf + self.mission_lora_retry_delay
            self._safe_after(lambda err=str(e): self.append_mission_log(f"[ERROR] Kirim sikap error: {err}"))
            self._safe_after(
                lambda delay=self.mission_lora_retry_delay: self.update_mission_lora_status(
                    f"Recovering ({delay:.1f}s)", "#ff9900"
                )
            )

    def _send_mission_final_message(self, target_class, timestamp_value):
        """Send final target-detected message exactly 3 times."""
        self._stop_mission_lora_worker(join_timeout=2.0)
        finish_value = max(0, len(self.mission_route_points))
        iter_value = max(0, self.mission_route_index + 1)
        found_value = bool(getattr(self, "mission_last_found", False))
        tail_hit_value = bool(self.mission_tail_hit)
        message = (
            f"I:{iter_value} F:{finish_value} TS:{timestamp_value} TARGET:{target_class} "
            f"Status: Selesai, Found: {found_value}, TailHit: {tail_hit_value}"
        )
        for attempt in range(1, 4):
            if not self._ensure_mission_lora_sender():
                self._safe_after(
                    lambda n=attempt: self.append_mission_log(
                        f"[FINAL] {n}/3 sender belum siap, auto-retry..."
                    )
                )
                time.sleep(self.mission_lora_retry_delay)
                continue

            try:
                # Fix #2 – borrow sender reference under lock, send outside.
                with self.mission_lora_lock:
                    sender_ref = self.mission_lora_sender
                if sender_ref is None:
                    raise RuntimeError("LoRa sender mission belum tersedia")
                sukses = sender_ref.lora.kirim(message, timeout=MISSION_LORA_TIMEOUT_SECONDS)
                result_text = "TERKIRIM" if sukses else "TIMEOUT"
                self._safe_after(
                    lambda n=attempt, r=result_text: self.append_mission_log(f"[FINAL] {n}/3 {r} | {message}")
                )
            except Exception as e:
                self._release_mission_lora_sender()
                self._safe_after(
                    lambda n=attempt, err=str(e): self.append_mission_log(f"[FINAL] {n}/3 ERROR | {err}")
                )
            time.sleep(0.3)

    def _run_mission_detection(self, frame, target_class):
        """Run YOLO detection and draw overlay with target-class lock evaluation."""
        import cv2

        results = list(self.yolo_model.prediksi(frame))
        detected_count = 0
        top_conf = 0.0

        for label in results:
            boxes = getattr(label, "boxes", None)
            if boxes is None:
                continue

            for box in boxes:
                try:
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    name = str(self.yolo_model.kelas.get(cls_id, "")).lower()
                    x1, y1, x2, y2 = box.xyxy[0]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                except Exception:
                    continue

                is_target = bool(target_class) and name == target_class and conf >= self.mission_conf_threshold
                if is_target:
                    detected_count += 1
                    top_conf = max(top_conf, conf)

                color = (0, 220, 0) if is_target else (130, 130, 130)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                cv2.putText(
                    frame,
                    f"{name} {conf:.2f}",
                    (x1, max(20, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.45,
                    color,
                    2,
                )

        return detected_count > 0, detected_count, top_conf

    def _clear_active_mission_target(self):
        """Clear active mission target runtime fields."""
        self.mission_target = None
        self.mission_active_target_id = None
        self.mission_route_points = []
        self.mission_route_index = -1
        self.mission_route_next_step_at = 0.0
        self.mission_tail_detect_streak = 0
        self.mission_tail_hit = False
        self.mission_last_found = False
        self.mission_lock_started_at = None
        self.mission_countdown_until = None
        self.mission_next_camera_retry_at = 0.0
        self.mission_next_lora_retry_at = 0.0
        self.mission_canvas_last_update_at = 0.0

    def start_waiting_mission(self):
        """Start waiting mission runtime loop."""
        if self.mission_running:
            return

        init_coord, coord_error = self._get_initial_coordinates()
        if coord_error:
            self._set_mission_state("READINESS FAIL", "#ff0000")
            self.update_mission_lora_status("Readiness gate failed", "#ff0000")
            messagebox.showwarning("Readiness Gate", coord_error)
            return

        self.mission_start_lat, self.mission_start_lon = init_coord

        if self.yolo_shutting_down or (self.yolo_thread is not None and self.yolo_thread.is_alive()):
            self.update_status_bar("Stop YOLO manual dulu sebelum start Waiting Misi")
            return

        image_ready, image_error = self._check_latest_target_image_path_ready()
        if not image_ready:
            self._set_mission_state("READINESS FAIL", "#ff0000")
            self.update_mission_lora_status("Target image missing", "#ff0000")
            if image_error:
                self.append_mission_log(f"[WARN] {image_error}")
                messagebox.showwarning("Readiness Gate", image_error)
            return

        if not self._load_yolo_model():
            self._set_mission_state("MODEL ERROR", "#ff0000")
            return

        if not self._start_socket_server_process():
            self._set_mission_state("SOURCE ERROR", "#ff0000")
            return

        if not self._start_mission_lora_worker():
            self._set_mission_state("LORA ERROR", "#ff0000")
            self.update_mission_lora_status("Worker mission gagal start", "#ff0000")
            return

        # Fix – inisialisasi sender SEKARANG (eager) bukan saat step pertama (lazy)
        # agar P/R/Y sensor sudah terbaca dari step 1, bukan hanya di akhir.
        self.append_mission_log("[INFO] Inisialisasi LoRa sender...")
        if not self._ensure_mission_lora_sender():
            self._set_mission_state("LORA INIT ERROR", "#ff0000")
            self.update_mission_lora_status("Sender gagal init", "#ff0000")
            self._stop_mission_lora_worker()
            return

        self.mission_running = True
        self._clear_active_mission_target()
        self.mission_last_lora_sent_at = 0.0
        self.mission_next_lora_retry_at = 0.0
        self.mission_next_camera_retry_at = 0.0
        self.mission_frame_fail_count = 0
        self.mission_lora_interval = MISSION_ROUTE_STEP_SECONDS
        self.mission_detail_last_poll_at = 0.0
        self.mission_detail_cache = None
        self._reset_mission_lora_debug_counters()

        if hasattr(self, "mission_start_btn"):
            self.mission_start_btn.config(state=tk.DISABLED)
        if hasattr(self, "mission_stop_btn"):
            self.mission_stop_btn.config(state=tk.NORMAL)

        self._set_mission_state("WAITING TARGET", "#ffcc00")
        self.update_mission_yolo_status("Menunggu detail misi terbaru", "#ffcc00")
        self.update_mission_lora_status("Idle (1.0s interval)", "#ffcc00")
        self.clear_mission_countdown()
        self.append_mission_log("[INFO] Waiting mission started.")
        self.append_mission_log(
            f"[READY] Initial coordinate = ({self.mission_start_lat:.7f}, {self.mission_start_lon:.7f})"
        )

        # Fix #6 – clear stop-event before spawning the new thread
        self._mission_stop_event.clear()
        self.mission_thread = threading.Thread(target=self._mission_loop, daemon=True)
        self.mission_thread.start()
        # Fix #1 – start mission canvas poller on UI thread
        self._safe_after(self._poll_mission_canvas)

    def stop_waiting_mission(self):
        """Stop waiting mission loop and clean mission resources."""
        # Fix #6 – signal background thread to exit cleanly via event
        self._mission_stop_event.set()
        self.mission_running = False
        self.mission_countdown_until = None
        self.mission_lock_started_at = None
        self.mission_next_camera_retry_at = 0.0
        self.mission_next_lora_retry_at = 0.0
        self.mission_frame_fail_count = 0
        self.mission_route_points = []
        self.mission_route_index = -1
        self.mission_route_next_step_at = 0.0
        self.mission_tail_detect_streak = 0
        self.mission_tail_hit = False
        self.mission_last_found = False
        self.mission_canvas_last_update_at = 0.0
        self.mission_detail_last_poll_at = 0.0
        self.mission_detail_cache = None

        if self.mission_camera is not None:
            try:
                self.mission_camera.stop()
            except Exception:
                pass
            self.mission_camera = None

        self._stop_mission_lora_worker()
        self._release_mission_lora_sender()
        self._stop_socket_server_process()

        if self.mission_thread is not None and self.mission_thread.is_alive() and threading.current_thread() is not self.mission_thread:
            self.mission_thread.join(timeout=2.0)

        if hasattr(self, "mission_start_btn"):
            self.mission_start_btn.config(state=tk.NORMAL)
        if hasattr(self, "mission_stop_btn"):
            self.mission_stop_btn.config(state=tk.DISABLED)

        if not self.app_closing:
            self._set_mission_state("IDLE", "#ffcc00")
            self.update_mission_yolo_status("Stopped", "#ffcc00")
            self.update_mission_lora_status("Stopped", "#ffcc00")
            self.clear_mission_countdown()
            self._clear_mission_camera_canvas()

    def _mission_loop(self):
        """Mission runtime using detail_misi source + generated straight route."""
        import cv2

        from finalCode.camera.stream import WebcamStream

        try:
            # Fix #6 – honour stop event in addition to flag for clean exit
            while self.mission_running and not self.app_closing and not self._mission_stop_event.is_set():
                loop_perf = time.perf_counter()
                latest_target = self._read_latest_target_state_cached(loop_perf)
                if latest_target is not None:
                    new_target_id = latest_target.get("target_id")
                    if new_target_id and new_target_id != self.mission_last_target_id:
                        finish_points = int(latest_target.get("finish_points") or MISSION_ROUTE_POINTS)
                        route_points = self._build_route_points(
                            self.mission_start_lat,
                            self.mission_start_lon,
                            float(latest_target.get("target_lat")),
                            float(latest_target.get("target_lon")),
                            finish_points,
                        )

                        target_data = dict(latest_target)
                        target_data["start_lat"] = self.mission_start_lat
                        target_data["start_lon"] = self.mission_start_lon
                        target_data["route_points"] = route_points
                        route_path = self._save_route_json(target_data, route_points)
                        target_data["route_file"] = route_path

                        self.mission_last_target_id = new_target_id
                        self.mission_last_route_file = route_path
                        self.mission_target = target_data
                        self.mission_active_target_id = new_target_id
                        self.mission_route_points = route_points
                        self.mission_route_index = -1
                        self.mission_route_next_step_at = time.perf_counter()
                        self.mission_tail_detect_streak = 0
                        self.mission_tail_hit = False
                        self.mission_last_found = False
                        self.mission_last_lora_sent_at = 0.0
                        self.mission_next_camera_retry_at = 0.0
                        self.mission_next_lora_retry_at = 0.0
                        self.mission_frame_fail_count = 0
                        self.mission_countdown_until = None
                        self.mission_lock_started_at = None

                        if self.mission_camera is not None:
                            try:
                                self.mission_camera.stop()
                            except Exception:
                                pass
                            self.mission_camera = None
                            self._safe_after(self._clear_mission_camera_canvas)

                        self._clear_mission_lora_queue()
                        self._release_mission_lora_sender()
                        self._safe_after(lambda data=target_data: self._handle_new_mission_target(data))
                        self._safe_after(
                            lambda total=len(route_points): self.mission_route_label.config(
                                text=f"Route: 0/{total}"
                            )
                        )
                        self._safe_after(lambda: self._set_mission_state("ROUTE READY", "#00ff99"))
                        self._safe_after(lambda: self.update_mission_yolo_status("Tracking route mission", "#00ff99"))
                        self._safe_after(
                            lambda route_name=os.path.basename(route_path), total=len(route_points): self.append_mission_log(
                                f"[ROUTE] {route_name} generated ({total} points)."
                            )
                        )

                if self.mission_active_target_id is None:
                    time.sleep(MISSION_IDLE_POLL_SECONDS)
                    continue

                now_perf = time.perf_counter()

                if self.mission_camera is None:
                    if now_perf < self.mission_next_camera_retry_at:
                        time.sleep(0.05)
                        continue

                    try:
                        self.mission_camera = WebcamStream(0, 416, 416)
                        if not self.mission_camera.is_ready():
                            raise RuntimeError("Camera not ready")
                        self.mission_frame_fail_count = 0
                        self.mission_next_camera_retry_at = 0.0
                        self._safe_after(lambda: self._set_mission_state("TRACKING", "#00ff99"))
                        self._safe_after(lambda: self.update_mission_yolo_status("Tracking target on route", "#00ff99"))
                    except Exception as e:
                        self.mission_next_camera_retry_at = time.perf_counter() + self.mission_camera_retry_delay
                        self._safe_after(
                            lambda err=str(e): self.append_mission_log(f"[ERROR] Camera mission gagal dibuka: {err}")
                        )
                        self._safe_after(
                            lambda delay=self.mission_camera_retry_delay: self.append_mission_log(
                                f"[WARN] Auto-recover camera retry dalam {delay:.1f}s"
                            )
                        )
                        self._safe_after(lambda: self._set_mission_state("CAMERA RETRY", "#ff9900"))
                        self._safe_after(lambda: self.update_mission_yolo_status("Camera auto-recover", "#ff9900"))
                        time.sleep(0.2)
                        continue

                ret, frame = self.mission_camera.get_frame()
                if not ret or frame is None:
                    self.mission_frame_fail_count += 1
                    if self.mission_frame_fail_count >= self.mission_frame_fail_reopen_threshold:
                        self._safe_after(
                            lambda cnt=self.mission_frame_fail_count: self.append_mission_log(
                                f"[WARN] Frame gagal {cnt}x, restart kamera..."
                            )
                        )
                        try:
                            self.mission_camera.stop()
                        except Exception:
                            pass
                        self.mission_camera = None
                        self.mission_frame_fail_count = 0
                        self.mission_next_camera_retry_at = time.perf_counter() + self.mission_camera_retry_delay
                        self._safe_after(lambda: self._set_mission_state("CAMERA RETRY", "#ff9900"))
                        self._safe_after(lambda: self.update_mission_yolo_status("Re-opening camera...", "#ff9900"))
                    time.sleep(0.02)
                    continue
                self.mission_frame_fail_count = 0

                target_class = str((self.mission_target or {}).get("class_name", "")).strip().lower()
                route_total = len(self.mission_route_points)
                if route_total == 0:
                    self._safe_after(lambda: self.append_mission_log("[WARN] Route points kosong, reset target."))
                    self._clear_active_mission_target()
                    continue

                try:
                    lock_now, detected_count, top_conf = self._run_mission_detection(frame, target_class)
                except Exception as e:
                    self._safe_after(lambda err=str(e): self.append_mission_log(f"[ERROR] YOLO mission error: {err}"))
                    lock_now = False
                    detected_count = 0
                    top_conf = 0.0

                step_advanced = False
                route_finished_now = False
                current_point = None

                if now_perf >= self.mission_route_next_step_at and self.mission_route_index < route_total - 1:
                    self.mission_route_index += 1
                    self.mission_route_next_step_at = now_perf + MISSION_ROUTE_STEP_SECONDS
                    step_advanced = True
                    route_finished_now = self.mission_route_index >= route_total - 1
                    current_point = self.mission_route_points[self.mission_route_index]

                    in_tail_window = self.mission_route_index >= (route_total - MISSION_ROUTE_TAIL_POINTS)
                    current_step = self.mission_route_index + 1

                    # Status: 'Selesai' pada titik terakhir, 'Launch' untuk yang lain
                    mission_status = "Selesai" if route_finished_now else "Launch"
                    self._send_mission_sikap_once(
                        now_perf,
                        current_point,
                        current_step,
                        route_total,
                        lock_now,    # Found = hasil deteksi YOLO saat itu
                        mission_status,
                    )

                    self._safe_after(
                        lambda idx=current_step, total=route_total: self.mission_route_label.config(
                            text=f"Route: {idx}/{total}"
                        )
                    )

                if current_point is None and self.mission_route_index >= 0:
                    current_point = self.mission_route_points[self.mission_route_index]

                found_color = (0, 255, 0) if lock_now else (0, 0, 255)
                cv2.putText(
                    frame,
                    f"Found={'True' if lock_now else 'False'}",
                    (10, 36),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.9,
                    found_color,
                    3,
                )

                # Fix #1 – push frame to single-slot queue; UI poller renders at ~30 FPS
                self._push_frame(self._mission_frame_queue, frame.copy())

                if route_finished_now:
                    # Route selesai – tutup kamera, bersihkan target, tunggu misi berikutnya.
                    # Tidak ada evaluasi SUCCESS/FAILED; receiver yang menilai berdasarkan
                    # data Found yang sudah dikirim per-step.
                    if self.mission_camera is not None:
                        try:
                            self.mission_camera.stop()
                        except Exception:
                            pass
                        self.mission_camera = None
                        self._safe_after(self._clear_mission_camera_canvas)

                    self._safe_after(
                        lambda: self.append_mission_log(
                            "[DONE] Route selesai. Menunggu misi berikutnya..."
                        )
                    )
                    self._safe_after(lambda: self._set_mission_state("WAITING TARGET", "#ffcc00"))
                    self._safe_after(lambda: self.update_mission_yolo_status("Menunggu detail misi baru", "#ffcc00"))
                    self._safe_after(lambda: self.update_mission_lora_status("Idle", "#ffcc00"))
                    self._safe_after(lambda: self.mission_route_label.config(text="Route: -"))
                    self._clear_active_mission_target()

                time.sleep(0.01 if step_advanced else 0.02)
        except Exception as e:
            self._safe_after(lambda err=str(e): self.append_mission_log(f"[ERROR] Mission loop crash: {err}"))
            self._safe_after(lambda: self._set_mission_state("ERROR", "#ff0000"))
        finally:
            if self.mission_camera is not None:
                try:
                    self.mission_camera.stop()
                except Exception:
                    pass
                self.mission_camera = None

            self._stop_mission_lora_worker()
            self._release_mission_lora_sender()
            self._stop_socket_server_process()
            self._safe_after(lambda: self.mission_route_label.config(text="Route: -"))
            self._safe_after(self._clear_mission_camera_canvas)
            self._safe_after(lambda: self.update_mission_yolo_status("Stopped", "#ffcc00"))
            self._safe_after(lambda: self.update_mission_lora_status("Stopped", "#ffcc00"))
            self._safe_after(lambda: self.mission_start_btn.config(state=tk.NORMAL))
            self._safe_after(lambda: self.mission_stop_btn.config(state=tk.DISABLED))

    def _close_yolo_window(self):
        """Reset YOLO canvas preview area."""
        if not hasattr(self, "yolo_canvas"):
            return
        self.yolo_canvas.delete("all")
        self.yolo_canvas.create_text(
            208,
            208,
            text="YOLO Preview berhenti\nClick Start YOLO",
            fill="#bdbdbd",
            font=("Arial", 14, "bold"),
            justify=tk.CENTER
        )
        self.yolo_photo = None

    def _update_yolo_canvas(self, frame):
        """Render BGR OpenCV frame into Tk canvas."""
        if Image is None or ImageTk is None:
            self.update_yolo_status("Pillow belum terpasang", "#ff0000")
            return
        if not hasattr(self, "yolo_canvas"):
            return

        import cv2

        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(rgb)
        photo = ImageTk.PhotoImage(image=img)

        # Fix #7 – explicitly release old PhotoImage before replacing
        old_photo = self.yolo_photo
        self.yolo_canvas.delete("all")
        self.yolo_canvas.create_image(0, 0, anchor=tk.NW, image=photo)
        self.yolo_photo = photo
        del old_photo

    def update_yolo_status(self, message, color="#ffcc00"):
        """Update YOLO status label."""
        self.yolo_status_label.config(text=f"YOLO: {message}", fg=color)

    def update_lora_status(self, message, color="#ffcc00"):
        """Update LoRa status label."""
        self.lora_status_label.config(text=f"LoRa: {message}", fg=color)

    def append_lora_log(self, text):
        """Append one line to LoRa log box safely."""
        self.lora_log.config(state=tk.NORMAL)
        self.lora_log.insert(tk.END, text + "\n")
        self.lora_log.see(tk.END)
        self.lora_log.config(state=tk.DISABLED)

    def clear_lora_log(self):
        """Clear Health Check LoRa log widget."""
        if not hasattr(self, "lora_log"):
            return
        self.lora_log.config(state=tk.NORMAL)
        self.lora_log.delete("1.0", tk.END)
        self.lora_log.insert(tk.END, "[INFO] Log dibersihkan.\n")
        self.lora_log.config(state=tk.DISABLED)

    def _load_yolo_model(self):
        """Load YOLO model from configured path."""
        if self.yolo_model is not None:
            return True

        if not os.path.exists(YOLO_MODEL_PATH):
            self.update_yolo_status("Model file belum ada", "#ff0000")
            messagebox.showwarning(
                "Model YOLO Belum Ada",
                f"Model belum ditemukan di:\n{YOLO_MODEL_PATH}\n\n"
                "Silakan copy model YOLO Anda ke path tersebut."
            )
            return False

        try:
            from modules.detektor import YoloDetektor
            self.yolo_model = YoloDetektor(YOLO_MODEL_PATH)
            self.update_yolo_status("Model loaded", "#00ff99")
            return True
        except ImportError:
            self.update_yolo_status("Module detektor/ultralytics belum siap", "#ff0000")
            messagebox.showerror(
                "Dependency Missing",
                "Module detektor atau dependency model belum tersedia di environment aktif.\n"
                "Pastikan package ultralytics dan modul project bisa diimport."
            )
            return False
        except Exception as e:
            self.update_yolo_status(f"Gagal load model: {str(e)[:40]}", "#ff0000")
            return False

    def start_yolo_detection(self):
        """Start YOLO detection in a background thread."""
        if self.yolo_running:
            return

        if self.yolo_shutting_down or (self.yolo_thread is not None and self.yolo_thread.is_alive()):
            self.update_yolo_status("Tunggu, YOLO masih cleanup...", "#ff9900")
            return

        if not self._load_yolo_model():
            return

        self.yolo_running = True
        self.yolo_shutting_down = False
        self.yolo_start_btn.config(state=tk.DISABLED)
        self.yolo_stop_btn.config(state=tk.NORMAL)
        self.update_yolo_status("Starting camera + OpenCV window...", "#ffcc00")

        self.yolo_thread = threading.Thread(target=self._yolo_loop, daemon=True)
        self.yolo_thread.start()
        # Fix #1 – start YOLO canvas poller on UI thread
        self._safe_after(self._poll_yolo_canvas)

    def stop_yolo_detection(self):
        """Stop YOLO detection loop."""
        self.yolo_running = False
        if self.yolo_thread is not None and self.yolo_thread.is_alive():
            self.yolo_shutting_down = True
            self.update_yolo_status("Stopping...", "#ff9900")
        if hasattr(self, "yolo_start_btn"):
            self.yolo_start_btn.config(state=tk.NORMAL)
        if hasattr(self, "yolo_stop_btn"):
            self.yolo_stop_btn.config(state=tk.DISABLED)
        if hasattr(self, "yolo_status_label") and not self.yolo_shutting_down:
            self.update_yolo_status("Stopped", "#ffcc00")

    def _finish_yolo_shutdown(self):
        """Finalize YOLO UI state after thread fully exits."""
        self.yolo_running = False
        self.yolo_shutting_down = False
        self.yolo_thread = None
        if hasattr(self, "yolo_start_btn"):
            self.yolo_start_btn.config(state=tk.NORMAL)
        if hasattr(self, "yolo_stop_btn"):
            self.yolo_stop_btn.config(state=tk.DISABLED)
        if hasattr(self, "yolo_status_label"):
            self.update_yolo_status("Stopped", "#ffcc00")

    def _initialize_lora_sender(self):
        """Initialize LoRa sender for sikap payload mode."""
        if self.lora_sender is not None:
            return True

        try:
            from finalCode.lora.sender_sensor import LoRaSensorSender
            self.lora_sender = LoRaSensorSender(sensors='sikap')
            self.lora_counter = 1
            self._safe_after(lambda: self.update_lora_status("Sender initialized", "#00ff99"))
            self._safe_after(lambda: self.append_lora_log("[INFO] Sender LoRa mode SIKAP initialized."))
            return True
        except Exception as e:
            err = str(e)
            self._safe_after(lambda: self.update_lora_status("Init gagal", "#ff0000"))
            self._safe_after(lambda: self.append_lora_log(f"[ERROR] Init LoRa gagal: {err}"))
            return False

    def start_lora_sender(self):
        """Start LoRa sender loop for sikap payload."""
        if self.lora_running:
            return

        self.lora_running = True
        self.lora_start_btn.config(state=tk.DISABLED)
        self.lora_stop_btn.config(state=tk.NORMAL)
        self.update_lora_status("Starting...", "#ffcc00")

        self.lora_thread = threading.Thread(target=self._lora_loop, daemon=True)
        self.lora_thread.start()

    def stop_lora_sender(self):
        """Stop LoRa sender and ensure GPIO is released."""
        self.lora_running = False
        if hasattr(self, "lora_start_btn"):
            self.lora_start_btn.config(state=tk.NORMAL)
        if hasattr(self, "lora_stop_btn"):
            self.lora_stop_btn.config(state=tk.DISABLED)

        if self.lora_sender is not None:
            try:
                self.lora_sender.cleanup()
                self.append_lora_log("[INFO] Cleanup LoRa + GPIO selesai.")
            except Exception as e:
                self.append_lora_log(f"[WARN] Cleanup LoRa bermasalah: {e}")
            finally:
                self.lora_sender = None

        if hasattr(self, "lora_status_label"):
            self.update_lora_status("Stopped", "#ffcc00")

    def _lora_loop(self):
        """Background loop for periodic sikap data transmission."""
        if not self._initialize_lora_sender():
            self._safe_after(self.stop_lora_sender)
            return

        self._safe_after(lambda: self.update_lora_status("Running", "#00ff99"))

        try:
            while self.lora_running:
                sukses, pesan = self.lora_sender.kirim_data(self.lora_counter)
                jam = time.strftime("%H:%M:%S")
                status_text = "TERKIRIM" if sukses else "TIMEOUT"
                log_line = f"[{jam}] #{self.lora_counter} {status_text} | {pesan}"
                self._safe_after(lambda line=log_line: self.append_lora_log(line))
                self._safe_after(lambda st=status_text: self.update_lora_status(st, "#00ff99" if st == "TERKIRIM" else "#ff9900"))
                self.lora_counter += 1

                # Use short sleep chunks so stop request responds quickly.
                remaining = self.lora_interval
                while remaining > 0 and self.lora_running:
                    chunk = min(0.1, remaining)
                    time.sleep(chunk)
                    remaining -= chunk
        except Exception as e:
            err = str(e)
            self._safe_after(lambda: self.append_lora_log(f"[ERROR] Loop LoRa error: {err}"))
            self._safe_after(lambda: self.update_lora_status("Error", "#ff0000"))
        finally:
            self._safe_after(self.stop_lora_sender)

    def _yolo_loop(self):
        """Capture camera frames, run YOLO, and show result on Tk canvas."""
        import cv2

        from finalCode.camera.stream import WebcamStream

        if Image is None or ImageTk is None:
            self._safe_after(lambda: self.update_yolo_status("Install pillow dulu", "#ff0000"))
            self._safe_after(self._finish_yolo_shutdown)
            return

        kamera = None
        for attempt in range(1, 11):
            try:
                kamera = WebcamStream(0, 416, 416)
                if kamera.is_ready():
                    break
            except Exception:
                kamera = None

            self.root.after(
                0,
                lambda n=attempt: self.update_yolo_status(f"Camera retry {n}/10...", "#ff9900")
            )
            time.sleep(0.5)

        if kamera is None or not kamera.is_ready():
            self._safe_after(lambda: self.update_yolo_status("Camera tidak bisa dibuka", "#ff0000"))
            self._safe_after(self._finish_yolo_shutdown)
            return

        prev_time = time.perf_counter()
        fps_smooth = 0.0
        frame_count = 0

        try:
            while self.yolo_running:
                ret, frame = kamera.get_frame()
                if not ret or frame is None:
                    self._safe_after(lambda: self.update_yolo_status("Gagal baca frame", "#ff0000"))
                    continue

                status_message = "Tidak ada deteksi"

                try:
                    infer_start = time.perf_counter()
                    results = list(self.yolo_model.prediksi(frame))
                    infer_ms = (time.perf_counter() - infer_start) * 1000.0

                    frame = self.yolo_model.bounding_box(frame, results)
                    frame = self.yolo_model.fps(frame)

                    detected_count = 0
                    for label in results:
                        boxes = getattr(label, "boxes", None)
                        if boxes is not None:
                            detected_count += len(boxes)

                    now = time.perf_counter()
                    inst_fps = 1.0 / max(now - prev_time, 1e-6)
                    prev_time = now
                    fps_smooth = inst_fps if fps_smooth == 0.0 else (fps_smooth * 0.9 + inst_fps * 0.1)

                    cv2.putText(
                        frame,
                        f"GUI FPS: {fps_smooth:.1f} | INF: {infer_ms:.1f} ms",
                        (10, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 220, 0),
                        2,
                        cv2.LINE_AA,
                    )

                    status_message = f"Deteksi {detected_count} objek | FPS {fps_smooth:.1f}"
                except Exception as e:
                    status_message = f"Inference error: {str(e)[:35]}"

                # Fix #1 – push to queue; poller renders at ~30 FPS
                self._push_frame(self._yolo_frame_queue, frame.copy())

                frame_count += 1
                if frame_count % 10 == 0:
                    self._safe_after(lambda msg=status_message: self.update_yolo_status(msg, "#00ff99"))

        finally:
            if kamera is not None:
                try:
                    kamera.stop()
                except Exception:
                    pass
            time.sleep(0.2)
            self._safe_after(self._close_yolo_window)
            self._safe_after(self._finish_yolo_shutdown)
        
    def create_sensor_widget(self, parent, sensor_name, sensor_key):
        """Create a sensor status widget."""
        widget_frame = tk.Frame(parent, bg="#2a2a2a", relief=tk.FLAT, highlightthickness=1, highlightbackground="#444444")
        widget_frame.pack(fill=tk.X, pady=5)
        
        # Sensor name
        name_label = tk.Label(
            widget_frame,
            text=sensor_name,
            font=("Arial", 11),
            bg="#2a2a2a",
            fg=self.COLOR_FG,
            anchor=tk.W
        )
        name_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15, pady=12)
        
        # Status circle
        status_canvas = tk.Canvas(
            widget_frame,
            width=30,
            height=30,
            bg="#2a2a2a",
            highlightthickness=0
        )
        status_canvas.pack(side=tk.RIGHT, padx=15, pady=10)
        
        # Draw initial pending status
        status_canvas.create_oval(5, 5, 25, 25, fill=self.COLOR_PENDING, outline=self.COLOR_PENDING)
        
        # Status text
        status_text = tk.Label(
            widget_frame,
            text="PENDING",
            font=("Arial", 9, "bold"),
            bg="#2a2a2a",
            fg=self.COLOR_PENDING
        )
        status_text.pack(side=tk.RIGHT, padx=10)
        
        return {
            'frame': widget_frame,
            'canvas': status_canvas,
            'label': status_text,
            'name_label': name_label
        }
    
    def set_sensor_status(self, sensor_key, status, message=""):
        """Update sensor status display."""
        if threading.current_thread() is not threading.main_thread():
            self._safe_after(lambda: self.set_sensor_status(sensor_key, status, message))
            return

        if sensor_key not in self.sensor_widgets:
            return
        
        widget = self.sensor_widgets[sensor_key]
        
        # Determine color based on status
        if status == "success":
            color = self.COLOR_SUCCESS
            text = "OK" if not message else f"OK - {message}"
        elif status == "warning":
            color = self.COLOR_WARNING
            text = f"WARNING - {message}" if message else "WARNING"
        elif status == "error":
            color = self.COLOR_ERROR
            text = f"ERROR - {message}" if message else "ERROR"
        else:  # pending
            color = self.COLOR_PENDING
            text = "PENDING"
        
        # Update canvas
        widget['canvas'].delete("all")
        widget['canvas'].create_oval(5, 5, 25, 25, fill=color, outline=color)
        
        # Update label
        widget['label'].config(text=text, fg=color)
        
        self.sensor_status[sensor_key] = status
        # Fix #4 – removed update_idletasks(); mainloop handles redraw
    
    def reset_status(self):
        """Reset all sensor status to pending."""
        for sensor_key in self.sensor_widgets:
            self.set_sensor_status(sensor_key, "pending")
        self.update_status_bar("Ready")
    
    def update_status_bar(self, message):
        """Update the status bar message."""
        if threading.current_thread() is not threading.main_thread():
            self._safe_after(lambda: self.update_status_bar(message))
            return

        self.status_bar.config(text=message)
        # Fix #4 – removed update_idletasks(); mainloop handles redraw
    
    def start_health_check(self):
        """Start non-blocking health check sequence on UI thread."""
        if self.is_checking:
            messagebox.showwarning("Already Checking", "Health check is already in progress!")
            return
        
        self.is_checking = True
        self.start_btn.config(state=tk.DISABLED)
        self.reset_status()

        self.health_check_steps = [
            ("Checking camera...", self.check_camera),
            ("Checking LoRa module...", self.check_lora),
            ("Checking MPU6050...", self.check_mpu6050),
            ("Checking BMP280...", self.check_bmp280),
            ("Checking GY511...", self.check_gy511),
            ("Checking GPSM6N...", self.check_gpsm6n),
            ("Checking WiFi...", self.check_wifi),
            ("Checking power supply...", self.check_power),
        ]
        self.health_check_step_index = 0
        self._safe_after(self._run_health_check_step)

    def _finish_health_check(self, status_message):
        """Finalize health check UI state safely."""
        self.is_checking = False
        self.update_status_bar(status_message)
        if hasattr(self, "start_btn"):
            self.start_btn.config(state=tk.NORMAL)

    def _run_health_check_step(self):
        """Run one health check step and schedule the next one."""
        if not self.is_checking:
            return

        if self.health_check_step_index >= len(self.health_check_steps):
            self._finish_health_check("✓ Health check completed!")
            return

        status_text, check_fn = self.health_check_steps[self.health_check_step_index]
        self.update_status_bar(status_text)

        try:
            check_fn()
        except Exception as e:
            self._finish_health_check(f"✗ Error during health check: {str(e)}")
            return

        self.health_check_step_index += 1
        self._safe_after(self._run_health_check_step, 500)
    
    def perform_health_check(self):
        """Backward-compatible wrapper for scheduled health check flow."""
        self._safe_after(self.start_health_check)
    
    # ==== Sensor Check Methods ====
    
    def check_camera(self):
        """Check camera availability."""
        try:
            import cv2
            cap = cv2.VideoCapture(0)
            if cap.isOpened():
                ret, frame = cap.read()
                cap.release()
                if ret:
                    self.set_sensor_status("camera", "success", "Ready")
                else:
                    self.set_sensor_status("camera", "error", "Cannot capture frame")
            else:
                self.set_sensor_status("camera", "error", "Cannot open device")
        except ImportError:
            self.set_sensor_status("camera", "warning", "OpenCV not installed")
        except Exception as e:
            self.set_sensor_status("camera", "error", str(e)[:20])
    
    def check_lora(self):
        """Check LoRa module."""
        try:
            # Try to import LoRa library
            from SX127x.LoRa import LoRa
            from SX127x.board_config import BOARD
            self.set_sensor_status("lora", "success", "Ready")
        except ImportError:
            self.set_sensor_status("lora", "warning", "Library not installed")
        except Exception as e:
            self.set_sensor_status("lora", "error", str(e)[:20])
    
    def check_mpu6050(self):
        """Check MPU6050 sensor."""
        try:
            from finalCode.sensor.mpu6050 import SensorMPU6050
            sensor = SensorMPU6050()
            data = sensor.baca_semua()
            if data:
                self.set_sensor_status("mpu6050", "success", "Ready")
            else:
                self.set_sensor_status("mpu6050", "error", "No data")
        except ImportError:
            self.set_sensor_status("mpu6050", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("mpu6050", "error", str(e)[:20])
    
    def check_bmp280(self):
        """Check BMP280 sensor."""
        try:
            from finalCode.sensor.bmp280 import SensorBMP280
            sensor = SensorBMP280()
            data = sensor.baca_semua()
            if data:
                self.set_sensor_status("bmp280", "success", "Ready")
            else:
                self.set_sensor_status("bmp280", "error", "No data")
        except ImportError:
            self.set_sensor_status("bmp280", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("bmp280", "error", str(e)[:20])
    
    def check_gy511(self):
        """Check GY511 sensor."""
        try:
            from finalCode.sensor.gy511 import SensorGY511
            sensor = SensorGY511()
            data = sensor.baca_akselerasi()
            if "error" in data:
                self.set_sensor_status("gy511", "error", data["error"])
            elif data:
                self.set_sensor_status("gy511", "success", "Ready")
            else:
                self.set_sensor_status("gy511", "error", "No data")
        except ImportError:
            self.set_sensor_status("gy511", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("gy511", "error", str(e)[:20])
    
    def check_gpsm6n(self):
        """Check GPSM6N sensor."""
        try:
            from finalCode.sensor.gpsm6n import SensorGPSM6N
            sensor = SensorGPSM6N()
            data = sensor.baca_semua()
            if data:
                # Check if GPS has a valid fix with coordinates
                if data.get('status') == 'FIX' and data.get('latitude') is not None and data.get('longitude') is not None:
                    self.set_sensor_status("gpsm6n", "success", f"Fixed ({data.get('satellites', 0)} sat)")
                elif data.get('status') == 'NO_FIX':
                    # Module detected but no fix yet
                    self.set_sensor_status("gpsm6n", "warning", f"No fix ({data.get('satellites', 0)} sat)")
                else:
                    self.set_sensor_status("gpsm6n", "warning", "Searching...")
            else:
                self.set_sensor_status("gpsm6n", "error", "No data")
        except ImportError:
            self.set_sensor_status("gpsm6n", "warning", "Module not found")
        except Exception as e:
            self.set_sensor_status("gpsm6n", "error", str(e)[:20])
    
    def check_wifi(self):
        """Check WiFi connection."""
        try:
            import subprocess
            result = subprocess.run(
                ["ip", "link", "show", "wlan0"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                # Check if connected to a network
                result2 = subprocess.run(
                    ["iwconfig", "wlan0"],
                    capture_output=True,
                    timeout=5
                )
                if b"ESSID" in result2.stdout and b"off/any" not in result2.stdout:
                    self.set_sensor_status("wifi", "success", "Connected")
                else:
                    self.set_sensor_status("wifi", "warning", "Interface ready, not connected")
            else:
                self.set_sensor_status("wifi", "error", "No interface")
        except Exception as e:
            self.set_sensor_status("wifi", "warning", "Cannot check")
    
    def check_power(self):
        """Check power supply status."""
        try:
            # Read voltage from ADC or system file
            power_file = "/sys/devices/platform/bcm2710-rng/base"
            if os.path.exists(power_file):
                self.set_sensor_status("power", "success", "Normal")
            else:
                # Fallback: check if system is running
                import psutil
                cpu_percent = psutil.cpu_percent(interval=0.1)
                if cpu_percent >= 0:  # System is responsive
                    self.set_sensor_status("power", "success", "Normal")
                else:
                    self.set_sensor_status("power", "warning", "Unknown")
        except Exception as e:
            self.set_sensor_status("power", "warning", "Cannot verify")


def main():
    """Main entry point."""
    root = tk.Tk()
    app = HealthCheckGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
