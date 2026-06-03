import tkinter as tk
from tkinter import simpledialog, messagebox
import numpy as np
import math
import copy
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# --- Constants & Config ---
GRID_SIZE = 40
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
SNAP_TOLERANCE = 10
CLICK_THRESHOLD = 15

# Component Types
TYPE_WIRE = "Wire"
TYPE_RESISTOR = "Resistor"
TYPE_CAPACITOR = "Capacitor"
TYPE_INDUCTOR = "Inductor"
TYPE_V_SOURCE = "Voltage Source"
TYPE_I_SOURCE = "Current Source"

class Component:
    def __init__(self, c_type, start, end, value=0):
        self.type = c_type
        self.start = start
        self.end = end
        self.value = value
        self.nodes = [None, None] 
        self.v_prev = 0.0
        self.i_prev = 0.0

    def __repr__(self):
        return f"{self.type} ({self.value}) {self.start}->{self.end}"

class CircuitSimulator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python Circuit Simulator (State Preservation)")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.configure(bg="#f0f0f0")

        self.components = []
        self.history = []
        self.redo_history = []
        self.current_tool = None
        self.temp_start = None
        
        
        self.has_run_before = False 
        
        self._init_ui()
        
        
        self.bind("<Control-z>", lambda event: self.undo())
        self.bind("<Command-z>", lambda event: self.undo()) 
        self.bind("<Control-y>", lambda event: self.redo())
        self.bind("<Command-y>", lambda event: self.redo())

    def _init_ui(self):
        
        toolbar = tk.Frame(self, width=80, bg="#ffffff", relief="raised", bd=1)
        toolbar.pack(side="left", fill="y")
        
        tk.Label(toolbar, text="Tools", bg="white", font=("Arial", 10, "bold")).pack(pady=10)

        tools = [
            ("Wire", TYPE_WIRE),
            ("Resistor", TYPE_RESISTOR),
            ("Volt Source", TYPE_V_SOURCE),
            ("Curr Source", TYPE_I_SOURCE),
            ("Capacitor", TYPE_CAPACITOR),
            ("Inductor", TYPE_INDUCTOR)
        ]

        self.btn_map = {}
        for name, mode in tools:
            btn = tk.Button(toolbar, text=name, width=10, height=2, 
                            command=lambda m=mode: self.set_tool(m), relief="flat", bg="#e0e0e0")
            btn.pack(pady=2, padx=5)
            self.btn_map[mode] = btn

        # Undo Button
        tk.Button(toolbar, text="⟲ Undo", bg="#fff9c4", command=self.undo).pack(pady=10, padx=5)
        
        # Redo Button
        tk.Button(toolbar, text="⟳ Redo", bg="#14e4ff", command=self.redo).pack(pady=0, padx=5)

        # Clear Button
        tk.Button(toolbar, text="Clear All", bg="#ffcccc", command=self.clear_all).pack(pady=10, padx=5)

       
        top_bar = tk.Frame(self, height=50, bg="#ffffff")
        top_bar.pack(side="top", fill="x")

        title = tk.Label(top_bar, text="Circuit Solver", font=("Helvetica", 16), bg="white")
        title.pack(side="left", padx=20)
        
        sub = tk.Label(top_bar, text="(Node 0 is Auto-Ground)", font=("Arial", 10), bg="white", fg="gray")
        sub.pack(side="left", padx=5)
        
        
        btn_frame = tk.Frame(top_bar, bg="white")
        btn_frame.pack(side="right", padx=20, pady=5)

        # Reset IC Button
        reset_btn = tk.Button(btn_frame, text="Reset IC", bg="#ff9800", fg="white", 
                              font=("Arial", 10, "bold"), padx=10, command=self.reset_ic)
        reset_btn.pack(side="left", padx=5)

        run_btn = tk.Button(btn_frame, text="▶ Run Analysis", bg="#28a745", fg="white", 
                            font=("Arial", 12, "bold"), padx=15, command=self.run_transient_analysis)
        run_btn.pack(side="left", padx=5)

        # --- Main Canvas ---
        self.canvas = tk.Canvas(self, bg="white", cursor="cross")
        self.canvas.pack(side="right", fill="both", expand=True)

        self._draw_grid()
        
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Motion>", self.on_mouse_move)

    def _draw_grid(self):
        w = WINDOW_WIDTH
        h = WINDOW_HEIGHT
        for i in range(0, w, GRID_SIZE):
            for j in range(0, h, GRID_SIZE):
                self.canvas.create_oval(i-1, j-1, i+1, j+1, fill="#d0d0d0", outline="")

    def set_tool(self, mode):
        self.current_tool = mode
        self.temp_start = None
        for k, btn in self.btn_map.items():
            btn.configure(bg="#e0e0e0", relief="flat")
        self.btn_map[mode].configure(bg="#bbdefb", relief="sunken")

    def snap_to_grid(self, x, y):
        nx = round(x / GRID_SIZE) * GRID_SIZE
        ny = round(y / GRID_SIZE) * GRID_SIZE
        return nx, ny

    
    def save_state(self):
        
        self.history.append(copy.deepcopy(self.components))
        self.redo_history.clear()
        if len(self.history) > 50:
            self.history.pop(0)

    def undo(self):
        if not self.history:
            return
        self.redo_history.append(copy.deepcopy(self.components))
    
        self.components = self.history.pop()
        self.refresh_canvas()
    
    def redo(self):
        if not self.redo_history:
            return
            
        self.history.append(copy.deepcopy(self.components))
        
        self.components = self.redo_history.pop()
        self.refresh_canvas()
        
    def reset_ic(self):
        """Resets stored voltages/currents in components to zero."""
        for c in self.components:
            c.v_prev = 0.0
            c.i_prev = 0.0
        self.has_run_before = False
        messagebox.showinfo("Reset", "Initial conditions (states) cleared.\nNext run will start from 0.")

    
    def on_canvas_click(self, event):
        if not self.current_tool: return
        sx, sy = self.snap_to_grid(event.x, event.y)

        if self.temp_start is None:
            self.temp_start = (sx, sy)
        else:
            start, end = self.temp_start, (sx, sy)
            if start == end:
                self.temp_start = None
                return
            
            
            self.save_state()
            
            self.prompt_value_and_add(start, end)
            self.temp_start = None
            self.canvas.delete("preview_line")

    def on_mouse_move(self, event):
        if self.temp_start:
            sx, sy = self.snap_to_grid(event.x, event.y)
            self.canvas.delete("preview_line")
            self.canvas.create_line(self.temp_start[0], self.temp_start[1], sx, sy, 
                                    fill="gray", dash=(4, 2), tag="preview_line")

    def on_double_click(self, event):
        clicked_comp = self.get_component_at(event.x, event.y)
        if clicked_comp:
            
            self.edit_component(clicked_comp)

    def get_component_at(self, x, y):
        for comp in self.components:
            x1, y1 = comp.start
            x2, y2 = comp.end
            px, py = x2 - x1, y2 - y1
            norm_sq = px*px + py*py
            if norm_sq == 0: continue
            u = ((x - x1) * px + (y - y1) * py) / norm_sq
            if u > 1: u = 1
            elif u < 0: u = 0
            dx, dy = x1 + u * px - x, y1 + u * py - y
            if math.sqrt(dx*dx + dy*dy) < CLICK_THRESHOLD:
                return comp
        return None

    def edit_component(self, comp):
        new_val = None
        
        
        def ask_val(title, prompt, init, min_v=None):
            return simpledialog.askfloat(title, prompt, initialvalue=init, minvalue=min_v)

        if comp.type == TYPE_RESISTOR:
            new_val = ask_val("Edit", "Resistance (Ohms):", comp.value, 0.001)
        elif comp.type == TYPE_V_SOURCE:
            new_val = ask_val("Edit", "Voltage (Volts):", comp.value)
        elif comp.type == TYPE_I_SOURCE:
            new_val = ask_val("Edit", "Current (Amps):", comp.value)
        elif comp.type == TYPE_CAPACITOR:
            
            v = ask_val("Edit", "Capacitance (uF):", comp.value*1e6, 0.0001)
            if v: new_val = v * 1e-6
        elif comp.type == TYPE_INDUCTOR:
            
            v = ask_val("Edit", "Inductance (mH):", comp.value*1e3, 0.0001)
            if v: new_val = v * 1e-3
            
        if new_val is not None and new_val != comp.value: 
            self.save_state() 
            comp.value = new_val
            self.refresh_canvas()

    def refresh_canvas(self):
        self.canvas.delete("all")
        self._draw_grid()
        for comp in self.components:
            self.draw_component(comp)

    def clear_all(self):
        self.save_state()
        self.components = []
        self.has_run_before = False 
        self.refresh_canvas()

    def prompt_value_and_add(self, start, end):
        val = 0.0
        if self.current_tool not in [TYPE_WIRE]:
            if self.current_tool == TYPE_RESISTOR:
                val = simpledialog.askfloat("Input", "Resistance (Ohms):", minvalue=0.001)
            elif self.current_tool == TYPE_V_SOURCE:
                val = simpledialog.askfloat("Input", "Voltage (Volts):")
            elif self.current_tool == TYPE_I_SOURCE:
                val = simpledialog.askfloat("Input", "Current (Amps):")
            elif self.current_tool == TYPE_CAPACITOR:
                val = simpledialog.askfloat("Input", "Capacitance (uF):", minvalue=0.0001)
            elif self.current_tool == TYPE_INDUCTOR:
                val = simpledialog.askfloat("Input", "Inductance (mH):", minvalue=0.0001)
            
            if val is None: 
                
                if self.history: self.history.pop()
                return

        final_val = val
        if self.current_tool == TYPE_CAPACITOR and val: final_val = val * 1e-6
        if self.current_tool == TYPE_INDUCTOR and val: final_val = val * 1e-3
        
        comp = Component(self.current_tool, start, end, final_val if final_val else 0)
        self.components.append(comp)
        self.draw_component(comp)

    def draw_component(self, comp):
        x1, y1 = comp.start
        x2, y2 = comp.end
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        length = math.sqrt(dx*dx + dy*dy)
        if length == 0: return
        
        ux, uy = dx/length, dy/length
        px, py = -uy, ux
        width = 2
        text = ""

        if comp.type == TYPE_WIRE:
            self.canvas.create_line(x1, y1, x2, y2, width=width, fill="black")
        
        elif comp.type == TYPE_RESISTOR:
            num_zags, lead = 6, 10
            if length < 2 * lead: lead = length/4
            points = [(x1, y1), (x1 + ux*lead, y1 + uy*lead)]
            zig_len = length - 2*lead
            step = zig_len / (num_zags * 2)
            curr = lead
            for i in range(num_zags * 2):
                curr += step
                offset = 12 if i % 2 == 0 else -12
                points.append((x1 + ux*curr + px*offset, y1 + uy*curr + py*offset))
            points.append((x2 - ux*lead, y2 - uy*lead))
            points.append((x2, y2))
            flat = [c for p in points for c in p]
            self.canvas.create_line(*flat, width=width, fill="black")
            text = f"{comp.value}Ω"
            
        elif comp.type == TYPE_INDUCTOR:
            num_loops, lead = 4, 10
            if length < 2 * lead: lead = length/4
            self.canvas.create_line(x1, y1, x1+ux*lead, y1+uy*lead, width=width, fill="#4a148c")
            prev_x, prev_y = x1+ux*lead, y1+uy*lead
            coil_len = length - 2*lead
            loop_step = coil_len/num_loops
            start_dist = lead
            for i in range(num_loops):
                for j in range(11):
                    t = j/10
                    angle = math.pi * t
                    dist = start_dist + loop_step*i + loop_step*t
                    h = math.sin(angle) * 15
                    cx, cy = x1 + ux*dist + px*h, y1 + uy*dist + py*h
                    self.canvas.create_line(prev_x, prev_y, cx, cy, width=width, fill="#4a148c")
                    prev_x, prev_y = cx, cy
            self.canvas.create_line(prev_x, prev_y, x2, y2, width=width, fill="#4a148c")
            text = f"{comp.value*1000:.1f}mH"

        elif comp.type == TYPE_CAPACITOR:
            gap, plate_w = 6, 12
            p1_x, p1_y = mid_x - gap*ux, mid_y - gap*uy
            self.canvas.create_line(x1, y1, p1_x, p1_y, width=width)
            self.canvas.create_line(p1_x+px*plate_w, p1_y+py*plate_w, p1_x-px*plate_w, p1_y-py*plate_w, width=width)
            p2_x, p2_y = mid_x + gap*ux, mid_y + gap*uy
            self.canvas.create_line(p2_x+px*plate_w, p2_y+py*plate_w, p2_x-px*plate_w, p2_y-py*plate_w, width=width)
            self.canvas.create_line(p2_x, p2_y, x2, y2, width=width)
            text = f"{comp.value*1000000:.1f}uF"

        elif comp.type == TYPE_V_SOURCE:
            self.canvas.create_oval(mid_x-15, mid_y-15, mid_x+15, mid_y+15, outline="black", width=2)
            self.canvas.create_line(x1, y1, mid_x-15*ux, mid_y-15*uy, width=width)
            self.canvas.create_line(mid_x+15*ux, mid_y+15*uy, x2, y2, width=width)
            self.canvas.create_text(mid_x, mid_y, text="+  -", font=("Arial", 12, "bold"), angle=math.degrees(math.atan2(dy, dx)))
            text = f"{comp.value}V"

        elif comp.type == TYPE_I_SOURCE:
            self.canvas.create_oval(mid_x-15, mid_y-15, mid_x+15, mid_y+15, outline="black", width=2)
            self.canvas.create_line(x1, y1, mid_x-15*ux, mid_y-15*uy, width=width)
            self.canvas.create_line(mid_x+15*ux, mid_y+15*uy, x2, y2, width=width)
            self.canvas.create_line(mid_x-10*ux, mid_y-10*uy, mid_x+10*ux, mid_y+10*uy, arrow=tk.LAST, width=2)
            text = f"{comp.value}A"

        if text:
            self.canvas.create_text(mid_x + px*20, mid_y + py*20, text=text, fill="blue", font=("Arial", 9, "bold"))

    def draw_node_labels(self, node_map):
        self.canvas.delete("node_label")
        for coord, node_id in node_map.items():
            cx, cy = coord
            # N0 is Ground
            label_text = f"N{node_id}" if node_id != 0 else "GND"
            color = "#ffcccc" if node_id == 0 else "#ffffcc"
            
            self.canvas.create_oval(cx-3, cy-3, cx+3, cy+3, fill="red", outline="black", tag="node_label")
            self.canvas.create_rectangle(cx+5, cy-12, cx+35, cy+2, fill=color, outline="black", tag="node_label")
            self.canvas.create_text(cx+20, cy-5, text=label_text, fill="black", font=("Arial", 8, "bold"), tag="node_label")

    
    def run_transient_analysis(self):
        dt = simpledialog.askfloat("Simulation", "Time Step (seconds) (e.g., 0.001):", initialvalue=0.001, minvalue=0.000001)
        if not dt: return
        duration = simpledialog.askfloat("Simulation", "Duration (seconds) (e.g., 1.0):", initialvalue=1.0, minvalue=dt)
        if not duration: return

       
        node_map = {}
        node_counter = 0
        coords = set()
        for c in self.components:
            coords.add(c.start); coords.add(c.end)
        
        
        sorted_coords = sorted(list(coords), key=lambda k: (k[1], k[0]))
        
        for coord in sorted_coords:
            node_map[coord] = node_counter
            node_counter += 1

        num_nodes = node_counter
        if num_nodes < 2: 
            messagebox.showerror("Error", "Circuit must have at least 2 nodes.")
            return

        self.draw_node_labels(node_map)
        
        
        for c in self.components:
            c.nodes = [node_map[c.start], node_map[c.end]]
           
            if not self.has_run_before:
                c.v_prev = 0.0
                c.i_prev = 0.0
        
        
        self.has_run_before = True

        time_steps = int(duration / dt)
        times = np.linspace(0, duration, time_steps)
        history = {i: np.zeros(time_steps) for i in range(num_nodes)}
        
        voltage_sources = [c for c in self.components if c.type == TYPE_V_SOURCE]
        num_v_sources = len(voltage_sources)
        
        
        dim = (num_nodes - 1) + num_v_sources
        
        
        def get_idx(node_id): 
            return node_id - 1

        for t_idx, t in enumerate(times):
            A = np.zeros((dim, dim))
            z = np.zeros(dim)

            for c in self.components:
                n1, n2 = c.nodes
                idx1, idx2 = get_idx(n1), get_idx(n2)
                
                g_equiv = 0
                if c.type == TYPE_RESISTOR:
                    g_equiv = 1.0 / c.value
                elif c.type == TYPE_WIRE:
                    g_equiv = 1.0 / 0.000001
                elif c.type == TYPE_CAPACITOR:
                    g_equiv = c.value / dt
                elif c.type == TYPE_INDUCTOR:
                    g_equiv = dt / c.value
                elif c.type == TYPE_I_SOURCE:
                    if idx1 >= 0: z[idx1] -= c.value
                    if idx2 >= 0: z[idx2] += c.value
                    continue
                elif c.type == TYPE_V_SOURCE:
                    continue

                if idx1 >= 0: A[idx1, idx1] += g_equiv
                if idx2 >= 0: A[idx2, idx2] += g_equiv
                if idx1 >= 0 and idx2 >= 0:
                    A[idx1, idx2] -= g_equiv
                    A[idx2, idx1] -= g_equiv
                
                if c.type == TYPE_CAPACITOR:
                    val = g_equiv * c.v_prev
                    if idx1 >= 0: z[idx1] += val
                    if idx2 >= 0: z[idx2] -= val
                elif c.type == TYPE_INDUCTOR:
                    val = c.i_prev
                    if idx1 >= 0: z[idx1] -= val
                    if idx2 >= 0: z[idx2] += val

            for i, vs in enumerate(voltage_sources):
                row_idx = (num_nodes - 1) + i
                n_pos, n_neg = vs.nodes
                idx_pos, idx_neg = get_idx(n_pos), get_idx(n_neg)
                
                if idx_pos >= 0: 
                    A[row_idx, idx_pos] = 1
                    A[idx_pos, row_idx] = 1
                if idx_neg >= 0: 
                    A[row_idx, idx_neg] = -1
                    A[idx_neg, row_idx] = -1
                
                z[row_idx] = vs.value

            try:
                x = np.linalg.solve(A, z)
            except np.linalg.LinAlgError:
                break 
            
            # Extract Results
            step_voltages = {0: 0.0}
            for i in range(num_nodes - 1):
                step_voltages[i+1] = x[i]
            
            for nid in range(num_nodes):
                history[nid][t_idx] = step_voltages[nid]

            # Update States
            for c in self.components:
                n1, n2 = c.nodes
                v_new = step_voltages[n1] - step_voltages[n2]
                
                if c.type == TYPE_CAPACITOR:
                    c.v_prev = v_new
                elif c.type == TYPE_INDUCTOR:
                    g_equiv = dt / c.value
                    c.i_prev = c.i_prev + g_equiv * v_new

        self.show_plots(times, history, num_nodes)

    def show_plots(self, times, history, num_nodes):
        plot_window = tk.Toplevel(self)
        plot_window.title("Transient Response")
        plot_window.geometry("800x600")

        fig, ax = plt.subplots(figsize=(8, 6))
        
        for n_id in range(1, num_nodes): 
            ax.plot(times, history[n_id], label=f"Node {n_id}")

        ax.set_title("Voltage vs Time")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Voltage (V)")
        ax.grid(True)
        ax.legend()

        canvas = FigureCanvasTkAgg(fig, master=plot_window)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

if __name__ == "__main__":
    app = CircuitSimulator()
    app.mainloop()
    