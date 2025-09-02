"""
Vanity Address Generator
A multithreaded offline CPU-only vanity address generator for Bitcoin, Ethereum, and Tor (.onion)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import os
import time
import math
import multiprocessing
from datetime import datetime, timedelta
from vanity_generators import BitcoinGenerator, EthereumGenerator, TorGenerator


class VanityAddressGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Vanity Address Generator")
        self.root.geometry("900x750")
        self.root.resizable(True, True)
        
        # Configure style
        self.setup_styles()
        
        # Variables
        self.is_generating = False
        self.result_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.generator_threads = []
        
        # Thread-safe statistics tracking with lock
        self._lock = threading.Lock()
        self.start_time = None
        self.total_attempts = 0
        self.found_count = 0
        self.last_update_time = time.time()
        self.last_attempts = 0
        
        self.setup_ui()
        self.check_queue()
        self.update_stats()
        
    def setup_styles(self):
        """Configure custom dark hacker theme styles"""
        style = ttk.Style()
        
        # Dark hacker color scheme
        bg_dark = '#0d1117'        # GitHub dark background
        bg_darker = '#161b22'      # Darker sections
        bg_accent = '#21262d'      # Accent backgrounds
        fg_primary = '#c9d1d9'     # Primary text (light gray)
        fg_secondary = '#8b949e'   # Secondary text (medium gray)
        fg_accent = '#58a6ff'      # Accent text (blue)
        fg_success = '#3fb950'     # Success text (green)
        fg_warning = '#f85149'     # Warning/error text (red)
        fg_hacker = '#39ff14'      # Classic hacker green
        
        # Configure root window
        self.root.configure(bg=bg_dark)
        
        # Configure main styles
        style.theme_use('clam')  # Base theme
        
        # Configure frame styles
        style.configure('TFrame', background=bg_dark, borderwidth=0)
        style.configure('Card.TFrame', background=bg_darker, relief='flat', borderwidth=1)
        
        # Configure label styles
        style.configure('TLabel', background=bg_dark, foreground=fg_primary, font=('Consolas', 9))
        style.configure('Title.TLabel', background=bg_dark, foreground=fg_hacker, 
                       font=('Consolas', 20, 'bold'))
        style.configure('Subtitle.TLabel', background=bg_dark, foreground=fg_secondary, 
                       font=('Consolas', 10))
        style.configure('Heading.TLabel', background=bg_darker, foreground=fg_accent, 
                       font=('Consolas', 10, 'bold'))
        style.configure('Status.TLabel', background=bg_dark, foreground=fg_hacker, 
                       font=('Consolas', 10, 'bold'))
        style.configure('Stats.TLabel', background=bg_dark, foreground=fg_secondary, 
                       font=('Consolas', 9))
        style.configure('Success.TLabel', background=bg_dark, foreground=fg_success, 
                       font=('Consolas', 10, 'bold'))
        style.configure('Error.TLabel', background=bg_dark, foreground=fg_warning, 
                       font=('Consolas', 8))
        
        # Configure button styles
        style.configure('TButton', 
                       background=bg_accent, 
                       foreground=fg_primary, 
                       borderwidth=1,
                       focuscolor='none',
                       font=('Consolas', 9))
        style.map('TButton',
                 background=[('active', fg_accent), ('pressed', bg_darker)],
                 foreground=[('active', bg_dark)])
        
        style.configure('Start.TButton', 
                       background=fg_success, 
                       foreground=bg_dark, 
                       font=('Consolas', 10, 'bold'))
        style.map('Start.TButton',
                 background=[('active', '#2ea043'), ('pressed', '#238636')])
        
        style.configure('Stop.TButton', 
                       background=fg_warning, 
                       foreground=bg_dark, 
                       font=('Consolas', 10, 'bold'))
        style.map('Stop.TButton',
                 background=[('active', '#da3633'), ('pressed', '#b91c1c')])
        
        style.configure('Action.TButton', 
                       background=bg_accent, 
                       foreground=fg_accent, 
                       font=('Consolas', 9))
        
        # Configure entry styles
        style.configure('TEntry',
                       fieldbackground=bg_accent,
                       foreground=fg_primary,
                       borderwidth=1,
                       insertcolor=fg_hacker,
                       font=('Consolas', 11))
        style.map('TEntry',
                 focuscolor=[('!focus', bg_accent)],
                 fieldbackground=[('focus', bg_darker)])
        
        # Configure radiobutton styles
        style.configure('TRadiobutton',
                       background=bg_darker,
                       foreground=fg_primary,
                       focuscolor='none',
                       font=('Consolas', 9))
        style.map('TRadiobutton',
                 background=[('active', bg_darker)],
                 foreground=[('active', fg_accent)])
        
        # Configure checkbutton styles
        style.configure('TCheckbutton',
                       background=bg_darker,
                       foreground=fg_primary,
                       focuscolor='none',
                       font=('Consolas', 9))
        style.map('TCheckbutton',
                 background=[('active', bg_darker)],
                 foreground=[('active', fg_accent)])
        
        # Configure labelframe styles
        style.configure('TLabelframe',
                       background=bg_dark,
                       foreground=fg_accent,
                       borderwidth=1,
                       relief='solid')
        style.configure('TLabelframe.Label',
                       background=bg_dark,
                       foreground=fg_accent,
                       font=('Consolas', 11, 'bold'))
        
        # Configure progressbar styles
        style.configure('TProgressbar',
                       background=fg_hacker,
                       troughcolor=bg_accent,
                       borderwidth=0,
                       lightcolor=fg_hacker,
                       darkcolor=fg_hacker)
        
    def setup_ui(self):
        # Main frame with compact padding
        main_frame = ttk.Frame(self.root, style='TFrame', padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Window size optimization
        self.root.geometry("700x650")
        self.root.minsize(650, 600)
        
        # Compact header
        title_frame = ttk.Frame(main_frame, style='Card.TFrame', padding="10")
        title_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        
        header_label = ttk.Label(title_frame, text="⚡ VANITY GENERATOR ⚡", style='Title.TLabel', 
                                font=('Consolas', 16, 'bold'), justify='center')
        header_label.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        subtitle_label = ttk.Label(title_frame, text=">> OFFLINE CRYPTO ADDRESS GENERATOR <<", 
                                  style='Subtitle.TLabel', justify='center')
        subtitle_label.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(2, 0))
        
        # Configuration section - more compact
        config_frame = ttk.LabelFrame(main_frame, text=" ⚙ CONFIG ", padding="10", style='TLabelframe')
        config_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        config_frame.columnconfigure(1, weight=1)
        
        current_row = 0
        
        # Row 1: Crypto selection and Pattern in same row
        ttk.Label(config_frame, text="TARGET:", style='Heading.TLabel').grid(
            row=current_row, column=0, sticky=tk.W, pady=(0, 5))
        self.crypto_var = tk.StringVar(value="bitcoin")
        self.crypto_var.trace('w', self.on_crypto_change)
        self.compressed_var = tk.BooleanVar(value=False)  # Option for compressed Bitcoin keys
        crypto_frame = ttk.Frame(config_frame, style='TFrame')
        crypto_frame.grid(row=current_row, column=1, sticky=(tk.W, tk.E), pady=(0, 5))
        
        ttk.Radiobutton(crypto_frame, text="⚬ Bitcoin", variable=self.crypto_var, 
                       value="bitcoin", style='TRadiobutton').grid(row=0, column=0, padx=(0, 10))
        ttk.Radiobutton(crypto_frame, text="⚬ Ethereum", variable=self.crypto_var, 
                       value="ethereum", style='TRadiobutton').grid(row=0, column=1, padx=(0, 10))
        ttk.Radiobutton(crypto_frame, text="⚬ Tor (.onion)", variable=self.crypto_var, 
                       value="tor", style='TRadiobutton').grid(row=0, column=2, padx=(0, 10))
        
        # Compressed option for Bitcoin (on second row of crypto_frame)
        self.compressed_check = ttk.Checkbutton(crypto_frame, text="⚡ Compressed", 
                                              variable=self.compressed_var, style='TCheckbutton')
        self.compressed_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        
        # Help button - fix the positioning
        help_button = ttk.Button(crypto_frame, text="?", width=3, style='Action.TButton',
                                command=self.show_protocol_constraints)
        help_button.grid(row=0, column=3, padx=(5, 0))
        
        current_row += 1
        
        # Row 2: Pattern and Position in same row
        pattern_pos_frame = ttk.Frame(config_frame, style='TFrame')
        pattern_pos_frame.grid(row=current_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        pattern_pos_frame.columnconfigure(1, weight=1)
        
        # Pattern
        ttk.Label(pattern_pos_frame, text="PATTERN:", style='Heading.TLabel').grid(
            row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.pattern_var = tk.StringVar()
        self.pattern_var.trace('w', self.on_pattern_change)
        pattern_entry = ttk.Entry(pattern_pos_frame, textvariable=self.pattern_var, 
                                 font=('Consolas', 10), width=15)
        pattern_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 15))
        
        # Position with "Both" option restored
        ttk.Label(pattern_pos_frame, text="POS:", style='Heading.TLabel').grid(
            row=0, column=2, sticky=tk.W, padx=(0, 5))
        self.position_var = tk.StringVar(value="start")
        self.position_var.trace('w', self.on_position_change)  # Add trace to handle Both option
        position_frame = ttk.Frame(pattern_pos_frame, style='TFrame')
        position_frame.grid(row=0, column=3, sticky=tk.W)
        
        ttk.Radiobutton(position_frame, text="Start", variable=self.position_var, 
                       value="start", style='TRadiobutton').grid(row=0, column=0, padx=(0, 5))
        ttk.Radiobutton(position_frame, text="End", variable=self.position_var, 
                       value="end", style='TRadiobutton').grid(row=0, column=1, padx=(0, 5))
        ttk.Radiobutton(position_frame, text="Both", variable=self.position_var, 
                       value="both", style='TRadiobutton').grid(row=0, column=2, padx=(0, 5))
        ttk.Radiobutton(position_frame, text="Any", variable=self.position_var, 
                       value="anywhere", style='TRadiobutton').grid(row=0, column=3)
        
        current_row += 1
        
        # Pattern validation label
        self.pattern_validation_label = ttk.Label(config_frame, text="", style='Error.TLabel')
        self.pattern_validation_label.grid(row=current_row, column=0, columnspan=2, sticky=tk.W, pady=(2, 5))
        
        current_row += 1
        
        # End pattern field (initially hidden, shows when "Both" is selected)
        self.end_pattern_frame = ttk.Frame(config_frame, style='TFrame')
        self.end_pattern_label = ttk.Label(self.end_pattern_frame, text="END PATTERN:", style='Heading.TLabel')
        self.end_pattern_label.grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        
        self.end_pattern_var = tk.StringVar()
        self.end_pattern_var.trace('w', self.on_pattern_change)
        self.end_pattern_entry = ttk.Entry(self.end_pattern_frame, textvariable=self.end_pattern_var, 
                                          font=('Consolas', 10), width=15)
        self.end_pattern_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
        
        # End pattern validation
        self.end_pattern_validation_label = ttk.Label(self.end_pattern_frame, text="", style='Error.TLabel')
        self.end_pattern_validation_label.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(2, 0))
        
        current_row += 1
        
        # Settings in same row - clarify what "Addresses" means
        settings_frame = ttk.Frame(config_frame, style='TFrame')
        settings_frame.grid(row=current_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 0))
        
        ttk.Label(settings_frame, text="MAX RESULTS:", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.count_var = tk.StringVar(value="5")
        count_entry = ttk.Entry(settings_frame, textvariable=self.count_var, width=5, font=('Consolas', 10))
        count_entry.grid(row=0, column=1, padx=(5, 15))
        
        ttk.Label(settings_frame, text="THREADS:", style='Heading.TLabel').grid(row=0, column=2, sticky=tk.W)
        self.threads_var = tk.StringVar(value=str(multiprocessing.cpu_count()))
        threads_entry = ttk.Entry(settings_frame, textvariable=self.threads_var, width=5, font=('Consolas', 10))
        threads_entry.grid(row=0, column=3, padx=(5, 0))
        
        current_row += 1
        
        # Control buttons - compact
        button_frame = ttk.Frame(main_frame, style='TFrame', padding="8")
        button_frame.grid(row=2, column=0, columnspan=3, pady=(0, 10))
        
        self.start_button = ttk.Button(button_frame, text="⚡ START", 
                                      command=self.start_generation, style='Start.TButton',
                                      width=10)
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="⏹ STOP", 
                                     command=self.stop_generation, state=tk.DISABLED, style='Stop.TButton',
                                     width=8)
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        
        self.clear_button = ttk.Button(button_frame, text="🗑 CLEAR", 
                                      command=self.clear_results, style='Action.TButton',
                                      width=8)
        self.clear_button.grid(row=0, column=2)
        
        # Statistics section with hacker styling
        stats_frame = ttk.LabelFrame(main_frame, text=" ⚡ SYSTEM STATUS ", padding="15", style='TLabelframe')
        stats_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        stats_frame.columnconfigure(1, weight=1)
        
        # Status with terminal-like display
        ttk.Label(stats_frame, text="[STATUS]:", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.status_var = tk.StringVar(value="READY")
        self.status_label = ttk.Label(stats_frame, textvariable=self.status_var, style='Status.TLabel')
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=(10, 0))
        
        # Progress bar with hacker colors
        self.progress_bar = ttk.Progressbar(stats_frame, mode='indeterminate', length=400, style='TProgressbar')
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 15))
        
        # Statistics display
        stats_display_frame = ttk.Frame(stats_frame)
        stats_display_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        stats_display_frame.columnconfigure(1, weight=1)
        stats_display_frame.columnconfigure(3, weight=1)
        
        # Speed
        ttk.Label(stats_display_frame, text="Speed:", style='Heading.TLabel').grid(row=0, column=0, sticky=tk.W)
        self.speed_var = tk.StringVar(value="0 addr/sec")
        ttk.Label(stats_display_frame, textvariable=self.speed_var, style='Stats.TLabel').grid(
            row=0, column=1, sticky=tk.W, padx=(10, 30))
        
        # Time estimation
        ttk.Label(stats_display_frame, text="Est. Time:", style='Heading.TLabel').grid(row=0, column=2, sticky=tk.W)
        self.time_est_var = tk.StringVar(value="Unknown")
        ttk.Label(stats_display_frame, textvariable=self.time_est_var, style='Stats.TLabel').grid(
            row=0, column=3, sticky=tk.W, padx=(10, 0))
        
        # Total attempts
        ttk.Label(stats_display_frame, text="Total Attempts:", style='Heading.TLabel').grid(row=1, column=0, sticky=tk.W, pady=(5, 0))
        self.attempts_var = tk.StringVar(value="0")
        ttk.Label(stats_display_frame, textvariable=self.attempts_var, style='Stats.TLabel').grid(
            row=1, column=1, sticky=tk.W, padx=(10, 30), pady=(5, 0))
        
        # Found count
        ttk.Label(stats_display_frame, text="Found:", style='Heading.TLabel').grid(row=1, column=2, sticky=tk.W, pady=(5, 0))
        self.found_count = 0
        self.found_var = tk.StringVar(value="0 addresses")
        ttk.Label(stats_display_frame, textvariable=self.found_var, style='Success.TLabel').grid(
            row=1, column=3, sticky=tk.W, padx=(10, 0), pady=(5, 0))
        
        # Results area - compact terminal styling
        results_frame = ttk.LabelFrame(main_frame, text=" ⚡ RESULTS ", padding="8", style='TLabelframe')
        results_frame.grid(row=4, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        
        # Results text with terminal styling - smaller height
        self.results_text = tk.Text(results_frame, height=8, wrap=tk.WORD, 
                                   font=('Consolas', 9), bg='#0d1117', fg='#39ff14',
                                   insertbackground='#39ff14', selectbackground='#21262d',
                                   selectforeground='#c9d1d9', borderwidth=1, relief='solid')
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        
        self.results_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Add initial text with security warnings
        self.results_text.insert(tk.END, "[SYSTEM] Vanity Hacker v2.0 - READY\n")
        self.results_text.insert(tk.END, "[WARN] ⚠ SECURITY: NEVER import private keys on websites! ⚠\n")
        self.results_text.insert(tk.END, "[WARN] ⚠ Keep private keys OFFLINE and SECURE! ⚠\n")
        self.results_text.insert(tk.END, "[INFO] Configure target and pattern...\n")
        self.results_text.config(state=tk.DISABLED)
        
        # Initialize crypto-specific UI state (after all variables are created)
        self.on_crypto_change()
        
    def on_position_change(self, *args):
        """Handle position radio button changes to show/hide end pattern field"""
        position = self.position_var.get()
        if position == "both":
            # Show end pattern field
            current_row = 3  # After pattern validation
            self.end_pattern_frame.grid(row=current_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(5, 5))
            self.end_pattern_frame.columnconfigure(1, weight=1)
        else:
            # Hide end pattern field
            self.end_pattern_frame.grid_remove()
        
        # Update pattern validation when position changes
        self.on_pattern_change()
        
        # Update validation and estimation
        self.on_pattern_change()
    
    def on_crypto_change(self, *args):
        """Handle cryptocurrency selection changes"""
        crypto = self.crypto_var.get()
        
        # Show/hide compressed option based on crypto selection
        if crypto == "bitcoin":
            self.compressed_check.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))
        else:
            self.compressed_check.grid_remove()  # Hide the checkbox
            self.compressed_var.set(False)  # Reset to uncompressed for non-Bitcoin
        
        # Also call pattern change to update validation
        self.on_pattern_change()
    
    def on_pattern_change(self, *args):
        """Handle pattern changes for real-time validation and estimation"""
        crypto = self.crypto_var.get()
        
        # Validate main pattern
        pattern = self.pattern_var.get().strip()
        if pattern:
            is_valid, error_msg = self.validate_pattern(pattern, crypto)
            if not is_valid:
                self.pattern_validation_label.config(text=error_msg.split('\n')[0])  # First line only
            else:
                self.pattern_validation_label.config(text="")
        else:
            self.pattern_validation_label.config(text="")
        
        # Validate end pattern if visible
        if self.position_var.get() == "both":
            end_pattern = self.end_pattern_var.get().strip()
            if end_pattern:
                is_valid_end, error_msg_end = self.validate_pattern(end_pattern, crypto)
                if not is_valid_end:
                    self.end_pattern_validation_label.config(text=error_msg_end.split('\n')[0])  # First line only
                else:
                    self.end_pattern_validation_label.config(text="")
            else:
                self.end_pattern_validation_label.config(text="")
    
    def show_protocol_constraints(self):
        """Show a help dialog with protocol constraints"""
        constraints = {
            "bitcoin": "Bitcoin (Base58):\n• Allowed: 1-9, A-Z, a-z\n• Excluded: 0, O, I, l\n• Example: 1A2b3C",
            "ethereum": "Ethereum (Hexadecimal):\n• Allowed: 0-9, a-f\n• Case insensitive\n• Example: dead, beef, cafe",
            "tor": "Tor .onion v3 (Base32):\n• Allowed: a-z, 2-7\n• No uppercase, no 0-1, 8-9\n• Example: god, test, hello\n• Note: v3 addresses = 56 characters + .onion"
        }
        
        crypto = self.crypto_var.get()
        messagebox.showinfo("Pattern Constraints", constraints[crypto])
        
    def validate_pattern(self, pattern, crypto):
        """
        Validate if pattern is valid for the selected cryptocurrency
        Returns: (is_valid, error_message)
        """
        if not pattern:
            return True, ""  # Empty pattern is valid, just no filtering
        
        if crypto == "bitcoin":
            # Bitcoin Base58 alphabet (no 0, O, I, l) - CASE SENSITIVE
            valid_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"
            invalid_chars = [c for c in pattern if c not in valid_chars]  # Keep original case
            if invalid_chars:
                return False, f"Bitcoin addresses cannot contain: {', '.join(set(invalid_chars))}\nAllowed: 1-9, A-Z, a-z (except: 0, O, I, l)"
        
        elif crypto == "ethereum":
            pattern = pattern.lower()  # Convert to lowercase for Ethereum
            # Ethereum hex alphabet (0-9, a-f only)
            valid_chars = "0123456789abcdef"
            invalid_chars = [c for c in pattern if c not in valid_chars]
            if invalid_chars:
                return False, f"Ethereum addresses can only contain hex characters: 0-9, a-f\nInvalid characters: {', '.join(set(invalid_chars))}"
        
        elif crypto == "tor":
            pattern = pattern.lower()  # Convert to lowercase for Tor
            # Tor Base32 alphabet (a-z, 2-7 only)
            valid_chars = "abcdefghijklmnopqrstuvwxyz234567"
            invalid_chars = [c for c in pattern if c not in valid_chars]
            if invalid_chars:
                return False, f"Tor addresses can only contain: a-z, 2-7\nInvalid characters: {', '.join(set(invalid_chars))}"
        
        return True, ""
    
    def get_charset_size(self, crypto):
        """Get the character set size for difficulty calculations"""
        if crypto == "bitcoin":
            return 58  # Base58
        elif crypto == "ethereum":
            return 16  # Hex (0-9, a-f)
        else:  # tor
            return 32  # Base32 (a-z, 2-7)
    
    def calculate_difficulty_estimate(self, pattern, position, crypto):
        """Calculate estimated difficulty and time for finding a pattern"""
        if not pattern:
            return float('inf'), "Unknown"
        
        # Validate pattern first
        is_valid, error_msg = self.validate_pattern(pattern, crypto)
        if not is_valid:
            return float('inf'), f"Invalid pattern: {error_msg}"
        
        charset_size = self.get_charset_size(crypto)
        pattern_len = len(pattern)
        end_pattern_len = len(self.end_pattern_var.get()) if position == "both" else 0
        
        if position == "start":
            difficulty = charset_size ** pattern_len
        elif position == "end":
            difficulty = charset_size ** pattern_len
        elif position == "both":
            # Validate end pattern too
            end_pattern = self.end_pattern_var.get().strip()
            if end_pattern:
                is_valid_end, error_msg_end = self.validate_pattern(end_pattern, crypto)
                if not is_valid_end:
                    return float('inf'), f"Invalid end pattern: {error_msg_end}"
            difficulty = charset_size ** (pattern_len + end_pattern_len)
        else:  # anywhere
            # For "anywhere", it's much easier - approximate as pattern_len with address length factor
            address_length = 34 if crypto == "bitcoin" else (40 if crypto == "ethereum" else 56)  # v3 onion = 56 chars
            positions_available = max(1, address_length - pattern_len + 1)
            difficulty = (charset_size ** pattern_len) / positions_available
        
        return difficulty, self.format_time_estimate(difficulty)
    
    def format_time_estimate(self, difficulty):
        """Format time estimate in human readable format with realistic speed"""
        if difficulty == float('inf'):
            return "Unknown"
        
        # Get realistic speeds based on our benchmarks
        threads = int(self.threads_var.get()) if self.threads_var.get().isdigit() else 4
        crypto = self.crypto_var.get()
        
        if crypto == "bitcoin":
            base_speed = 1500  # addresses per second per thread
        elif crypto == "ethereum":
            base_speed = 1600  # addresses per second per thread
        else:  # tor v3
            base_speed = 50  # Much slower for v3 onion addresses (Ed25519 + SHA3)
        
        total_speed = base_speed * threads
        
        # On average, we need to check half the possibilities
        avg_time_seconds = (difficulty / 2) / total_speed
        
        return self.format_time_estimate_from_seconds(avg_time_seconds)
    
    def update_stats(self):
        """Update statistics display with hacker formatting"""
        current_time = time.time()
        
        if self.is_generating and self.start_time:
            # Calculate speed
            time_elapsed = current_time - self.last_update_time
            if time_elapsed >= 1.0:  # Update every second
                attempts_diff = self.total_attempts - self.last_attempts
                speed = attempts_diff / time_elapsed if time_elapsed > 0 else 0
                
                self.speed_var.set(f"{int(speed):,} ADDR/SEC")
                self.attempts_var.set(f"{self.total_attempts:,}")
                
                # Update time estimation based on current speed and progress
                if speed > 0:
                    pattern = self.pattern_var.get()
                    position = self.position_var.get()
                    crypto = self.crypto_var.get()
                    difficulty, _ = self.calculate_difficulty_estimate(pattern, position, crypto)
                    
                    if difficulty != float('inf'):
                        remaining = difficulty - self.total_attempts
                        if remaining > 0:
                            est_seconds = remaining / speed
                            self.time_est_var.set(self.format_time_estimate_from_seconds(est_seconds))
                        else:
                            self.time_est_var.set("Any moment now...")
                
                self.last_update_time = current_time
                self.last_attempts = self.total_attempts
        else:
            # Show initial estimates
            pattern = self.pattern_var.get()
            position = self.position_var.get()
            crypto = self.crypto_var.get()
            _, time_est = self.calculate_difficulty_estimate(pattern, position, crypto)
            self.time_est_var.set(time_est)
        
        # Schedule next update
        self.root.after(1000, self.update_stats)
    
    def format_time_estimate_from_seconds(self, seconds):
        """Format time estimate from seconds"""
        if seconds < 1:
            return "< 1 second"
        elif seconds < 60:
            return f"{int(seconds)} sec"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            return f"{minutes} min"
        elif seconds < 86400:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            if minutes > 0:
                return f"{hours}h {minutes}m"
            else:
                return f"{hours}h"
        elif seconds < 604800:  # Less than a week
            days = int(seconds / 86400)
            hours = int((seconds % 86400) / 3600)
            if hours > 0:
                return f"{days}d {hours}h"
            else:
                return f"{days}d"
        elif seconds < 2629746:  # Less than a month
            weeks = int(seconds / 604800)
            return f"{weeks} week{'s' if weeks != 1 else ''}"
        elif seconds < 31556952:  # Less than a year
            months = int(seconds / 2629746)
            return f"{months} month{'s' if months != 1 else ''}"
        else:
            years = int(seconds / 31556952)
            if years < 10:
                months = int((seconds % 31556952) / 2629746)
                if months > 0:
                    return f"{years}y {months}m"
                else:
                    return f"{years} year{'s' if years != 1 else ''}"
            else:
                return f"{years} year{'s' if years != 1 else ''}"
    
    def start_generation(self):
        if self.is_generating:
            return
            
        # Validate inputs
        pattern = self.pattern_var.get().strip()
        if not pattern:
            messagebox.showerror("Error", "Please enter a pattern to search for")
            return
        
        # Validate pattern for selected cryptocurrency
        crypto = self.crypto_var.get()
        is_valid, error_msg = self.validate_pattern(pattern, crypto)
        if not is_valid:
            messagebox.showerror("Invalid Pattern", error_msg)
            return
        
        # Validate end pattern if "both" is selected
        if self.position_var.get() == "both":
            end_pattern = self.end_pattern_var.get().strip()
            if not end_pattern:
                messagebox.showerror("Error", "Please enter an end pattern when using 'Both' position")
                return
            
            is_valid_end, error_msg_end = self.validate_pattern(end_pattern, crypto)
            if not is_valid_end:
                messagebox.showerror("Invalid End Pattern", error_msg_end)
                return
            
        try:
            count = int(self.count_var.get())
            if count <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid positive number of addresses")
            return
        
        # Update UI state with hacker messaging
        self.is_generating = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("SCANNING...")
        self.progress_bar.start()
        
        # Log start message in terminal style
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, f"\n[SCAN] Initiating {crypto.upper()} address generation...\n")
        self.results_text.insert(tk.END, f"[TARGET] Pattern: '{pattern}' | Position: {self.position_var.get().upper()}\n")
        if self.position_var.get() == "both":
            self.results_text.insert(tk.END, f"[TARGET] End Pattern: '{end_pattern}'\n")
        
        try:
            thread_count = int(self.threads_var.get())
            if thread_count <= 0 or thread_count > 32:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid number of threads (1-32)")
            return
        
        # Add configuration message after validation
        self.results_text.insert(tk.END, f"[CONFIG] Max addresses: {count} | Threads: {thread_count}\n")
        self.results_text.config(state=tk.DISABLED)
        self.results_text.see(tk.END)
        
        # Show difficulty warning for very difficult patterns
        difficulty, time_est = self.calculate_difficulty_estimate(pattern, self.position_var.get(), crypto)
        if difficulty > 1000000:  # More than 1 million attempts expected
            response = messagebox.askyesno(
                "Difficult Pattern Warning", 
                f"This pattern may take a very long time to find.\n\n"
                f"Estimated time: {time_est}\n"
                f"Estimated attempts: {int(difficulty/2):,}\n\n"
                f"Do you want to continue?"
            )
            if not response:
                return
        
        # Start generation
        # Initialize generation state
        self.is_generating = True
        self.found_count = 0
        self.total_attempts = 0
        self.start_time = time.time()
        self.last_update_time = time.time()
        self.last_attempts = 0
        self.stop_event.clear()
        
        # Update UI with hacker styling
        self.speed_var.set("0 ADDR/SEC")
        self.attempts_var.set("0")
        self.found_var.set("0 ADDRESSES")
        
        # Get generator class
        if crypto == "bitcoin":
            generator_class = BitcoinGenerator
        elif crypto == "ethereum":
            generator_class = EthereumGenerator
        else:
            generator_class = TorGenerator
        
        # Start worker threads
        self.generator_threads = []
        for i in range(thread_count):
            thread = threading.Thread(
                target=self.generation_worker,
                args=(generator_class, pattern, self.position_var.get(), count, i),
                daemon=True
            )
            thread.start()
            self.generator_threads.append(thread)
    
    def generation_worker(self, generator_class, pattern, position, target_count, thread_id):
        generator = generator_class()
        attempts = 0
        pattern_lower = pattern.lower()
        end_pattern_lower = self.end_pattern_var.get().lower() if position == "both" else ""
        crypto_type = self.crypto_var.get()  # Get crypto type for pattern matching
        
        while not self.stop_event.is_set():
            try:
                # Generate address with compression support for Bitcoin
                if crypto_type == "bitcoin":
                    compressed = self.compressed_var.get()
                    address, private_key = generator.generate_address(compressed)
                else:
                    address, private_key = generator.generate_address()
                attempts += 1
                
                # Thread-safe increment with lock
                with self._lock:
                    self.total_attempts += 1
                    current_found = self.found_count
                    stop_now = (current_found >= target_count)
                
                if stop_now:
                    break
                
                # Check if address matches pattern - now includes crypto type
                if self.matches_pattern_enhanced(address, pattern_lower, end_pattern_lower, position, crypto_type):
                    result = {
                        'address': address,
                        'private_key': private_key,
                        'pattern': pattern,
                        'end_pattern': self.end_pattern_var.get() if position == "both" else "",
                        'position': position,
                        'crypto': crypto_type,
                        'compressed': self.compressed_var.get() if crypto_type == "bitcoin" else False,
                        'thread_id': thread_id,
                        'attempts': attempts,
                        'total_attempts': self.total_attempts
                    }
                    self.result_queue.put(result)
                    
                # Update status every 1000 attempts
                if attempts % 1000 == 0:
                    self.result_queue.put({
                        'status_update': f"Thread {thread_id}: {attempts:,} attempts",
                        'thread_attempts': attempts,
                        'thread_id': thread_id
                    })
                    
            except Exception as e:
                self.result_queue.put({'error': str(e)})
                break
    
    def matches_pattern_enhanced(self, address, pattern_lower, end_pattern_lower, position, crypto_type):
        """Enhanced pattern matching with support for both start and end patterns and crypto-specific handling"""
        address_lower = address.lower()
        
        # For Bitcoin addresses, remove the prefix when checking patterns
        if crypto_type == "bitcoin":
            if address_lower.startswith("1") or address_lower.startswith("3"):
                address_to_check = address[1:]  # Remove single char prefix - PRESERVE CASE
            elif address_lower.startswith("bc1q"):
                address_to_check = address[4:]  # Remove 'bc1q' prefix - PRESERVE CASE
            elif address_lower.startswith("bc1p"):
                address_to_check = address[4:]  # Remove 'bc1p' prefix - PRESERVE CASE
            elif address_lower.startswith("bc1"):
                address_to_check = address[3:]  # Remove 'bc1' prefix - PRESERVE CASE
            else:
                address_to_check = address  # Unknown format, use as-is - PRESERVE CASE
            
            # Bitcoin patterns are CASE SENSITIVE - don't use pattern_lower
            pattern_to_check = self.pattern_var.get()  # Original case
            end_pattern_to_check = self.end_pattern_var.get() if position == "both" else ""
        # For Ethereum addresses, remove the '0x' prefix when checking patterns
        elif crypto_type == "ethereum" and address_lower.startswith("0x"):
            address_to_check = address_lower[2:]  # Remove '0x' prefix
            pattern_to_check = pattern_lower
            end_pattern_to_check = end_pattern_lower
        # For Tor addresses, remove the '.onion' suffix when checking patterns
        elif crypto_type == "tor" and address_lower.endswith(".onion"):
            address_to_check = address_lower[:-6]  # Remove '.onion' suffix
            pattern_to_check = pattern_lower
            end_pattern_to_check = end_pattern_lower
        else:
            address_to_check = address_lower
            pattern_to_check = pattern_lower
            end_pattern_to_check = end_pattern_lower
        
        if position == "start":
            return address_to_check.startswith(pattern_to_check)
        elif position == "end":
            return address_to_check.endswith(pattern_to_check)
        elif position == "both":
            return address_to_check.startswith(pattern_to_check) and address_to_check.endswith(end_pattern_to_check)
        else:  # anywhere
            return pattern_to_check in address_to_check
    
    def check_queue(self):
        try:
            while True:
                result = self.result_queue.get_nowait()
                
                if 'error' in result:
                    self.results_text.config(state=tk.NORMAL)
                    self.results_text.insert(tk.END, f"[ERROR] {result['error']}\n")
                    self.results_text.config(state=tk.DISABLED)
                elif 'status_update' in result:
                    # Don't update status too frequently in UI, let update_stats handle it
                    pass
                else:
                    # Found a matching address - thread-safe increment
                    with self._lock:
                        self.found_count += 1
                        current_found = self.found_count
                    
                    self.found_var.set(f"{current_found} ADDRESSES")
                    
                    # Display result with hacker terminal formatting
                    if result['position'] == "both":
                        pattern_info = f"START: '{result['pattern']}' | END: '{result['end_pattern']}'"
                    else:
                        pattern_info = f"PATTERN: '{result['pattern']}' | POS: {result['position'].upper()}"
                    
                    # Prepare compression info for Bitcoin
                    if result['crypto'] == "bitcoin" and result.get('compressed', False):
                        type_info = f"{result['crypto'].upper()} (COMPRESSED)"
                    else:
                        type_info = result['crypto'].upper()
                    
                    result_text = (
                        f"\n[MATCH] ===== TARGET ACQUIRED #{self.found_count:03d} =====\n"
                        f"[ADDR] {result['address']}\n"
                        f"[PRIV] {result['private_key']}\n"
                        f"[META] {pattern_info}\n"
                        f"[TYPE] {type_info}\n"
                        f"[THRD] T{result['thread_id']:02d} | ATTEMPTS: {result['attempts']:,}\n"
                        f"[STAT] TOTAL: {result['total_attempts']:,} | TIME: {datetime.now().strftime('%H:%M:%S')}\n"
                        f"[====] ===============================================\n"
                    )
                    
                    self.results_text.config(state=tk.NORMAL)
                    self.results_text.insert(tk.END, result_text)
                    self.results_text.config(state=tk.DISABLED)
                    self.results_text.see(tk.END)
                    
                    # Save to file
                    self.save_result(result)
                    
                    # Check if we've found enough addresses
                    target_count = int(self.count_var.get())
                    if self.found_count >= target_count:
                        self.stop_generation()
                        elapsed = time.time() - self.start_time if self.start_time else 0
                        messagebox.showinfo("🎉 MISSION COMPLETE!", 
                                          f"ACQUIRED {self.found_count} TARGET ADDRESSES!\n"
                                          f"ELAPSED TIME: {self.format_time_estimate_from_seconds(elapsed)}\n"
                                          f"TOTAL SCANS: {self.total_attempts:,}")
                        
        except queue.Empty:
            pass
        
        # Schedule next check
        self.root.after(100, self.check_queue)
    
    def save_result(self, result):
        try:
            # Create output directory if it doesn't exist
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            
            # Create filename based on crypto and pattern
            crypto = result['crypto']
            pattern = result['pattern']
            if result['position'] == "both":
                pattern_part = f"{pattern}_{result['end_pattern']}"
            else:
                pattern_part = pattern
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{crypto}_vanity_{pattern_part}_{timestamp}.txt"
            filepath = os.path.join(output_dir, filename)
            
            # Write result to file
            with open(filepath, 'a', encoding='utf-8') as f:
                f.write(f"🎯 VANITY ADDRESS FOUND\n")
                f.write(f"{'='*50}\n")
                f.write(f"Cryptocurrency: {crypto.title()}")
                if crypto == "bitcoin" and result.get('compressed', False):
                    f.write(f" (Compressed)\n")
                else:
                    f.write(f"\n")
                f.write(f"Address: {result['address']}\n")
                f.write(f"Private Key: {result['private_key']}\n")
                
                if result['position'] == "both":
                    f.write(f"Start Pattern: {result['pattern']}\n")
                    f.write(f"End Pattern: {result['end_pattern']}\n")
                    f.write(f"Position: Both (start and end)\n")
                else:
                    f.write(f"Pattern: {result['pattern']}\n")
                    f.write(f"Position: {result['position'].title()}\n")
                
                f.write(f"Thread ID: {result['thread_id']}\n")
                f.write(f"Thread Attempts: {result['attempts']:,}\n")
                f.write(f"Total Attempts: {result['total_attempts']:,}\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"{'='*50}\n\n")
                
        except Exception as e:
            print(f"Error saving result: {e}")
    
    def stop_generation(self):
        if not self.is_generating:
            return
            
        self.stop_event.set()
        self.is_generating = False
        
        # Update UI with hacker messaging
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("TERMINATED")
        self.progress_bar.stop()
        
        # Log termination message
        self.results_text.config(state=tk.NORMAL)
        self.results_text.insert(tk.END, f"\n[SYSTEM] Scan terminated at {datetime.now().strftime('%H:%M:%S')}\n")
        self.results_text.insert(tk.END, f"[STATS] Final results: {self.found_count} addresses | {self.total_attempts:,} attempts\n")
        self.results_text.config(state=tk.DISABLED)
        self.results_text.see(tk.END)
        
        # Clear thread list
        self.generator_threads.clear()
    
    def clear_results(self):
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        # Add initial hacker messages again
        self.results_text.insert(tk.END, "[SYSTEM] Vanity Address Generator v2.0 - READY\n")
        self.results_text.insert(tk.END, "[INFO] Terminal cleared - Configure target and initiate scan...\n")
        self.results_text.config(state=tk.DISABLED)
        
        self.found_count = 0
        self.found_var.set("0 ADDRESSES")
        self.total_attempts = 0
        self.attempts_var.set("0")
        self.speed_var.set("0 ADDR/SEC")


def main():
    root = tk.Tk()
    app = VanityAddressGUI(root)
    
    # Handle window closing
    def on_closing():
        if app.is_generating:
            if messagebox.askokcancel("Quit", "Generation is running. Do you want to stop and quit?"):
                app.stop_generation()
                root.destroy()
        else:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
