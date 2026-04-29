# visuals.py
import plotly.graph_objects as go
import numpy as np
import math

def draw_longitudinal_section(pile, layers, reinf):
    """Generates a professional elevation-based longitudinal section."""
    fig = go.Figure()
    
    # Values
    gl = pile.ground_level
    col = pile.cut_off_level
    toe = pile.toe_level
    gwt = pile.gwt_level
    dia_m = pile.diameter / 1000.0
    
    # Set plot range
    y_min = toe - 2
    y_max = max(gl, col) + 2
    
    # 1. Draw Soil Layers (Background)
    colors = ["#f2e8cf", "#e76f51", "#a8dadc", "#457b9d"]
    for i, layer in enumerate(layers):
        z_top = gl - layer.depth_top
        z_bot = gl - layer.depth_bottom
        color = colors[i % len(colors)]
        
        fig.add_shape(type="rect", x0=-3, y0=z_bot, x1=3, y1=z_top,
                      fillcolor=color, opacity=0.2, line=dict(width=0))
        fig.add_annotation(x=-2.9, y=(z_top + z_bot)/2, 
                           text=f"<b>{layer.name}</b><br>{layer.soil_type.value}", 
                           showarrow=False, xanchor="left", font=dict(size=10))

    # 2. Draw Pile Concrete Body
    fig.add_shape(type="rect", x0=-dia_m/2, y0=toe, x1=dia_m/2, y1=col,
                  fillcolor="rgba(180, 180, 180, 0.6)", line=dict(color="black", width=2))
    
    # 3. Draw Longitudinal Reinforcement (The Cage)
    cage_cover_m = pile.cover / 1000.0
    cage_x = (dia_m / 2.0) - cage_cover_m
    fig.add_shape(type="line", x0=-cage_x, y0=toe + 0.2, x1=-cage_x, y1=col, line=dict(color="red", width=3))
    fig.add_shape(type="line", x0=cage_x, y0=toe + 0.2, x1=cage_x, y1=col, line=dict(color="red", width=3))
    
    # 3b. Draw Spiral/Links
    spacing_m = reinf.stirrup_spacing / 1000.0
    current_z = col
    while current_z > toe:
        fig.add_shape(type="line", x0=-cage_x, y0=current_z, x1=cage_x, y1=current_z,
                      line=dict(color="darkred", width=1))
        current_z -= spacing_m * 5 
        if current_z < toe + 1: break

    # Labels
    fig.add_annotation(x=cage_x, y=col - 2, text=f"Main: {reinf.num_bars}T{reinf.bar_diameter}",
                       showarrow=True, arrowhead=2, ax=60, ay=-30, font=dict(color="red"))
    fig.add_annotation(x=-cage_x, y=col - 4, text=f"Links: T{reinf.stirrup_diameter}@{reinf.stirrup_spacing}",
                       showarrow=True, arrowhead=2, ax=-60, ay=30, font=dict(color="darkred"))

    # 4. Key Level Lines
    fig.add_shape(type="line", x0=-3.5, y0=gl, x1=3.5, y1=gl, line=dict(color="brown", width=3))
    fig.add_annotation(x=3.5, y=gl, text=f"G.L. {gl:+.2f}", xanchor="left", showarrow=False, font=dict(color="brown"))
    fig.add_annotation(x=1.1, y=col, text=f"C.O.L. {col:+.2f}", xanchor="left", showarrow=False)
    fig.add_annotation(x=1.1, y=toe, text=f"TOE {toe:+.2f}", xanchor="left", showarrow=False)
    fig.add_shape(type="line", x0=-3.5, y0=gwt, x1=3.5, y1=gwt, line=dict(color="blue", width=2, dash="dash"))
    fig.add_annotation(x=-3.5, y=gwt, text=f"GWT {gwt:+.2f} ▽", xanchor="right", showarrow=False, font=dict(color="blue"))

    fig.update_layout(
        title="Technical Longitudinal Section (Elevations in m)",
        yaxis=dict(title="Elevation (m)", range=[y_min, y_max], gridcolor='lightgray', tickfont=dict(size=11)),
        xaxis=dict(visible=False, range=[-5, 5]),
        height=800, # Matches app.py iframe height for print
        template="plotly_white",
        margin=dict(l=20, r=20, t=50, b=20)
    )
    return fig

