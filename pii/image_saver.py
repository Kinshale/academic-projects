import numpy as np
import matplotlib.pyplot as plt
from ipywidgets import interact, interactive, ColorPicker, FloatSlider, IntSlider, Layout, Dropdown, Output, Box, VBox, HBox, Tab
from IPython.display import display
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


def A(x, d):
    return d * (1 - x)


def B(x, a, h, g):
    return (a * x * (1 - x) ** g) / (1 + a * h * x)


def C(x, r, s):
    if x == 0:  # Avoid 0 division error
        return 0

    term1 = r * (1 - x)
    term2 = (1 - r) * x
    return 1 / (1 + (term1 / term2) ** s)


def delta(x, d, a, h, g, r, s):
    return A(x, d) - B(x, a, h, g) * C(x, r, s)


def simulate(x0, d, a, h, g, r, s, steps=50):
    x = np.zeros(steps)
    x[0] = x0

    for t in range(steps - 1):
        x[t + 1] = x[t] + delta(x[t], d, a, h, g, r, s)
        x[t + 1] = np.clip(x[t + 1], 0, 1)

    return x


PARAMETERS = {
    "x0": {
        "default": 0.3,
        "description": "Initial value",
        "range": {"min": 0.01, "max": 0.99, "step": 0.01}
    },
    "steps": {
        "default": 100,
        "description": "Number of simulation steps",
        "range": {"min": 10, "max": 300, "step": 10}
    },
    "d": {
        "default": 0.5,
        "description": "Environmental dynamicity",
        "range": {"min": 0.01, "max": 5, "step": 0.1}
    },
    "a": {
        "default": 2,
        "description": "IT department efficacy",
        "range": {"min": 0.1, "max": 10, "step": 0.1}
    },
    "h": {
        "default": 1,
        "description": "IT system rigidity",
        "range": {"min": 0.1, "max": 5, "step": 0.1}
    },
    "g": {
        "default": 1,
        "description": "IT investment propensity",
        "range": {"min": 0.1, "max": 5, "step": 0.1}
    },
    "r": {
        "default": 0.3,
        "description": "Action threshold",
        "range": {"min": 0.01, "max": 0.99, "step": 0.01}
    },
    "s": {
        "default": 3,
        "description": "Organizational flexibility",
        "range": {"min": 1, "max": 10, "step": 0.1}
    }
}

