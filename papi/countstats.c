
#include <limits.h>
#define MAX_AIR_ROUTES 5
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define CLAMP(val, min, max)                                                   \
	((val) < (min) ? (min) : ((val) > (max) ? (max) : (val)))
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#ifdef DEBUG
#define DEBUG_PRINT(fmt, ...) printf("DEB: " fmt, ##__VA_ARGS__)
#else
#define DEBUG_PRINT(fmt, ...)                                                  \
	do {                                                                       \
	} while (0)
#endif

typedef struct {
	uint8_t cost;			// (0, 100)
	uint8_t air_out_degree; // (0, 5)
	uint8_t air_in_degree;	// (0, N)
} Cell;

typedef struct {
	int from_x, from_y;
	int to_x, to_y;
} AirRoute;

typedef struct {
	int x, y;
	int radius;
} changePoint;

// ==== Hardcoded neighbor offsets ====
typedef struct {
	int8_t dx[6];
	int8_t dy[6];
} NeighborOffsets;

static const NeighborOffsets even_offsets = {
	.dx = {-1, -1, -1, 0, 1, 0}, // dx_even for directions 0-5
	.dy = {1, 0, -1, -1, 0, 1}	 // dy for directions 0-5
};

static const NeighborOffsets odd_offsets = {
	.dx = {0, -1, 0, 1, 1, 1}, // dx_odd for directions 0-5
	.dy = {1, 0, -1, -1, 0, 1} // dy for directions 0-5
};

// NOTE: For performance we can use a flat array
int W, H;

Cell **hive;

AirRoute *air_routes = NULL;
int air_route_count = 0;
int air_route_capacity = 0;

void print_stats() {
	if (hive == NULL) {
		printf("Hive not initialized yet.\n");
		return;
	}

	// Print dimensions
	printf("Hive dimensions: %d x %d\n", W, H);

	// Count 0s and 1s in hive costs
	int count_zeros = 0;
	int count_ones = 0;

	for (int i = 0; i < W; i++) {
		for (int j = 0; j < H; j++) {
			if (hive[i][j].cost == 0) {
				count_zeros++;
			} else if (hive[i][j].cost == 1) {
				count_ones++;
			}
		}
	}

	printf("Number of 0s in hive costs: %d\n", count_zeros);
	printf("Number of 1s in hive costs: %d\n", count_ones);

	// Print air routes
	printf("Number of air routes: %d\n", air_route_count);
	for (int i = 0; i < air_route_count; i++) {
		printf("Air route %d: (%d, %d) -> (%d, %d)\n", i, air_routes[i].from_x,
			   air_routes[i].from_y, air_routes[i].to_x, air_routes[i].to_y);
	}
}

int in_bounds(int x, int y) { return x >= 0 && x < W && y >= 0 && y < H; }

void parse_init(int w, int h) {
	// Free resources
	if (hive != NULL) {
		for (int i = 0; i < W; i++)
			free(hive[i]);
		free(hive);
		hive = NULL;
		DEBUG_PRINT("Freed memory for Hive\n");
	}

	if (air_routes != NULL)
		free(air_routes);

	air_routes = NULL;
	air_route_count = 0;
	air_route_capacity = 0;

	DEBUG_PRINT("Init map: %d (Rows) x %d (Columns)\n", h, w);

	W = w;
	H = h;

	hive = malloc(W * sizeof(Cell *));
	for (int i = 0; i < W; i++) {
		hive[i] = malloc(H * sizeof(Cell));
		for (int j = 0; j < H; j++) {
			hive[i][j].cost = 1;
			hive[i][j].air_out_degree = 0;
			hive[i][j].air_in_degree = 0;
		}
	}

	DEBUG_PRINT("Allocated and initialized Hive\n");
}

