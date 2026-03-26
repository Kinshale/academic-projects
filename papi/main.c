// TODO: Regione intransitabile per empty.txt

#define MAX_AIR_ROUTES 5
#define MAX(a, b) ((a) > (b) ? (a) : (b))
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define CLAMP(val, min, max)                                                   \
	((val) < (min) ? (min) : ((val) > (max) ? (max) : (val)))
#include <assert.h>
#include <limits.h>
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

// ==== Hexagon map implementation ====
typedef struct {
	uint8_t cost;			// (0, 100)
	uint8_t air_out_degree; // (0, 5)
	uint8_t air_in_degree;	// (0, N)
} Cell;

// ==== Storing special points ====
typedef struct {
	int from_x, from_y;
	int to_x, to_y;
} AirRoute;

typedef struct {
	int x, y;
	int radius;
} changePoint;

// ==== Unreachability labeling implementation ====
typedef struct {
	uint32_t forward_label;	 // Reachable from some starting points
	uint32_t backward_label; // Can reach some ending points
	uint8_t visited;		 // For floodfill traversal
} RegionInfo;

// ==== Hardcoded neighbor offsets (Starting from Up Left)====
typedef struct {
	int8_t dx[6];
	int8_t dy[6];
} NeighborOffsets;

static const NeighborOffsets even_offsets = {.dx = {-1, -1, -1, 0, 1, 0},
											 .dy = {1, 0, -1, -1, 0, 1}};

static const NeighborOffsets odd_offsets = {.dx = {0, -1, 0, 1, 1, 1},
											.dy = {1, 0, -1, -1, 0, 1}};

// ===== Graph with the airports (when all cells cost 1) ======
typedef struct {
	int x, y;
} Point;

typedef struct {
	int node_index;
	int cost;
} Edge;

typedef struct {
	Edge *edges;
	int count;
	int capacity;
} AdjList;

// ==== Priority queue implementation ====
typedef struct {
	int x, y;
	int cost;
} Node;

typedef struct {
	Node *data;
	int size;
	int capacity;
} MinHeap;

// NOTE: Priorty queue methods
MinHeap *create_min_heap(int capacity) {
	MinHeap *heap = malloc(sizeof(MinHeap));
	heap->data = malloc(sizeof(Node) * capacity);
	heap->size = 0;
	heap->capacity = capacity;
	return heap;
}

void swap(Node *a, Node *b) {
	Node temp = *a;
	*a = *b;
	*b = temp;
}

void heapify_up(MinHeap *heap, int idx) {
	while (idx > 0) {
		int parent = (idx - 1) / 2;
		if (heap->data[parent].cost > heap->data[idx].cost) {
			swap(&heap->data[parent], &heap->data[idx]);
			idx = parent;
		} else
			break;
	}
}

void heapify_down(MinHeap *heap, int idx) {
	while (1) {
		int left = 2 * idx + 1, right = 2 * idx + 2, smallest = idx;
		if (left < heap->size &&
			heap->data[left].cost < heap->data[smallest].cost)
			smallest = left;
		if (right < heap->size &&
			heap->data[right].cost < heap->data[smallest].cost)
			smallest = right;
		if (smallest != idx) {
			swap(&heap->data[smallest], &heap->data[idx]);
			idx = smallest;
		} else
			break;
	}
}

void push(MinHeap *heap, int x, int y, int cost) {
	if (heap->size == heap->capacity)
		return;
	heap->data[heap->size++] = (Node){x, y, cost};
	heapify_up(heap, heap->size - 1);
}

Node pop(MinHeap *heap) {
	Node top = heap->data[0];
	heap->data[0] = heap->data[--heap->size];
	heapify_down(heap, 0);
	return top;
}

int is_empty(MinHeap *heap) { return heap->size == 0; }

// NOTE: Global variables

int W, H;
Cell **hive;

AirRoute *air_routes = NULL;
int air_route_count = 0;
int air_route_capacity = 0;

changePoint *change_points = NULL;
int change_point_count = 0;
int change_point_capacity = 0;

RegionInfo **region_info = NULL;
uint32_t current_forward_label = 1;
uint32_t current_backward_label = 1;

