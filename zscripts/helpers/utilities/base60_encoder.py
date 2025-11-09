import math
from typing import Any, Dict, List, Tuple

import pygame


# Function to convert degrees to base 60
def degrees_to_base60(degrees: float) -> Tuple[int, int, float]:
    whole_deg = int(degrees)
    minutes = (degrees - whole_deg) * 60
    whole_min = int(minutes)
    seconds = (minutes - whole_min) * 60
    return whole_deg, whole_min, seconds


# Function to convert base 60 to degrees
def base60_to_degrees(degrees: int, minutes: int, seconds: float) -> float:
    return degrees + minutes / 60 + seconds / 3600


# Function to calculate distance between two points in 2D
def distance_2d(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


# Initialize Pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Base 60 Interactive Shapes")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)

# Fonts
font = pygame.font.Font(None, 36)
small_font = pygame.font.Font(None, 24)

# Shape data
shapes = []
show_calculations = False


# Function to draw shapes and calculations
def draw_shapes(screen: Any, shapes: List[Dict[str, Any]], show_calculations: bool) -> None:
    for shape in shapes:
        if shape["type"] == "triangle":
            pygame.draw.polygon(screen, RED, shape["points"], 3)
            if show_calculations:
                a = distance_2d(shape["points"][0], shape["points"][1])
                b = distance_2d(shape["points"][1], shape["points"][2])
                c = distance_2d(shape["points"][2], shape["points"][0])
                points = shape["points"]
                text = small_font.render(f"a: {a:.2f}, b: {b:.2f}, c: {c:.2f}", True, BLACK)
                screen.blit(text, (points[0][0], points[0][1] - 20))
        elif shape["type"] == "square":
            pygame.draw.rect(screen, GREEN, shape["rect"], 3)
            if show_calculations:
                w = shape["rect"].width
                h = shape["rect"].height
                points = [
                    shape["rect"].topleft,
                    shape["rect"].topright,
                    shape["rect"].bottomright,
                    shape["rect"].bottomleft,
                ]
                text = small_font.render(f"w: {w}, h: {h}", True, BLACK)
                screen.blit(text, (shape["rect"].topleft[0], shape["rect"].topleft[1] - 20))
        elif shape["type"] == "circle":
            pygame.draw.circle(screen, BLUE, shape["center"], shape["radius"], 3)
            if show_calculations:
                r = shape["radius"]
                text = small_font.render(f"r: {r}", True, BLACK)
                screen.blit(text, (shape["center"][0], shape["center"][1] - 20))
        elif shape["type"] == "line":
            end_x = shape["start"][0] + shape["length"] * math.cos(math.radians(shape["angle"]))
            end_y = shape["start"][1] + shape["length"] * math.sin(math.radians(shape["angle"]))
            pygame.draw.line(screen, BLACK, shape["start"], (end_x, end_y), 3)
            if show_calculations:
                angle_base60 = degrees_to_base60(shape["angle"])
                angle_text = f"{angle_base60[0]}° {angle_base60[1]}' {angle_base60[2]:.2f}''"
                text = small_font.render(angle_text, True, BLACK)
                screen.blit(text, (shape["start"][0], shape["start"][1] - 20))


# Main loop
running = True
drawing = False
shape_type = "triangle"
start_pos = None

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_1:
                shape_type = "triangle"
            elif event.key == pygame.K_2:
                shape_type = "square"
            elif event.key == pygame.K_3:
                shape_type = "circle"
            elif event.key == pygame.K_4:
                shape_type = "line"
            elif event.key == pygame.K_c:
                show_calculations = not show_calculations
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if not drawing:
                start_pos = event.pos
                drawing = True
            else:
                end_pos = event.pos
                if shape_type == "triangle":
                    shapes.append(
                        {
                            "type": "triangle",
                            "points": [start_pos, end_pos, (start_pos[0], end_pos[1])],
                        }
                    )
                elif shape_type == "square":
                    x1, y1 = start_pos
                    x2, y2 = end_pos
                    top_left = (min(x1, x2), min(y1, y2))
                    width = abs(x2 - x1)
                    height = abs(y2 - y1)
                    rect = pygame.Rect(top_left, (width, height))
                    shapes.append({"type": "square", "rect": rect})
                elif shape_type == "circle":
                    radius = int(math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1]))
                    shapes.append({"type": "circle", "center": start_pos, "radius": radius})
                elif shape_type == "line":
                    length = int(math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1]))
                    angle = math.degrees(
                        math.atan2(end_pos[1] - start_pos[1], end_pos[0] - start_pos[0])
                    )
                    shapes.append(
                        {"type": "line", "start": start_pos, "length": length, "angle": angle}
                    )
                drawing = False

    screen.fill(WHITE)
    draw_shapes(screen, shapes, show_calculations)

    # Display instructions
    instructions = [
        "Press 1 for Triangle",
        "Press 2 for Square",
        "Press 3 for Circle",
        "Press 4 for Line",
        "Press C to Toggle Calculations",
    ]
    for i, instruction in enumerate(instructions):
        text = small_font.render(instruction, True, BLACK)
        screen.blit(text, (10, 10 + i * 20))

    pygame.display.flip()

pygame.quit()
