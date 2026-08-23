"""Tkinter GUI for the offline vanity address generator."""

from __future__ import annotations

import multiprocessing
import os
import queue
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Type

import tkinter as tk
from tkinter import messagebox, ttk

from gpu_backend import GPUAddressMatcher, list_gpu_devices
from vanity_core import estimate_difficulty, matches_pattern, searchable_address_length, validate_pattern
from vanity_generators import BitcoinGenerator, EthereumGenerator, TorGenerator


MAX_WORKERS = 64
STATS_BATCH_SIZE = 256
GPU_BATCH_SIZE = 4096
BENCHMARK_SECONDS = 2.0
BASE_SPEED_BY_TARGET = {
    "bitcoin": 12000,
    "ethereum": 12000,
    "tor": 10000,
}
GPU_SPEED_MULTIPLIER_BY_TARGET = {
    "bitcoin": 1.35,
    "ethereum": 1.35,
    "tor": 1.25,
}
GPU_REFERENCE_COMPUTE_UNITS = 16
GPU_COMPUTE_UNIT_SCALE_LIMIT = 1.75
GENERATOR_TYPES: dict[str, Type[BitcoinGenerator] | Type[EthereumGenerator] | Type[TorGenerator]] = {
    "bitcoin": BitcoinGenerator,
    "ethereum": EthereumGenerator,
    "tor": TorGenerator,
}


@dataclass(frozen=True)
class GenerationConfig:
    crypto: str
    pattern: str
    end_pattern: str
    position: str
    target_count: int
    thread_count: int
    compressed: bool
    compute_mode: str
    gpu_device_key: str
    output_path: Path


class VanityAddressGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Vanity Address Generator")
        self.root.geometry("760x700")
        self.root.minsize(700, 620)

        self.is_generating = False
        self.is_calibrating = False
        self.stop_event = threading.Event()
        self.calibration_stop_event = threading.Event()
        self.result_queue: queue.Queue[dict] = queue.Queue()
        self.generator_threads: list[threading.Thread] = []
        self.calibration_thread: threading.Thread | None = None
        self.current_config: GenerationConfig | None = None
        self.measured_speed_cache: dict[tuple[str, str, str, str, str, int, bool, str], float] = {}
        self.gpu_devices = list_gpu_devices()
        self.gpu_device_labels = {device.label: device.key for device in self.gpu_devices}
        self.gpu_matcher: GPUAddressMatcher | None = None
        self.gpu_lock = threading.Lock()

        self._lock = threading.Lock()
        self.start_time: float | None = None
        self.total_attempts = 0
        self.found_count = 0
        self.last_update_time = time.time()
        self.last_attempts = 0
        self.completion_notice_shown = False

        self.setup_styles()
        self.setup_ui()
        self.check_queue()
        self.update_stats()

    def setup_styles(self) -> None:
        style = ttk.Style()
        style.theme_use("clam")

        self.colors = {
            "bg": "#0d1117",
            "panel": "#161b22",
            "surface": "#21262d",
            "text": "#c9d1d9",
            "muted": "#8b949e",
            "accent": "#58a6ff",
            "success": "#3fb950",
            "danger": "#f85149",
            "terminal": "#39ff14",
        }

        self.root.configure(bg=self.colors["bg"])
        style.configure("TFrame", background=self.colors["bg"], borderwidth=0)
        style.configure("Panel.TFrame", background=self.colors["panel"], borderwidth=1)
        style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Consolas", 9))
        style.configure("Title.TLabel", background=self.colors["bg"], foreground=self.colors["terminal"], font=("Consolas", 17, "bold"))
        style.configure("Subtitle.TLabel", background=self.colors["bg"], foreground=self.colors["muted"], font=("Consolas", 10))
        style.configure("Heading.TLabel", background=self.colors["panel"], foreground=self.colors["accent"], font=("Consolas", 10, "bold"))
        style.configure("Stats.TLabel", background=self.colors["panel"], foreground=self.colors["text"], font=("Consolas", 9))
        style.configure("Status.TLabel", background=self.colors["panel"], foreground=self.colors["terminal"], font=("Consolas", 10, "bold"))
        style.configure("Error.TLabel", background=self.colors["panel"], foreground=self.colors["danger"], font=("Consolas", 8))

        style.configure("TButton", background=self.colors["surface"], foreground=self.colors["text"], borderwidth=1, focuscolor="none", font=("Consolas", 9))
        style.map("TButton", background=[("active", self.colors["accent"]), ("pressed", self.colors["panel"])], foreground=[("active", self.colors["bg"])])
        style.configure("Start.TButton", background=self.colors["success"], foreground=self.colors["bg"], font=("Consolas", 10, "bold"))
        style.configure("Stop.TButton", background=self.colors["danger"], foreground=self.colors["bg"], font=("Consolas", 10, "bold"))

        style.configure("TEntry", fieldbackground=self.colors["surface"], foreground=self.colors["text"], insertcolor=self.colors["terminal"], borderwidth=1, font=("Consolas", 10))
        style.configure("TRadiobutton", background=self.colors["panel"], foreground=self.colors["text"], focuscolor="none", font=("Consolas", 9))
        style.configure("TCheckbutton", background=self.colors["panel"], foreground=self.colors["text"], focuscolor="none", font=("Consolas", 9))
        style.configure("TLabelframe", background=self.colors["bg"], foreground=self.colors["accent"], borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", background=self.colors["bg"], foreground=self.colors["accent"], font=("Consolas", 11, "bold"))
        style.configure("TProgressbar", background=self.colors["terminal"], troughcolor=self.colors["surface"], borderwidth=0)

    def setup_ui(self) -> None:
        main_frame = ttk.Frame(self.root, padding=12)
        main_frame.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.E, tk.W))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)

        header = ttk.Frame(main_frame)
        header.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 12))
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="VANITY ADDRESS GENERATOR", style="Title.TLabel", anchor="center").grid(row=0, column=0, sticky=(tk.W, tk.E))
        ttk.Label(header, text="Offline Bitcoin, Ethereum, and Tor address generation", style="Subtitle.TLabel", anchor="center").grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 0))

        self.setup_config_section(main_frame)
        self.setup_controls(main_frame)
        self.setup_stats(main_frame)
        self.setup_results(main_frame)

    def setup_config_section(self, parent: ttk.Frame) -> None:
        config = ttk.LabelFrame(parent, text=" CONFIG ", padding=10)
        config.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        config.columnconfigure(1, weight=1)

        self.crypto_var = tk.StringVar(value="bitcoin")
        self.crypto_var.trace_add("write", self.on_crypto_change)
        self.compressed_var = tk.BooleanVar(value=True)

        ttk.Label(config, text="TARGET:", style="Heading.TLabel").grid(row=0, column=0, sticky=tk.W, pady=(0, 8))
        target_frame = ttk.Frame(config, style="Panel.TFrame")
        target_frame.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 8))
        for column, (label, value) in enumerate((("Bitcoin", "bitcoin"), ("Ethereum", "ethereum"), ("Tor (.onion)", "tor"))):
            ttk.Radiobutton(target_frame, text=label, variable=self.crypto_var, value=value).grid(row=0, column=column, padx=(0, 12))

        self.compressed_check = ttk.Checkbutton(target_frame, text="Compressed Bitcoin key", variable=self.compressed_var)
        self.compressed_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))
        ttk.Button(target_frame, text="?", width=3, command=self.show_protocol_constraints).grid(row=0, column=3, padx=(4, 0))

        pattern_frame = ttk.Frame(config, style="Panel.TFrame")
        pattern_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(2, 6))
        pattern_frame.columnconfigure(1, weight=1)

        self.pattern_var = tk.StringVar()
        self.pattern_var.trace_add("write", self.on_pattern_change)
        ttk.Label(pattern_frame, text="PATTERN:", style="Heading.TLabel").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(pattern_frame, textvariable=self.pattern_var, width=18).grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 12))

        self.position_var = tk.StringVar(value="start")
        self.position_var.trace_add("write", self.on_position_change)
        ttk.Label(pattern_frame, text="POSITION:", style="Heading.TLabel").grid(row=0, column=2, sticky=tk.W, padx=(0, 8))
        position_frame = ttk.Frame(pattern_frame, style="Panel.TFrame")
        position_frame.grid(row=0, column=3, sticky=tk.W)
        for column, (label, value) in enumerate((("Start", "start"), ("End", "end"), ("Both", "both"), ("Any", "anywhere"))):
            ttk.Radiobutton(position_frame, text=label, variable=self.position_var, value=value).grid(row=0, column=column, padx=(0, 6))

        self.pattern_validation_label = ttk.Label(config, text="", style="Error.TLabel")
        self.pattern_validation_label.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(0, 4))

        self.end_pattern_frame = ttk.Frame(config, style="Panel.TFrame")
        self.end_pattern_frame.columnconfigure(1, weight=1)
        self.end_pattern_var = tk.StringVar()
        self.end_pattern_var.trace_add("write", self.on_pattern_change)
        ttk.Label(self.end_pattern_frame, text="END PATTERN:", style="Heading.TLabel").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        ttk.Entry(self.end_pattern_frame, textvariable=self.end_pattern_var, width=18).grid(row=0, column=1, sticky=(tk.W, tk.E))
        self.end_pattern_validation_label = ttk.Label(self.end_pattern_frame, text="", style="Error.TLabel")
        self.end_pattern_validation_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(3, 0))

        compute = ttk.Frame(config, style="Panel.TFrame")
        compute.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(6, 0))
        compute.columnconfigure(4, weight=1)
        self.compute_var = tk.StringVar(value="cpu")
        self.compute_var.trace_add("write", self.on_compute_change)
        ttk.Label(compute, text="COMPUTE:", style="Heading.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Radiobutton(compute, text="CPU", variable=self.compute_var, value="cpu").grid(row=0, column=1, padx=(8, 10))
        self.gpu_radio = ttk.Radiobutton(compute, text="GPU", variable=self.compute_var, value="gpu")
        self.gpu_radio.grid(row=0, column=2, padx=(0, 10))
        labels = list(self.gpu_device_labels)
        self.gpu_device_var = tk.StringVar(value=labels[0] if labels else "No OpenCL GPU detected")
        self.gpu_device_combo = ttk.Combobox(
            compute,
            textvariable=self.gpu_device_var,
            values=labels if labels else ["No OpenCL GPU detected"],
            state="readonly" if labels else "disabled",
            width=44,
        )
        self.gpu_device_combo.grid(row=0, column=3, sticky=(tk.W, tk.E))
        self.gpu_device_combo.bind("<<ComboboxSelected>>", self.on_gpu_device_change)
        if not labels:
            self.gpu_radio.state(["disabled"])

        settings = ttk.Frame(config, style="Panel.TFrame")
        settings.grid(row=5, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(6, 0))
        self.count_var = tk.StringVar(value="5")
        default_workers = min(MAX_WORKERS, max(1, multiprocessing.cpu_count()))
        self.threads_var = tk.StringVar(value=str(default_workers))
        self.count_var.trace_add("write", self.on_estimate_input_change)
        self.threads_var.trace_add("write", self.on_estimate_input_change)
        ttk.Label(settings, text="MAX RESULTS:", style="Heading.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Entry(settings, textvariable=self.count_var, width=7).grid(row=0, column=1, padx=(6, 18))
        ttk.Label(settings, text="WORKERS:", style="Heading.TLabel").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(settings, textvariable=self.threads_var, width=7).grid(row=0, column=3, padx=(6, 0))

    def setup_controls(self, parent: ttk.Frame) -> None:
        controls = ttk.Frame(parent, padding=6)
        controls.grid(row=2, column=0, pady=(0, 10))
        self.start_button = ttk.Button(controls, text="START", command=self.start_generation, style="Start.TButton", width=12)
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        self.stop_button = ttk.Button(controls, text="STOP", command=self.stop_generation, style="Stop.TButton", width=10, state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        ttk.Button(controls, text="CLEAR", command=self.clear_results, width=10).grid(row=0, column=2)

    def setup_stats(self, parent: ttk.Frame) -> None:
        stats = ttk.LabelFrame(parent, text=" STATUS ", padding=12)
        stats.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        stats.columnconfigure(1, weight=1)
        stats.columnconfigure(3, weight=1)

        self.status_var = tk.StringVar(value="READY")
        self.speed_var = tk.StringVar(value="0 addr/sec")
        self.time_est_var = tk.StringVar(value="Unknown")
        self.attempts_var = tk.StringVar(value="0")
        self.found_var = tk.StringVar(value="0 addresses")

        ttk.Label(stats, text="STATE:", style="Heading.TLabel").grid(row=0, column=0, sticky=tk.W)
        ttk.Label(stats, textvariable=self.status_var, style="Status.TLabel").grid(row=0, column=1, sticky=tk.W, padx=(8, 20))
        self.progress_bar = ttk.Progressbar(stats, mode="indeterminate")
        self.progress_bar.grid(row=1, column=0, columnspan=4, sticky=(tk.W, tk.E), pady=(10, 12))

        ttk.Label(stats, text="SPEED:", style="Heading.TLabel").grid(row=2, column=0, sticky=tk.W)
        ttk.Label(stats, textvariable=self.speed_var, style="Stats.TLabel").grid(row=2, column=1, sticky=tk.W, padx=(8, 20))
        ttk.Label(stats, text="EST. TIME:", style="Heading.TLabel").grid(row=2, column=2, sticky=tk.W)
        ttk.Label(stats, textvariable=self.time_est_var, style="Stats.TLabel").grid(row=2, column=3, sticky=tk.W, padx=(8, 0))
        ttk.Label(stats, text="ATTEMPTS:", style="Heading.TLabel").grid(row=3, column=0, sticky=tk.W, pady=(6, 0))
        ttk.Label(stats, textvariable=self.attempts_var, style="Stats.TLabel").grid(row=3, column=1, sticky=tk.W, padx=(8, 20), pady=(6, 0))
        ttk.Label(stats, text="FOUND:", style="Heading.TLabel").grid(row=3, column=2, sticky=tk.W, pady=(6, 0))
        ttk.Label(stats, textvariable=self.found_var, style="Stats.TLabel").grid(row=3, column=3, sticky=tk.W, padx=(8, 0), pady=(6, 0))

    def setup_results(self, parent: ttk.Frame) -> None:
        results = ttk.LabelFrame(parent, text=" RESULTS ", padding=8)
        results.grid(row=4, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        results.columnconfigure(0, weight=1)
        results.rowconfigure(0, weight=1)

        self.results_text = tk.Text(
            results,
            height=10,
            wrap=tk.WORD,
            bg=self.colors["bg"],
            fg=self.colors["terminal"],
            insertbackground=self.colors["terminal"],
            selectbackground=self.colors["surface"],
            selectforeground=self.colors["text"],
            borderwidth=1,
            relief="solid",
            font=("Consolas", 9),
        )
        scrollbar = ttk.Scrollbar(results, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        self.results_text.grid(row=0, column=0, sticky=(tk.N, tk.S, tk.W, tk.E))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.append_result("[SYSTEM] Ready.\n")
        self.append_result("[WARN] Generated private keys control real assets. Store them securely.\n")

    def show_protocol_constraints(self) -> None:
        constraints = {
            "bitcoin": "Bitcoin P2PKH\nAllowed pattern characters: Base58 without 0, O, I, or l.\nSearch ignores the fixed leading address prefix: 1.",
            "ethereum": "Ethereum\nAllowed pattern characters: hexadecimal 0-9 and a-f.\nSearch ignores the fixed leading address prefix: 0x.",
            "tor": "Tor v3 onion\nAllowed pattern characters: Base32 a-z and 2-7.\nSearch ignores the fixed trailing suffix: .onion.",
        }
        messagebox.showinfo("Pattern Constraints", constraints[self.crypto_var.get()])

    def on_crypto_change(self, *_args: object) -> None:
        if self.crypto_var.get() == "bitcoin":
            self.compressed_check.grid()
        else:
            self.compressed_check.grid_remove()
            self.compressed_var.set(False)
        self.on_pattern_change()

    def on_position_change(self, *_args: object) -> None:
        if self.position_var.get() == "both":
            self.end_pattern_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(2, 4))
        else:
            self.end_pattern_frame.grid_remove()
        self.on_pattern_change()

    def on_compute_change(self, *_args: object) -> None:
        if self.compute_var.get() == "gpu" and not self.gpu_devices:
            self.compute_var.set("cpu")
            return
        if not self.is_generating:
            self.refresh_idle_estimate()

    def on_gpu_device_change(self, _event: object | None = None) -> None:
        if not self.is_generating:
            self.refresh_idle_estimate()

    def on_estimate_input_change(self, *_args: object) -> None:
        if not self.is_generating:
            self.refresh_idle_estimate()

    def on_pattern_change(self, *_args: object) -> None:
        crypto = self.crypto_var.get()
        pattern = self.pattern_var.get()
        valid, error = validate_pattern(pattern, crypto)
        self.pattern_validation_label.config(text="" if valid else error)

        if self.position_var.get() == "both":
            end_valid, end_error = validate_pattern(self.end_pattern_var.get(), crypto)
            self.end_pattern_validation_label.config(text="" if end_valid else end_error)

        if not self.is_generating:
            self.refresh_idle_estimate()

    def refresh_idle_estimate(self) -> None:
        pattern = self.pattern_var.get().strip()
        if not pattern:
            self.time_est_var.set("Unknown")
            return

        try:
            count = max(1, int(self.count_var.get()))
        except ValueError:
            count = 1

        difficulty = estimate_difficulty(pattern, self.position_var.get(), self.crypto_var.get(), self.end_pattern_var.get())
        self.time_est_var.set(self.format_time_estimate(difficulty, count))

    def validate_inputs(self) -> GenerationConfig | None:
        crypto = self.crypto_var.get()
        pattern = self.pattern_var.get().strip()
        end_pattern = self.end_pattern_var.get().strip() if self.position_var.get() == "both" else ""
        position = self.position_var.get()
        compute_mode = self.compute_var.get()
        gpu_device_key = ""

        if not pattern:
            messagebox.showerror("Missing Pattern", "Enter a pattern to search for.")
            return None

        valid, error = validate_pattern(pattern, crypto)
        if not valid:
            messagebox.showerror("Invalid Pattern", error)
            return None

        if position == "both":
            if not end_pattern:
                messagebox.showerror("Missing End Pattern", "Enter an end pattern for the Both position.")
                return None
            end_valid, end_error = validate_pattern(end_pattern, crypto)
            if not end_valid:
                messagebox.showerror("Invalid End Pattern", end_error)
                return None
            combined_limit = searchable_address_length(crypto)
            if len(pattern) + len(end_pattern) > combined_limit:
                messagebox.showerror(
                    "Patterns Too Long",
                    f"The start and end patterns together need {len(pattern) + len(end_pattern)} characters, "
                    f"but this target has at most {combined_limit} searchable characters. "
                    "No address can satisfy both patterns.",
                )
                return None

        try:
            target_count = int(self.count_var.get())
            if target_count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Max Results", "Enter a positive max result count.")
            return None

        try:
            thread_count = int(self.threads_var.get())
            if thread_count <= 0 or thread_count > MAX_WORKERS:
                raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Worker Count", f"Enter a worker count between 1 and {MAX_WORKERS}.")
            return None

        if compute_mode == "gpu":
            if not self.gpu_devices:
                messagebox.showerror("GPU Unavailable", "No OpenCL GPU device was detected.")
                return None
            gpu_device_key = self.gpu_device_labels.get(self.gpu_device_var.get(), "")
            if not gpu_device_key:
                messagebox.showerror("GPU Unavailable", "Select a valid OpenCL GPU device.")
                return None

        return GenerationConfig(
            crypto=crypto,
            pattern=pattern,
            end_pattern=end_pattern,
            position=position,
            target_count=target_count,
            thread_count=thread_count,
            compressed=self.compressed_var.get() if crypto == "bitcoin" else False,
            compute_mode=compute_mode,
            gpu_device_key=gpu_device_key,
            output_path=self.create_output_path(crypto, pattern, position, end_pattern),
        )

    def start_generation(self) -> None:
        if self.is_generating or self.is_calibrating:
            return

        config = self.validate_inputs()
        if config is None:
            return

        self.start_calibration(config)

    def start_calibration(self, config: GenerationConfig) -> None:
        self.is_calibrating = True
        self.calibration_stop_event.clear()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("CALIBRATING")
        self.progress_bar.start(12)
        self.speed_var.set("Measuring...")
        self.time_est_var.set("Calibrating...")
        self.append_result(
            f"\n[BENCH] Measuring real {config.compute_mode.upper()} speed for {config.thread_count} worker"
            f"{'s' if config.thread_count != 1 else ''}. This can take a few seconds.\n"
        )

        self.calibration_thread = threading.Thread(
            target=self.calibration_worker,
            args=(config,),
            daemon=True,
        )
        self.calibration_thread.start()

    def calibration_worker(self, config: GenerationConfig) -> None:
        gpu_matcher: GPUAddressMatcher | None = None
        try:
            if config.compute_mode == "gpu":
                gpu_matcher = GPUAddressMatcher(config.gpu_device_key)

            speed = self.measure_generation_speed(config, gpu_matcher)
            self.result_queue.put(
                {
                    "calibration": True,
                    "config": config,
                    "speed": speed,
                    "gpu_matcher": gpu_matcher,
                }
            )
        except Exception as exc:
            self.result_queue.put({"calibration_error": f"Calibration failed: {exc}"})

    def measure_generation_speed(
        self,
        config: GenerationConfig,
        gpu_matcher: GPUAddressMatcher | None,
    ) -> float:
        generator_type = GENERATOR_TYPES[config.crypto]
        worker_count = max(1, config.thread_count)
        counts = [0 for _ in range(worker_count)]
        errors: list[Exception] = []
        gpu_lock = threading.Lock()

        def generate_address(generator: BitcoinGenerator | EthereumGenerator | TorGenerator) -> str:
            if config.crypto == "bitcoin":
                address, _material = generator.generate_candidate(config.compressed)  # type: ignore[attr-defined]
            else:
                address, _material = generator.generate_candidate()  # type: ignore[call-arg]
            return address

        def benchmark_cpu(worker_index: int) -> None:
            generator = generator_type()
            local_count = 0
            try:
                while not self.calibration_stop_event.is_set():
                    address = generate_address(generator)
                    matches_pattern(address, config.pattern, config.crypto, config.position, config.end_pattern)
                    local_count += 1
            except Exception as exc:
                errors.append(exc)
                self.calibration_stop_event.set()
            finally:
                counts[worker_index] = local_count

        def benchmark_gpu(worker_index: int) -> None:
            if gpu_matcher is None:
                raise RuntimeError("GPU matcher is not initialized.")

            generator = generator_type()
            local_count = 0
            batch_addresses: list[str] = []
            try:
                while not self.calibration_stop_event.is_set():
                    batch_addresses.append(generate_address(generator))
                    if len(batch_addresses) >= GPU_BATCH_SIZE:
                        with gpu_lock:
                            gpu_matcher.match_addresses(
                                batch_addresses,
                                config.pattern,
                                config.crypto,
                                config.position,
                                config.end_pattern,
                            )
                        local_count += len(batch_addresses)
                        batch_addresses = []
            except Exception as exc:
                errors.append(exc)
                self.calibration_stop_event.set()
            finally:
                if batch_addresses and gpu_matcher is not None:
                    with gpu_lock:
                        gpu_matcher.match_addresses(
                            batch_addresses,
                            config.pattern,
                            config.crypto,
                            config.position,
                            config.end_pattern,
                        )
                    local_count += len(batch_addresses)
                counts[worker_index] = local_count

        target = benchmark_gpu if config.compute_mode == "gpu" else benchmark_cpu
        started_at = time.perf_counter()
        threads = [
            threading.Thread(target=target, args=(worker_index,), daemon=True)
            for worker_index in range(worker_count)
        ]
        for thread in threads:
            thread.start()

        while time.perf_counter() - started_at < BENCHMARK_SECONDS and not self.calibration_stop_event.is_set():
            time.sleep(0.05)

        self.calibration_stop_event.set()
        for thread in threads:
            thread.join(timeout=5.0)

        elapsed = max(0.001, time.perf_counter() - started_at)
        if errors:
            raise RuntimeError(errors[0])
        return sum(counts) / elapsed

    def finish_calibration(
        self,
        config: GenerationConfig,
        speed: float,
        gpu_matcher: GPUAddressMatcher | None,
    ) -> None:
        if not self.is_calibrating:
            return

        self.is_calibrating = False
        self.calibration_thread = None
        self.measured_speed_cache[self.speed_cache_key(config)] = speed
        self.gpu_matcher = gpu_matcher if config.compute_mode == "gpu" else None

        measured_speed = max(1.0, speed)
        difficulty = estimate_difficulty(config.pattern, config.position, config.crypto, config.end_pattern)
        # Expected attempts = target_count x difficulty (mean of the geometric
        # distribution); earlier versions halved it and understated times ~2x.
        expected = self.format_time_estimate_from_seconds(
            (difficulty * max(1, config.target_count)) / measured_speed
        )
        self.speed_var.set(f"{int(measured_speed):,} addr/sec")
        self.time_est_var.set(expected)
        self.append_result(
            f"[BENCH] Measured {int(measured_speed):,} addr/sec on this hardware. Estimated time: {expected}.\n"
        )

        if difficulty > 1_000_000:
            answer = messagebox.askyesno(
                "Difficult Pattern Warning",
                f"This pattern can take a long time.\n\nEstimated time: {expected}\nEstimated average attempts: {int((difficulty / 2) * config.target_count):,}\n\nContinue?",
            )
            if not answer:
                self.reset_to_ready()
                return

        self.launch_generation(config)

    def fail_calibration(self, error: str) -> None:
        if not self.is_calibrating:
            return
        self.is_calibrating = False
        self.calibration_thread = None
        self.gpu_matcher = None
        self.append_result(f"[ERROR] {error}\n")
        self.reset_to_ready()
        messagebox.showerror("Calibration Failed", error)

    def launch_generation(self, config: GenerationConfig) -> None:
        # Make sure workers from a previous run have fully stopped and flushed
        # their attempt counters before resetting shared state, otherwise a
        # late flush could corrupt the fresh totals.
        for thread in self.generator_threads:
            thread.join(timeout=2.0)
        self.generator_threads.clear()

        self.current_config = config
        self.is_generating = True
        self.completion_notice_shown = False
        self.stop_event.clear()

        with self._lock:
            self.total_attempts = 0
            self.found_count = 0

        self.start_time = time.perf_counter()
        self.last_update_time = self.start_time
        self.last_attempts = 0
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("RUNNING")
        self.progress_bar.start(12)
        self.speed_var.set("0 addr/sec")
        self.attempts_var.set("0")
        self.found_var.set("0 addresses")

        self.append_result(
            f"\n[START] {config.crypto.upper()} search | pattern={config.pattern!r} | position={config.position.upper()} | workers={config.thread_count} | compute={config.compute_mode.upper()}\n"
        )
        if self.gpu_matcher:
            self.append_result(f"[GPU] {self.gpu_matcher.device_label}\n")
        if config.position == "both":
            self.append_result(f"[TARGET] end_pattern={config.end_pattern!r}\n")
        self.append_result(f"[OUTPUT] {config.output_path}\n")

        generator_type = GENERATOR_TYPES[config.crypto]
        for thread_id in range(config.thread_count):
            thread = threading.Thread(
                target=self.generation_worker,
                args=(generator_type, config, thread_id),
                daemon=True,
            )
            thread.start()
            self.generator_threads.append(thread)

    def generation_worker(
        self,
        generator_type: Type[BitcoinGenerator] | Type[EthereumGenerator] | Type[TorGenerator],
        config: GenerationConfig,
        thread_id: int,
    ) -> None:
        if config.compute_mode == "gpu":
            self.gpu_generation_worker(generator_type, config, thread_id)
            return

        generator = generator_type()
        thread_attempts = 0
        pending_attempts = 0

        try:
            while not self.stop_event.is_set():
                if config.crypto == "bitcoin":
                    address, material = generator.generate_candidate(config.compressed)  # type: ignore[attr-defined]
                else:
                    address, material = generator.generate_candidate()  # type: ignore[call-arg]

                thread_attempts += 1
                pending_attempts += 1

                if pending_attempts >= STATS_BATCH_SIZE:
                    self.record_attempts(pending_attempts)
                    pending_attempts = 0

                if matches_pattern(address, config.pattern, config.crypto, config.position, config.end_pattern):
                    if pending_attempts:
                        total_after_flush = self.record_attempts(pending_attempts)
                        pending_attempts = 0
                    else:
                        with self._lock:
                            total_after_flush = self.total_attempts

                    with self._lock:
                        if self.found_count >= config.target_count:
                            self.stop_event.set()
                            break
                        self.found_count += 1
                        match_number = self.found_count
                        total_attempts = total_after_flush
                        if self.found_count >= config.target_count:
                            self.stop_event.set()

                    final_address, private_key = generator.finalize_match(address, material)  # type: ignore[arg-type]
                    self.result_queue.put(
                        {
                            "address": final_address,
                            "private_key": private_key,
                            "match_number": match_number,
                            "thread_id": thread_id,
                            "thread_attempts": thread_attempts,
                            "total_attempts": total_attempts,
                            "config": config,
                        }
                    )
        except Exception as exc:
            self.stop_event.set()
            self.result_queue.put({"error": f"Worker {thread_id} failed: {exc}"})
        finally:
            if pending_attempts:
                self.record_attempts(pending_attempts)

    def gpu_generation_worker(
        self,
        generator_type: Type[BitcoinGenerator] | Type[EthereumGenerator] | Type[TorGenerator],
        config: GenerationConfig,
        thread_id: int,
    ) -> None:
        generator = generator_type()
        thread_attempts = 0
        batch_addresses: list[str] = []
        batch_materials: list[object] = []
        batch_thread_attempts: list[int] = []

        try:
            while not self.stop_event.is_set():
                if config.crypto == "bitcoin":
                    address, material = generator.generate_candidate(config.compressed)  # type: ignore[attr-defined]
                else:
                    address, material = generator.generate_candidate()  # type: ignore[call-arg]

                thread_attempts += 1
                batch_addresses.append(address)
                batch_materials.append(material)
                batch_thread_attempts.append(thread_attempts)

                if len(batch_addresses) >= GPU_BATCH_SIZE:
                    self.process_gpu_batch(config, thread_id, batch_addresses, batch_materials, batch_thread_attempts)
                    batch_addresses = []
                    batch_materials = []
                    batch_thread_attempts = []
        except Exception as exc:
            self.stop_event.set()
            self.result_queue.put({"error": f"Worker {thread_id} failed: {exc}"})
        finally:
            if batch_addresses:
                self.process_gpu_batch(config, thread_id, batch_addresses, batch_materials, batch_thread_attempts)

    def process_gpu_batch(
        self,
        config: GenerationConfig,
        thread_id: int,
        addresses: list[str],
        materials: list[object],
        thread_attempts: list[int],
    ) -> None:
        if not addresses:
            return
        if self.gpu_matcher is None:
            raise RuntimeError("GPU matcher is not initialized.")

        total_after_batch = self.record_attempts(len(addresses))
        first_total_attempt = total_after_batch - len(addresses) + 1

        with self.gpu_lock:
            matched_indices = self.gpu_matcher.match_addresses(
                addresses,
                config.pattern,
                config.crypto,
                config.position,
                config.end_pattern,
            )

        for index in matched_indices:
            with self._lock:
                if self.found_count >= config.target_count:
                    self.stop_event.set()
                    return
                self.found_count += 1
                match_number = self.found_count
                if self.found_count >= config.target_count:
                    self.stop_event.set()

            final_address, private_key = GENERATOR_TYPES[config.crypto].finalize_match(addresses[index], materials[index])  # type: ignore[arg-type]
            self.result_queue.put(
                {
                    "address": final_address,
                    "private_key": private_key,
                    "match_number": match_number,
                    "thread_id": thread_id,
                    "thread_attempts": thread_attempts[index],
                    "total_attempts": first_total_attempt + index,
                    "config": config,
                }
            )

    def record_attempts(self, attempts: int) -> int:
        with self._lock:
            self.total_attempts += attempts
            return self.total_attempts

    def check_queue(self) -> None:
        try:
            while True:
                result = self.result_queue.get_nowait()
                if "calibration" in result:
                    self.finish_calibration(result["config"], result["speed"], result["gpu_matcher"])
                elif "calibration_error" in result:
                    self.fail_calibration(result["calibration_error"])
                elif "error" in result:
                    self.append_result(f"[ERROR] {result['error']}\n")
                    self.finish_generation("ERROR", show_dialog=False)
                else:
                    self.display_match(result)
                    self.save_result(result)
        except queue.Empty:
            pass

        if self.is_generating and self.generator_threads and all(not thread.is_alive() for thread in self.generator_threads):
            with self._lock:
                found_count = self.found_count
            if self.current_config and found_count >= self.current_config.target_count:
                self.finish_generation("COMPLETE", show_dialog=True)
            elif self.stop_event.is_set():
                self.finish_generation("STOPPED", show_dialog=False)

        self.root.after(100, self.check_queue)

    def display_match(self, result: dict) -> None:
        config: GenerationConfig = result["config"]
        type_info = config.crypto.upper()
        if config.crypto == "bitcoin" and config.compressed:
            type_info += " COMPRESSED"

        if config.position == "both":
            pattern_info = f"start={config.pattern!r} end={config.end_pattern!r}"
        else:
            pattern_info = f"pattern={config.pattern!r} position={config.position.upper()}"

        self.found_var.set(f"{result['match_number']} addresses")
        self.append_result(
            "\n"
            f"[MATCH #{result['match_number']:03d}]\n"
            f"Address: {result['address']}\n"
            f"Private key:\n{result['private_key']}\n"
            f"Target: {pattern_info}\n"
            f"Type: {type_info}\n"
            f"Compute: {config.compute_mode.upper()}\n"
            f"Worker: {result['thread_id']} | Worker attempts: {result['thread_attempts']:,}\n"
            f"Total attempts: {result['total_attempts']:,} | Time: {datetime.now().strftime('%H:%M:%S')}\n"
        )

    def save_result(self, result: dict) -> None:
        config: GenerationConfig = result["config"]
        os.makedirs(config.output_path.parent, exist_ok=True)
        with config.output_path.open("a", encoding="utf-8") as file:
            file.write("VANITY ADDRESS FOUND\n")
            file.write("=" * 50 + "\n")
            file.write(f"Target: {config.crypto.title()}")
            if config.crypto == "bitcoin" and config.compressed:
                file.write(" (compressed)")
            file.write("\n")
            file.write(f"Compute mode: {config.compute_mode.upper()}\n")
            file.write(f"Address: {result['address']}\n")
            file.write(f"Private key:\n{result['private_key']}\n")
            if config.position == "both":
                file.write(f"Start pattern: {config.pattern}\n")
                file.write(f"End pattern: {config.end_pattern}\n")
            else:
                file.write(f"Pattern: {config.pattern}\n")
                file.write(f"Position: {config.position}\n")
            file.write(f"Worker ID: {result['thread_id']}\n")
            file.write(f"Worker attempts: {result['thread_attempts']:,}\n")
            file.write(f"Total attempts: {result['total_attempts']:,}\n")
            file.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            file.write("=" * 50 + "\n\n")

    def stop_generation(self) -> None:
        if self.is_calibrating:
            self.cancel_calibration()
            return
        self.finish_generation("STOPPED", show_dialog=False)

    def cancel_calibration(self) -> None:
        if not self.is_calibrating:
            return
        self.calibration_stop_event.set()
        self.is_calibrating = False
        self.calibration_thread = None
        self.gpu_matcher = None
        self.append_result("[BENCH] Calibration canceled.\n")
        self.reset_to_ready()

    def reset_to_ready(self) -> None:
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("READY")
        self.progress_bar.stop()
        self.speed_var.set("0 addr/sec")
        self.attempts_var.set("0")
        self.refresh_idle_estimate()

    def finish_generation(self, state: str, show_dialog: bool) -> None:
        if not self.is_generating:
            return

        self.stop_event.set()
        self.is_generating = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set(state)
        self.progress_bar.stop()

        with self._lock:
            attempts = self.total_attempts
            found = self.found_count

        elapsed = time.perf_counter() - self.start_time if self.start_time else 0
        self.append_result(
            f"\n[END] {state} | found={found} | attempts={attempts:,} | elapsed={self.format_time_estimate_from_seconds(elapsed)}\n"
        )

        if show_dialog and not self.completion_notice_shown:
            self.completion_notice_shown = True
            messagebox.showinfo(
                "Search Complete",
                f"Found {found} matching address{'es' if found != 1 else ''}.\n"
                f"Elapsed time: {self.format_time_estimate_from_seconds(elapsed)}\n"
                f"Total attempts: {attempts:,}",
            )

    def clear_results(self) -> None:
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete("1.0", tk.END)
        self.results_text.config(state=tk.DISABLED)
        self.append_result("[SYSTEM] Ready.\n")
        self.append_result("[WARN] Generated private keys control real assets. Store them securely.\n")
        with self._lock:
            self.total_attempts = 0
            self.found_count = 0
        self.speed_var.set("0 addr/sec")
        self.attempts_var.set("0")
        self.found_var.set("0 addresses")

    def update_stats(self) -> None:
        current_time = time.perf_counter()
        with self._lock:
            total_attempts = self.total_attempts
            found_count = self.found_count

        if self.is_generating and self.start_time:
            elapsed = current_time - self.last_update_time
            if elapsed >= 1.0:
                attempts_delta = total_attempts - self.last_attempts
                speed = attempts_delta / elapsed if elapsed > 0 else 0
                self.speed_var.set(f"{int(speed):,} addr/sec")
                self.attempts_var.set(f"{total_attempts:,}")
                self.found_var.set(f"{found_count} addresses")

                if self.current_config and speed > 0:
                    difficulty = estimate_difficulty(
                        self.current_config.pattern,
                        self.current_config.position,
                        self.current_config.crypto,
                        self.current_config.end_pattern,
                    )
                    expected_total = difficulty * max(1, self.current_config.target_count)
                    remaining = max(0, expected_total - total_attempts)
                    self.time_est_var.set(self.format_time_estimate_from_seconds(remaining / speed))

                self.last_update_time = current_time
                self.last_attempts = total_attempts
        else:
            self.attempts_var.set(f"{total_attempts:,}")
            self.found_var.set(f"{found_count} addresses")
            self.refresh_idle_estimate()

        self.root.after(1000, self.update_stats)

    def append_result(self, text: str) -> None:
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, text)
        self.results_text.config(state=tk.DISABLED)
        self.results_text.see(tk.END)

    def create_output_path(self, crypto: str, pattern: str, position: str, end_pattern: str) -> Path:
        output_dir = Path("output")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts = [crypto, "vanity", self.safe_filename(pattern)]
        if position == "both":
            parts.append(self.safe_filename(end_pattern))
        parts.append(timestamp)
        return output_dir / ("_".join(parts) + ".txt")

    @staticmethod
    def safe_filename(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
        return cleaned.strip("._") or "pattern"

    def format_time_estimate(
        self,
        difficulty: float,
        target_count: int = 1,
        *,
        crypto: str | None = None,
        thread_count: int | None = None,
        compute_mode: str | None = None,
        gpu_device_key: str | None = None,
    ) -> str:
        if difficulty == float("inf"):
            return "Unknown"
        crypto = crypto or self.crypto_var.get()
        threads = thread_count if thread_count is not None else self.current_thread_count_for_estimate()
        compute_mode = compute_mode or self.compute_var.get()
        gpu_device_key = gpu_device_key if gpu_device_key is not None else self.selected_gpu_device_key()
        total_speed = self.cached_measured_speed(crypto, threads, compute_mode, gpu_device_key)
        if total_speed is None:
            total_speed = self.estimated_total_speed(crypto, threads, compute_mode, gpu_device_key)
        average_seconds = (difficulty * max(1, target_count)) / total_speed
        return self.format_time_estimate_from_seconds(average_seconds)

    def current_thread_count_for_estimate(self) -> int:
        try:
            return max(1, min(MAX_WORKERS, int(self.threads_var.get())))
        except ValueError:
            return 1

    def selected_gpu_device_key(self) -> str:
        return self.gpu_device_labels.get(self.gpu_device_var.get(), "")

    @staticmethod
    def speed_cache_key(config: GenerationConfig) -> tuple[str, str, int, bool, str]:
        # Speed does not measurably depend on the pattern itself, so pattern
        # fields are excluded to let the calibration cache be reused across
        # different patterns instead of forcing a new benchmark every time.
        gpu_key = config.gpu_device_key if config.compute_mode == "gpu" else ""
        return (
            config.crypto,
            config.compute_mode,
            config.thread_count,
            config.compressed,
            gpu_key,
        )

    def cached_measured_speed(
        self,
        crypto: str,
        thread_count: int,
        compute_mode: str,
        gpu_device_key: str,
    ) -> float | None:
        compressed = self.compressed_var.get() if crypto == "bitcoin" else False
        gpu_key = gpu_device_key if compute_mode == "gpu" else ""
        return self.measured_speed_cache.get(
            (
                crypto,
                compute_mode,
                thread_count,
                compressed,
                gpu_key,
            )
        )

    def estimated_total_speed(
        self,
        crypto: str,
        thread_count: int,
        compute_mode: str,
        gpu_device_key: str = "",
    ) -> int:
        threads = max(1, min(MAX_WORKERS, thread_count))
        cpu_speed = BASE_SPEED_BY_TARGET[crypto] * threads
        if compute_mode != "gpu":
            return max(1, int(cpu_speed))

        device = next((candidate for candidate in self.gpu_devices if candidate.key == gpu_device_key), None)
        compute_units = device.compute_units if device else GPU_REFERENCE_COMPUTE_UNITS
        device_scale = min(GPU_COMPUTE_UNIT_SCALE_LIMIT, max(1.0, compute_units / GPU_REFERENCE_COMPUTE_UNITS))
        multiplier = GPU_SPEED_MULTIPLIER_BY_TARGET[crypto] * device_scale
        return max(1, int(cpu_speed * multiplier))

    @staticmethod
    def format_time_estimate_from_seconds(seconds: float) -> str:
        if seconds < 1:
            return "< 1 second"
        if seconds < 60:
            return f"{int(seconds)} sec"
        if seconds < 3600:
            return f"{int(seconds / 60)} min"
        if seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m" if minutes else f"{hours}h"
        if seconds < 604800:
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            return f"{days}d {hours}h" if hours else f"{days}d"
        if seconds < 31556952:
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''}"
        years = int(seconds / 31556952)
        return f"{years} year{'s' if years != 1 else ''}"


def main() -> None:
    root = tk.Tk()
    app = VanityAddressGUI(root)

    def on_closing() -> None:
        if app.is_generating:
            if not messagebox.askokcancel("Quit", "Generation is running. Stop and quit?"):
                return
            app.stop_generation()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