// NOTE: Utility functions
int in_bounds(int x, int y) { return x >= 0 && x < W && y >= 0 && y < H; }

int hex_distance(int x1, int y1, int x2, int y2) {
	int dx = abs(x2 - x1), dy = abs(y2 - y1);
	int oc = (MIN(y1, y2) + ((x1 > x2) ^ (y1 > y2))) &
			 1; // Offset correcction: are we moving in the same direction in
				// the x and the y?
	return dx + dy - MIN((dy + oc) / 2, dx);
}

// Add this function near the other utility functions
int closest_special_point(int x0, int y0) {
	int closest = INT_MAX;

	// Check air routes (takeoff airports)
	for (int i = 0; i < air_route_count; i++) {
		int dist =
			hex_distance(air_routes[i].from_x, air_routes[i].from_y, x0, y0);
		if (dist < closest) {
			closest = dist;
		}
	}

	// Check change points (subtract radius since we care about the boundary)
	for (int i = 0; i < change_point_count; i++) {
		int dist = hex_distance(change_points[i].x, change_points[i].y, x0, y0);
		int boundary_dist = MAX(0, dist - change_points[i].radius);
		if (boundary_dist < closest) {
			closest = boundary_dist;
		}
	}

	return closest;
}

// ================= vvvv Dijikstra Algorithms vvvv ==================
int bidirectional_dijkstra(int x1, int y1, int x2, int y2) {
	if (x1 == x2 && y1 == y2)
		return 0;

	if (hive[x1][y1].cost == 0)
		return 0;

	int start_circle = closest_special_point(x1, y1);
	if (start_circle > hex_distance(x1, y1, x2, y2)) {
		return hex_distance(x1, y1, x2, y2);
	}

	// TODO: Initialize the search with R = hex_distance.

	int **dist_f = malloc(W * sizeof(int *));
	int **dist_b = malloc(W * sizeof(int *));
	char **visited_f = malloc(W * sizeof(char *));
	char **visited_b = malloc(W * sizeof(char *));

	for (int x = 0; x < W; x++) {
		dist_f[x] = malloc(H * sizeof(int));
		dist_b[x] = malloc(H * sizeof(int));
		visited_f[x] = malloc(H * sizeof(char));
		visited_b[x] = malloc(H * sizeof(char));
		for (int y = 0; y < H; y++) {
			dist_f[x][y] = INT_MAX;
			dist_b[x][y] = INT_MAX;
			visited_f[x][y] = 0;
			visited_b[x][y] = 0;
		}
	}

	MinHeap *heap_f = create_min_heap(W * H + 1000);
	MinHeap *heap_b = create_min_heap(W * H + 1000);

	// Initialize both searches
	dist_f[x1][y1] = 0;
	dist_b[x2][y2] = 0;
	push(heap_f, x1, y1, 0);
	push(heap_b, x2, y2, 0);

	int best_path = INT_MAX;

	while (!is_empty(heap_f) || !is_empty(heap_b)) {
		// Process forward search
		if (!is_empty(heap_f)) {
			Node node_f = pop(heap_f);
			int x = node_f.x;
			int y = node_f.y;

			if (!visited_f[x][y]) {
				visited_f[x][y] = 1;

				// Check if this node was visited by backward search
				if (visited_b[x][y]) {
					best_path = MIN(best_path, dist_f[x][y] + dist_b[x][y]);
				}

				Cell cell = hive[x][y];
				int cost = cell.cost;

				if (cost == 0)
					continue;

				// Explore hexagonal neighbors (forward direction - cost of
				// current cell)
				const NeighborOffsets *offsets =
					(y % 2 == 0) ? &even_offsets : &odd_offsets;
				for (int d = 0; d < 6; d++) {
					int nx = x + offsets->dx[d];
					int ny = y + offsets->dy[d];

					if (!in_bounds(nx, ny))
						continue;
					if (visited_f[nx][ny])
						continue;

					int new_cost = dist_f[x][y] + cost;
					if (new_cost < dist_f[nx][ny]) {
						dist_f[nx][ny] = new_cost;
						push(heap_f, nx, ny, new_cost);
					}
				}

				// Explore air routes (forward direction - cost of current cell)
				if (cell.air_out_degree > 0) {
					for (int i = 0; i < air_route_count; i++) {
						if (air_routes[i].from_x == x &&
							air_routes[i].from_y == y) {
							int nx = air_routes[i].to_x;
							int ny = air_routes[i].to_y;

							if (!in_bounds(nx, ny))
								continue;
							if (visited_f[nx][ny])
								continue;

							int new_cost = dist_f[x][y] + cost;
							if (new_cost < dist_f[nx][ny]) {
								dist_f[nx][ny] = new_cost;
								push(heap_f, nx, ny, new_cost);
							}
						}
					}
				}
			}
		}

		// Process backward search
		if (!is_empty(heap_b)) {
			Node node_b = pop(heap_b);
			int x = node_b.x;
			int y = node_b.y;

			if (!visited_b[x][y]) {
				visited_b[x][y] = 1;

				// Check if this node was visited by forward search
				if (visited_f[x][y]) {
					best_path = MIN(best_path, dist_f[x][y] + dist_b[x][y]);
				}

				// Explore hexagonal neighbors (backward direction - cost of
				// neighbor cell)
				const NeighborOffsets *offsets =
					(y % 2 == 0) ? &even_offsets : &odd_offsets;
				for (int d = 0; d < 6; d++) {
					int nx = x + offsets->dx[d];
					int ny = y + offsets->dy[d];

					if (!in_bounds(nx, ny))
						continue;
					if (visited_b[nx][ny])
						continue;

					Cell dest_cell = hive[nx][ny];
					int cost = dest_cell.cost;

					if (cost == 0)
						continue;

					int new_cost = dist_b[x][y] + cost;
					if (new_cost < dist_b[nx][ny]) {
						dist_b[nx][ny] = new_cost;
						push(heap_b, nx, ny, new_cost);
					}
				}

				// Explore air routes (backward direction - cost of destination
				// cell)
				if (hive[x][y].air_in_degree > 0) {
					for (int i = 0; i < air_route_count; i++) {
						if (air_routes[i].to_x == x &&
							air_routes[i].to_y == y) {
							int nx = air_routes[i].from_x;
							int ny = air_routes[i].from_y;

							if (!in_bounds(nx, ny))
								continue;
							if (visited_b[nx][ny])
								continue;

							Cell dest_cell = hive[nx][ny];
							int cost = dest_cell.cost;

							if (cost == 0)
								continue;

							int new_cost = dist_b[x][y] + cost;
							if (new_cost < dist_b[nx][ny]) {
								dist_b[nx][ny] = new_cost;
								push(heap_b, nx, ny, new_cost);
							}
						}
					}
				}
			}
		}

		// NOTE: Early termination if best path found is less than current heap
		// minimums
		if (best_path != INT_MAX) {
			int min_f = is_empty(heap_f) ? INT_MAX : heap_f->data[0].cost;
			int min_b = is_empty(heap_b) ? INT_MAX : heap_b->data[0].cost;

			if (best_path < min_f + min_b) {
				break;
			}
		}
	}

	// Cleanup
	for (int x = 0; x < W; x++) {
		free(dist_f[x]);
		free(dist_b[x]);
		free(visited_f[x]);
		free(visited_b[x]);
	}
	free(dist_f);
	free(dist_b);
	free(visited_f);
	free(visited_b);
	free(heap_f->data);
	free(heap_f);
	free(heap_b->data);
	free(heap_b);

	return best_path == INT_MAX ? -1 : best_path;
}