def draw_cross_section(pile, reinf):
    """Generates a professional cross-section schematic."""
    fig = go.Figure()
    R = (pile.diameter / 2.0)
    cover = pile.cover
    r_cage = R - cover
    
    # 1. Pile Outer Boundary
    theta = np.linspace(0, 2*np.pi, 100)
    fig.add_trace(go.Scatter(x=R*np.cos(theta), y=R*np.sin(theta), mode='lines', 
                             line=dict(color='black', width=3), name="Pile Edge"))
    
    # 2. Stirrup / Link
    fig.add_trace(go.Scatter(x=r_cage*np.cos(theta), y=r_cage*np.sin(theta), mode='lines', 
                             line=dict(color='gray', width=2), name="Link/Stirrup"))
    
    # 3. Longitudinal Bars (Drawn as coordinate-based circles for correct scaling)
    bar_angles = np.linspace(0, 2*np.pi, reinf.num_bars, endpoint=False)
    bar_radius_m = (reinf.bar_diameter / 2.0) # mm
    
    for angle in bar_angles:
        bx = r_cage * np.cos(angle)
        by = r_cage * np.sin(angle)
        fig.add_shape(type="circle",
                      xref="x", yref="y",
                      x0=bx - bar_radius_m, y0=by - bar_radius_m,
                      x1=bx + bar_radius_m, y1=by + bar_radius_m,
                      fillcolor="black", line_color="black")

    fig.add_annotation(x=0, y=0, text=f"D={pile.diameter}mm", showarrow=False)
    fig.add_annotation(x=R*1.1, y=0, text=f"Cover={pile.cover}mm", showarrow=False, xanchor="left")

    fig.update_layout(title="Technical Cross Section", 
                      xaxis=dict(visible=False, scaleanchor="y", scaleratio=1),
                      yaxis=dict(visible=False), height=350, showlegend=True, 
                      template="plotly_white", margin=dict(l=20, r=20, t=40, b=20))
    return fig

def draw_3d_pile_model(pile, layers):
    """Generates an interactive 3D model of the pile and soil strata."""
    fig = go.Figure()
    
    dia_m = pile.diameter / 1000.0
    r = dia_m / 2.0
    
    # 1. Draw Pile Cylinder
    z_pile = np.linspace(pile.toe_level, pile.cut_off_level, 20)
    theta = np.linspace(0, 2*np.pi, 20)
    theta_grid, z_grid = np.meshgrid(theta, z_pile)
    x_grid = r * np.cos(theta_grid)
    y_grid = r * np.sin(theta_grid)
    
    fig.add_trace(go.Surface(x=x_grid, y=y_grid, z=z_grid, 
                             colorscale=[[0, 'gray'], [1, 'lightgray']], 
                             showscale=False, opacity=0.9, name="Pile Body"))
    
    # 2. Draw Soil Layers as semi-transparent boxes
    colors = ["#f2e8cf", "#e76f51", "#a8dadc", "#457b9d", "#bc4749"]
    box_size = 2.0 # 2m x 2m box
    
    for i, layer in enumerate(layers):
        z_top = pile.ground_level - layer.depth_top
        z_bot = pile.ground_level - layer.depth_bottom
        color = colors[i % len(colors)]
        
        # Mesh3d for a box
        fig.add_trace(go.Mesh3d(
            x=[-box_size, -box_size, box_size, box_size, -box_size, -box_size, box_size, box_size],
            y=[-box_size, box_size, box_size, -box_size, -box_size, box_size, box_size, -box_size],
            z=[z_bot, z_bot, z_bot, z_bot, z_top, z_top, z_top, z_top],
            color=color, opacity=0.15, name=layer.name, showlegend=True,
            i=[7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2],
            j=[3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3],
            k=[0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        ))

    # 3. Water Table Plane
    plane_size = 3.0
    fig.add_trace(go.Surface(
        x=[[-plane_size, plane_size], [-plane_size, plane_size]],
        y=[[-plane_size, -plane_size], [plane_size, plane_size]],
        z=[[pile.gwt_level, pile.gwt_level], [pile.gwt_level, pile.gwt_level]],
        colorscale=[[0, 'blue'], [1, 'blue']], opacity=0.3, showscale=False, name="GWT"
    ))

    fig.update_layout(
        title="Interactive 3D Pile-Soil Model",
        scene=dict(
            xaxis_title="X (m)", yaxis_title="Y (m)", zaxis_title="Elevation (m)",
            zaxis=dict(range=[pile.toe_level - 5, pile.ground_level + 2]),
            aspectmode='manual',
            aspectratio=dict(x=1, y=1, z=2)
        ),
        margin=dict(l=0, r=0, b=0, t=40),
        height=700
    )
    return fig