# b is the parameter to plot on the x axis. 
def bifurcation_diagram(b_param, b_min, b_max, params, x0, n_points=700):
    b_values = np.linspace(b_min, b_max, n_points)
    n_last = 100
    n_transient = 100

    plt.figure(figsize=(12, 7))

    for b in b_values:
        params[b_param] = b
        
        x = x0
        
        for _ in range(n_transient):
            x = np.clip(x + delta(x, **params), 0, 1)
        
        x_vals = []
        for _ in range(n_last):
            x = np.clip(x + delta(x, **params), 0, 1)
            x_vals.append(x)
        
        plt.plot([b] * len(x_vals), x_vals, 'k.', markersize=0.5, alpha=0.6)

    plt.xlabel(f"{b_param} ({PARAMETERS[b_param]['description'] if b_param in PARAMETERS else ''})", fontsize=12)
    plt.ylabel("Long-term x value", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.show()
    
def update_bif_diagram(b_param, b_min, b_max, **kwargs):
    x0 = kwargs.pop('x0', PARAMETERS['x0']['default'])
    bifurcation_diagram(b_param, b_min, b_max, kwargs, x0)
    
def compute_lyapunov_exponent(x0=0.3, epsilon=1e-8, steps=50, **kwargs):

    x = simulate(x0=x0, steps=steps, **kwargs)
    x_perturbed = simulate(x0=x0 + epsilon, steps=steps, **kwargs)
    

    separation = np.abs(x_perturbed - x)
    
    valid_indices = separation > 0
    if np.sum(valid_indices) < 2:
        return 0
    
    t = np.arange(steps)[valid_indices]
    log_sep = np.log(separation[valid_indices])
    
    # Perform linear regression
    coeffs = np.polyfit(t, log_sep, 1)
    lyapunov_exponent = coeffs[0]
    
    return lyapunov_exponent

def lyapunov_diagram(b_param, b_min, b_max, params, x0, n_points=700):
    b_values = np.linspace(b_min, b_max, n_points)


    lambda_vals = []
    
    for b in b_values:
        params[b_param] = b
        lambda_vals.append(compute_lyapunov_exponent(x0, **params))
               

    plt.figure(figsize=(12, 6))

    plt.plot(b_values, lambda_vals, 
            color='black',    
            linewidth=1.5,
            linestyle='-',
            alpha=1)

    plt.axhline(0, color='red', linestyle='--', linewidth=1)

    plt.xlabel(f"{b_param} ({PARAMETERS[b_param]['description'] if b_param in PARAMETERS else ''})", fontsize=12)
    plt.ylabel("λ (Lyapunov exponent)", fontsize=12)
    plt.grid(True, color='lightgray', linestyle=':', alpha=0.7)
    plt.gca().spines[['top', 'right']].set_visible(False)
    plt.tight_layout()
    plt.show()
    
def update_lyapunov_diagram(b_param, b_min, b_max, **kwargs):
    x0 = kwargs.pop('x0', PARAMETERS['x0']['default'])
    lyapunov_diagram(b_param, b_min, b_max, kwargs, x0)
    
# print(compute_lyapunov_exponent())
# print(compute_lyapunov_exponent(x0=0.5, d=0.7, a=2.5))
# print(compute_lyapunov_exponent(x0=0.3, d=1, a=1, h=1, g=1, r=0.5, s=1))

def create_interactive():
    slider_style = {"description_width": "80px"}
    slider_layout = Layout(width="50%")
    initial_param = 'd'
    
    available_params = [p for p in PARAMETERS.keys() if p not in ['x0', 'steps']]
    param_dropdown = Dropdown(
        options=available_params,
        value=initial_param,
        description='Parameter:'
    )
    
    b_min_slider = FloatSlider(
        min=PARAMETERS[initial_param]['range']['min'],
        max=PARAMETERS[initial_param]['range']['max'],
        step=PARAMETERS[initial_param]['range']['step'],
        value=PARAMETERS[initial_param]['range']['min'],
        style=slider_style,
        layout=slider_layout,
        description='Min value:'
    )
    
    b_max_slider = FloatSlider(
        min=PARAMETERS[initial_param]['range']['min'],
        max=PARAMETERS[initial_param]['range']['max'],
        step=PARAMETERS[initial_param]['range']['step'],
        value=PARAMETERS[initial_param]['range']['max'],
        style=slider_style,
        layout=slider_layout,
        description='Max value:'
    )
    
    other_sliders = {}
    for param in PARAMETERS:
        if param not in ['steps']:
            other_sliders[param] = FloatSlider(
                min=PARAMETERS[param]['range']['min'],
                max=PARAMETERS[param]['range']['max'],
                step=PARAMETERS[param]['range']['step'],
                value=PARAMETERS[param]['default'],
                style=slider_style,
                layout=slider_layout,
                description=f"{param}",
                disabled=(param == initial_param)  # Initially disable 'd'
            )
    
    current_b_param = {'value': initial_param}
    
    def update_sliders(change):
        new_param = change['new']
        old_param = current_b_param['value']
        current_b_param['value'] = new_param

        b_min_slider.min = PARAMETERS[new_param]['range']['min']
        b_min_slider.max = PARAMETERS[new_param]['range']['max']
        b_min_slider.step = PARAMETERS[new_param]['range']['step']
        b_min_slider.value = PARAMETERS[new_param]['range']['min']
        
        b_max_slider.min = PARAMETERS[new_param]['range']['min']
        b_max_slider.max = PARAMETERS[new_param]['range']['max']
        b_max_slider.step = PARAMETERS[new_param]['range']['step']
        b_max_slider.value = PARAMETERS[new_param]['range']['max']
        
        if old_param in other_sliders:
            other_sliders[old_param].disabled = False
        
        if new_param in other_sliders:
            other_sliders[new_param].disabled = True
    
    param_dropdown.observe(update_sliders, names='value')
    
    def bif_wrapper(b_min, b_max, **kwargs):
        return update_bif_diagram(
            b_param=current_b_param['value'],
            b_min=b_min,
            b_max=b_max,
            **kwargs
        )
    
    def lyap_wrapper(b_min, b_max, **kwargs):
        return update_lyapunov_diagram(
            b_param=current_b_param['value'],
            b_min=b_min,
            b_max=b_max,
            **kwargs
        )
    
    bif_diagram = interactive(
        bif_wrapper,
        b_min=b_min_slider,
        b_max=b_max_slider,
        **other_sliders
    )
    
    lyapunov_diagram = interactive(
        lyap_wrapper,
        b_min=b_min_slider,
        b_max=b_max_slider,
        **other_sliders
    )
    
    tabs = Tab(children=[bif_diagram, lyapunov_diagram])
    tabs.set_title(0, 'Bifurcation Diagram')
    tabs.set_title(1, 'Lyapunov Exponent')
    
    return VBox([param_dropdown, Box(layout=Layout(height='5px')), tabs])

create_interactive()