int only_ones_dijkstra(int x1, int y1, int x2, int y2) {
	// Collect interesting points: start, end, and all air route endpoints
	Point points[52]; // Max 50 air_routes
	int n = 0;

	// Add start and end
	points[n++] = (Point){x1, y1};
	points[n++] = (Point){x2, y2};

	// Add all air route endpoints
	for (int i = 0; i < air_route_count; i++) {
		points[n++] = (Point){air_routes[i].from_x, air_routes[i].from_y};
		points[n++] = (Point){air_routes[i].to_x, air_routes[i].to_y};
		// Avoid duplicates? But n is small so it's okay to have duplicates.
	}

	// Build adjacency list for the graph of n nodes
	AdjList *graph = malloc(n * sizeof(AdjList));
	for (int i = 0; i < n; i++) {
		graph[i].edges = NULL;
		graph[i].count = 0;
		graph[i].capacity = 0;
	}

	// WARN: Can be optimezed by adding less edges and correcting duplicates

	// Add walking edges between every pair of nodes
	for (int i = 0; i < n; i++) {
		for (int j = i + 1; j < n; j++) {
			int d = hex_distance(points[i].x, points[i].y, points[j].x,
								 points[j].y);
			// Add edge i->j and j->i with cost d
			// For i->j
			if (graph[i].count == graph[i].capacity) {
				graph[i].capacity =
					graph[i].capacity ? graph[i].capacity * 2 : 4;
				graph[i].edges =
					realloc(graph[i].edges, graph[i].capacity * sizeof(Edge));
			}
			graph[i].edges[graph[i].count++] = (Edge){j, d};

			// For j->i
			if (graph[j].count == graph[j].capacity) {
				graph[j].capacity =
					graph[j].capacity ? graph[j].capacity * 2 : 4;
				graph[j].edges =
					realloc(graph[j].edges, graph[j].capacity * sizeof(Edge));
			}
			graph[j].edges[graph[j].count++] = (Edge){i, d};
		}
	}

	// Add air route edges: for each air route, find the indices of the from and
	// to points
	for (int i = 0; i < air_route_count; i++) {
		int from_index = -1, to_index = -1;
		for (int j = 0; j < n; j++) {
			if (points[j].x == air_routes[i].from_x &&
				points[j].y == air_routes[i].from_y) {
				from_index = j;
			}
			if (points[j].x == air_routes[i].to_x &&
				points[j].y == air_routes[i].to_y) {
				to_index = j;
			}
		}
		if (from_index != -1 && to_index != -1) {
			// Add edge from_index -> to_index with cost 1
			if (graph[from_index].count == graph[from_index].capacity) {
				graph[from_index].capacity =
					graph[from_index].capacity ? graph[from_index].capacity * 2
											   : 4;
				graph[from_index].edges =
					realloc(graph[from_index].edges,
							graph[from_index].capacity * sizeof(Edge));
			}
			graph[from_index].edges[graph[from_index].count++] =
				(Edge){to_index, 1};
		}
	}

	// Now run Dijkstra from node0 (start) to node1 (end)
	int *dist = malloc(n * sizeof(int));
	for (int i = 0; i < n; i++)
		dist[i] = INT_MAX;
	dist[0] = 0;

	MinHeap *heap = create_min_heap(n * n);
	push(heap, 0, 0, 0); // Using x as node index, y unused, cost

	while (!is_empty(heap)) {
		Node node = pop(heap);
		int u = node.x;
		if (u == 1)
			break; // Reached end

		for (int i = 0; i < graph[u].count; i++) {
			int v = graph[u].edges[i].node_index;
			int cost_uv = graph[u].edges[i].cost;
			int new_cost = dist[u] + cost_uv;
			if (new_cost < dist[v]) {
				dist[v] = new_cost;
				push(heap, v, 0, new_cost);
			}
		}
	}

	int result = dist[1];

	// Cleanup
	for (int i = 0; i < n; i++) {
		free(graph[i].edges);
	}
	free(graph);
	free(dist);
	free(heap->data);
	free(heap);

	return result;
}
// ================= ^^^^ Dijkstra Algorithms ^^^^  ==================
//
// ================= vvvv Logic for splitting the map into regions of
// unreachability vvvv ================== Initialize region information
void free_region_info() {
	if (region_info != NULL) {
		for (int x = 0; x < W; x++) {
			free(region_info[x]);
		}
		free(region_info);
	}
}

