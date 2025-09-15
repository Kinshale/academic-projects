# Simulation and Analysis of Business-IT Alignment Dynamics
A (Jupyter Notebook)[pii.ipynb] for analyzing and simulating the behavior of a discrete time equation modeling Business-IT alignment. The model captures how alignment evolves in organizations under various conditions such as *IT rigidity* or *action threshold*. 

### Model Overview
The model is based on the following equation:

$$ x_{t + 1} = x_t + A(x_t) - B(x_t)C(x_t) $$

Where:
- $A(x_t) = d(1 - x_t)$  
- $B(x_t) = \frac{a x_t (1 - x_t)^g}{1 + a h x_t}$  
- $C(x_t) = \frac{1}{1 + z^s}$  with $z = \frac{r (1 - x_t)}{x_t (1 - r)}$


| Parameter | Range      | Default | Description               |
|-----------|------------|---------|---------------------------|
| `x0`      | [0.01,0.99]| 0.3     | Initial misalignment      |
| `d`       | [0.01,5]   | 0.5     | Environmental dynamicity  |
| `a`       | [0.1,10]   | 2       | IT efficacy               |
| `h`       | [0.1,5]    | 1       | IT rigidity               |
| `g`       | [0.1,5]    | 1       | IT investment propensity  |
| `r`       | [0.01,0.99]| 0.3     | Action threshold          |
| `s`       | [1,10]     | 3       | Organizational flexibility|

### Features
1. **Interactive Explorer**: Adjust parameters with sliders to see how the alignment evolves.
2. **Phase Portraits**: Visualize stability and equilibria.
3. **Bifurcation Analysis**: Detect chaotic regimes. 

<!-- Add some cool images -->

### Intuitive explanations
The notebook provides explanations for the various components and parameters of the equation, giving insights to the model. 
The discussion then focuses on a few noteworthy cases, with a curated analysis and commentary.

<!-- Add some cool images -->

## Getting Started
1. Clone the repository. 
2. Install dependencies (You can see the conda environment at ...) . 
    ```bash
    pip install numpy matplotlib ipywidgets
    jupyter notebook pii.ipynb
    ```
3. Open the Jupyter Notebook (pii.ipynb) and run the cells.

## Author 
Alessandro Aquilini.  
Developed for the course "Progetto Ingegneria Informatica" at Politecnico di Milano.
