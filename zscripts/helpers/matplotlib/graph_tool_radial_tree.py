import pandas as pd
from graph_tool.all import Graph, graph_draw, radial_tree_layout  # noqa: F401
from helpers.utilities.paths import org_path

# Read data from Excel sheet via org_path
df = pd.read_excel(
    str(org_path("Revenue Streams", "Blogs", "format_ai", "livs_test", "proffessions .xlsx"))
)

# Create a dictionary to store vertices
vertices = {}

# Create a graph
g = Graph(directed=True)

# Create vertex properties for names
name = g.new_vertex_property("string")

# Iterate over rows in the dataframe
for _, row in df.iterrows():
    # Extract values from columns
    section = row["discipline"]
    parent = row["field"]
    child = row["branch"]

    # Create vertices for parent and child if not already present
    if parent not in vertices:
        parent_vertex = g.add_vertex()
        vertices[parent] = parent_vertex
        name[parent_vertex] = parent

    if child not in vertices:
        child_vertex = g.add_vertex()
        vertices[child] = child_vertex
        name[child_vertex] = child

    # Add edge from parent to child
    g.add_edge(vertices[parent], vertices[child])

# Layout the graph
pos = radial_tree_layout(g, vertices[g.vertex(0)])

# Create a graph visualization
graph_draw(
    g,
    pos=pos,
    vertex_text=name,
    vertex_font_size=10,
    vertex_fill_color="white",
    vertex_shape="circle",
    vertex_text_position=1,
    vertex_anchor=0.5,
    edge_color="black",
    edge_pen_width=1,
    output_size=(800, 600),
    output="organization_chart.png",
)