void init_region_info() {
	region_info = malloc(W * sizeof(RegionInfo *));
	for (int x = 0; x < W; x++) {
		region_info[x] = malloc(H * sizeof(RegionInfo));
		for (int y = 0; y < H; y++) {
			region_info[x][y].forward_label = 0;
			region_info[x][y].backward_label = 0;
			region_info[x][y].visited = 0;
		}
	}

	current_forward_label = 1;
	current_backward_label = 1;
}

// Floodfill to mark reachable regions (BFS)
void floodfill(int start_x, int start_y, int is_forward, uint32_t label) {
	if (!in_bounds(start_x, start_y) ||
		(hive[start_x][start_y].cost == 0 && is_forward)) {
		return;
	}

	// Use a queue for BFS
	int *queue_x = malloc(W * H * sizeof(int));
	int *queue_y = malloc(W * H * sizeof(int));
	int front = 0, rear = 0;

	// Mark and enqueue starting cell
	if (is_forward) {
		region_info[start_x][start_y].forward_label |= label;
	} else {
		region_info[start_x][start_y].backward_label |= label;
	}
	region_info[start_x][start_y].visited = 1;
	queue_x[rear] = start_x;
	queue_y[rear] = start_y;
	rear++;

	while (front < rear) {
		int x = queue_x[front];
		int y = queue_y[front];
		front++;

		Cell cell = hive[x][y];

		const NeighborOffsets *offsets =
			(y % 2 == 0) ? &even_offsets : &odd_offsets;
		// Explore hexagonal neighbors
		for (int d = 0; d < 6; d++) {
			int nx = x + offsets->dx[d];
			int ny = y + offsets->dy[d];

			if (!in_bounds(nx, ny) || hive[nx][ny].cost == 0 ||
				region_info[nx][ny].visited) {
				continue;
			}
			// HACK: Even in the forward direction, we do not visit cell with 0
			// since we cannot exit from them.

			// Mark and enqueue
			if (is_forward) {
				region_info[nx][ny].forward_label |= label;
			} else {
				region_info[nx][ny].backward_label |= label;
			}
			region_info[nx][ny].visited = 1;
			queue_x[rear] = nx;
			queue_y[rear] = ny;
			rear++;
		}

		// Explore air routes
		if (is_forward && cell.air_out_degree > 0) {
			for (int i = 0; i < air_route_count; i++) {
				if (air_routes[i].from_x == x && air_routes[i].from_y == y) {
					int nx = air_routes[i].to_x;
					int ny = air_routes[i].to_y;

					if (!in_bounds(nx, ny) || hive[nx][ny].cost == 0 ||
						region_info[nx][ny].visited) {
						continue;
					}

					region_info[nx][ny].forward_label |= label;
					region_info[nx][ny].visited = 1;
					queue_x[rear] = nx;
					queue_y[rear] = ny;
					rear++;
				}
			}
		} else if (!is_forward && cell.air_in_degree > 0) {
			for (int i = 0; i < air_route_count; i++) {
				if (air_routes[i].to_x == x && air_routes[i].to_y == y) {
					int nx = air_routes[i].from_x;
					int ny = air_routes[i].from_y;

					if (!in_bounds(nx, ny) || hive[nx][ny].cost == 0 ||
						region_info[nx][ny].visited) {
						continue;
					}

					region_info[nx][ny].backward_label |= label;
					region_info[nx][ny].visited = 1;
					queue_x[rear] = nx;
					queue_y[rear] = ny;
					rear++;
				}
			}
		}
	}

	// Reset visited flags
	for (int i = 0; i < rear; i++) {
		region_info[queue_x[i]][queue_y[i]].visited = 0;
	}

	free(queue_x);
	free(queue_y);
}