void parse_change_cost(int x0, int y0, int v, int R) {
	DEBUG_PRINT(
		"Changing costs of cells centered around (%d, %d) with rad %d.\n", x0,
		y0, R);

	if (R == 0) {
		DEBUG_PRINT("Radius is 0.\n");
		return;
	}

	if (!in_bounds(x0, y0)) {
		DEBUG_PRINT("Out of Bounds.\n");
		return;
	}

	if (v > 10 || v < -10 || R < 0) {
		DEBUG_PRINT("Wrong input data.\n");
		return;
	}

	int x = x0;
	int y = y0;

	for (int r = 0; r < R; r++) {
		// Handle the central cell
		if (r == 0) {
			hive[x][y].cost = CLAMP(hive[x][y].cost + v, 0, 100);
			continue;
		}

		// Delta_cost is a function of r
		int delta_cost = (int)floor(v * (R - r) / (double)R);

		x++; // Move outward to the hexagon of radius r

		for (int d = 0; d < 6; d++) {
			for (int i = 0; i < r; i++) {
				if (in_bounds(x, y))
					hive[x][y].cost =
						CLAMP(hive[x][y].cost + delta_cost, 0, 100);

				const NeighborOffsets *current_offsets =
					(y % 2 == 0) ? &even_offsets : &odd_offsets;
				x += current_offsets->dx[d];
				y += current_offsets->dy[d];
			}
		}
	}

}

void parse_toggle_air_route(int x1, int y1, int x2, int y2) {

	DEBUG_PRINT("Toggle air route from (%d, %d) to (%d, %d)\n", x1, y1, x2, y2);

	if (!in_bounds(x1, y1) || !in_bounds(x2, y2)) {
		DEBUG_PRINT("Out of Bounds\n");
		return;
	}

	Cell *cell = &hive[x1][y1];

	// Check if route already exists
	if (cell->air_out_degree != 0) {
		for (int i = 0; i < air_route_count; i++) {
			if (air_routes[i].from_x == x1 && air_routes[i].from_y == y1 &&
				air_routes[i].to_x == x2 && air_routes[i].to_y == y2) {
				// Remove the route by swapping with last element
				air_routes[i] = air_routes[air_route_count - 1];
				air_route_count--;
			}
		}

		cell->air_out_degree--;
		hive[x2][y2].air_in_degree--;
		DEBUG_PRINT("Removed air route\n");
		return;
	}

	if (cell->air_out_degree == MAX_AIR_ROUTES) {
		DEBUG_PRINT("Too many exiting air routes\n");
		printf("KO\n");
		return;
	} else if (cell->air_out_degree >= MAX_AIR_ROUTES) {
		DEBUG_PRINT("More than 5 exiting air routes\n");
		exit(1);
	}

	// Add new route
	if (air_route_count == air_route_capacity) {
		air_route_capacity =
			air_route_capacity ? air_route_capacity * 2
							   : 16; // Double the space if we ran out of space
		air_routes = realloc(air_routes, air_route_capacity * sizeof(AirRoute));
	}

	air_routes[air_route_count++] = (AirRoute){x1, y1, x2, y2};
	cell->air_out_degree++;
	hive[x2][y2].air_in_degree++;

	DEBUG_PRINT("Added new air route\n");
}

void parse_input() {
	char cmd[32];
#ifdef DEBUG
	int line = 1;
#endif

	while (scanf("%31s", cmd) == 1) { // Check return value for cmd input
#ifdef DEBUG
		DEBUG_PRINT("==== Line %d ==== \n", line++);
#endif

		if (strcmp(cmd, "init") == 0) {
			int w, h;
			if (scanf("%d %d", &w, &h) != 2) {
				fprintf(stderr, "Error reading init parameters\n");
				exit(EXIT_FAILURE);
			}
			print_stats();
			parse_init(w, h);
		} else if (strcmp(cmd, "change_cost") == 0) {
			int x, y, v, r;
			if (scanf("%d %d %d %d", &x, &y, &v, &r) != 4) {
				fprintf(stderr, "Error reading change_cost parameters\n");
				exit(EXIT_FAILURE);
			}
			parse_change_cost(x, y, v, r);
		} else if (strcmp(cmd, "travel_cost") == 0) {
			int x1, y1, x2, y2;
			if (scanf("%d %d %d %d", &x1, &y1, &x2, &y2) != 4) {
				fprintf(stderr, "Error reading travel_cost parameters\n");
				exit(EXIT_FAILURE);
			}
		} else if (strcmp(cmd, "toggle_air_route") == 0) {
			int x1, y1, x2, y2;
			if (scanf("%d %d %d %d", &x1, &y1, &x2, &y2) != 4) {
				fprintf(stderr, "Error reading toggle_air_route parameters\n");
				exit(EXIT_FAILURE);
			}
			parse_toggle_air_route(x1, y1, x2, y2);
		} else {
			fprintf(stderr, "Unknown command: %s\n", cmd);
			exit(EXIT_FAILURE);
		}
	}
}

int main() {
	parse_input();
	// printHive(0, 10, 0, 5);
	return 0;
}