int are_cells_disconnected(int x1, int y1, int x2, int y2) {
	if (!in_bounds(x1, y1) || !in_bounds(x2, y2) || hive[x1][y1].cost == 0) {
		return 1;
	}

	uint32_t forward_label = region_info[x1][y1].forward_label;
	uint32_t backward_label = region_info[x2][y2].backward_label;
	uint32_t overlap = forward_label & backward_label;

	return !(overlap == 0);
}
// ================= ^^^^ Logic for splitting the map into regions of
// unreachability ^^^^  ==================

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

	if (change_points != NULL)
		free(change_points);

	free_region_info();

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

	air_routes = NULL;
	air_route_count = 0;
	air_route_capacity = 0;

	change_points = NULL;
	change_point_count = 0;
	change_point_capacity = 0;

	init_region_info();

	DEBUG_PRINT("Allocated and initialized Hive\n");

	printf("OK\n");
}

void parse_change_cost(int x0, int y0, int v, int R) {
	DEBUG_PRINT(
		"Changing costs of cells centered around (%d, %d) with rad %d.\n", x0,
		y0, R);

	if (R == 0) {
		DEBUG_PRINT("Radius is 0.\n");
		printf("KO\n");
		return;
	}

	if (!in_bounds(x0, y0)) {
		DEBUG_PRINT("Out of Bounds.\n");
		printf("KO\n");
		return;
	}

	if (v > 10 || v < -10 || R < 0) {
		DEBUG_PRINT("Wrong input data.\n");
		printf("KO\n");
		return;
	}

	if (change_point_count == change_point_capacity) {
		change_point_capacity =
			change_point_capacity ? change_point_capacity * 2 : 16;
		change_points =
			realloc(change_points, change_point_capacity * sizeof(changePoint));
	}
	change_points[change_point_count++] = (changePoint){x0, y0, R};

	// Invalidate region labels since connectivity might have changed
	if (v > 1) {
		free_region_info();
		init_region_info();
		// TODO: Free only if one cell goes from 0 to a non zero value.
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

	printf("OK\n");
}

void parse_travel_cost(int x1, int y1, int x2, int y2) {

	DEBUG_PRINT("Travel from (%d, %d) to (%d, %d)\n", x1, y1, x2, y2);

	if (!in_bounds(x1, y1) || !in_bounds(x2, y2)) {
		DEBUG_PRINT("Out of Bounds\n");
		printf("%d\n", -1);
		return;
	}

	// First check if cells are in disconnected regions
	if (are_cells_disconnected(x1, y1, x2, y2)) {
		DEBUG_PRINT("Cells are in disconnected regions\n");
		printf("%d\n", -1);
		return;
	}

	// If the map has only ones, we can optimize
	int r;
	if (change_point_count == 0) {
		r = only_ones_dijkstra(x1, y1, x2, y2);
	} else {
		r = bidirectional_dijkstra(x1, y1, x2, y2);
	}

	if (r == -1) {
		uint32_t forward_label = current_forward_label;
		uint32_t backward_label = current_backward_label;

		floodfill(x1, y1, 1, forward_label);
		floodfill(x2, y2, 0, backward_label);

		// Update labels for next use (cycle through 32 bits)
		current_forward_label =
			(current_forward_label << 1) | (current_forward_label >> 31);
		current_backward_label =
			(current_backward_label << 1) | (current_backward_label >> 31);

		region_info[x1][y1].forward_label |= forward_label;
		region_info[x2][y2].backward_label |= backward_label;
	}

	printf("%d\n", r);
}

void parse_toggle_air_route(int x1, int y1, int x2, int y2) {

	DEBUG_PRINT("Toggle air route from (%d, %d) to (%d, %d)\n", x1, y1, x2, y2);

	if (!in_bounds(x1, y1) || !in_bounds(x2, y2)) {
		DEBUG_PRINT("Out of Bounds\n");
		printf("KO\n");
		return;
	}

	free_region_info();
	init_region_info();

	// TODO: Change only the connected air_route.

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
		printf("OK\n");
		return;
	}

	if (cell->air_out_degree >= MAX_AIR_ROUTES) {
		DEBUG_PRINT("Too many exiting air routes\n");
		printf("KO\n");
		return;
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
	printf("OK\n");
}

void parse_input() {
	char cmd[32];
#ifdef DEBUG
	int line = 1;
#endif

	while (scanf("%31s", cmd) == 1) {
#ifdef DEBUG
		DEBUG_PRINT("==== Line %d ==== \n", line++);
#endif

		if (strcmp(cmd, "init") == 0) {
			int w, h;
			if (scanf("%d %d", &w, &h) != 2) {
				fprintf(stderr, "Error reading init parameters\n");
				exit(EXIT_FAILURE);
			}
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
			parse_travel_cost(x1, y1, x2, y2);
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
	return 0;
}
