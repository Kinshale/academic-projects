F ?= main.c
I ?= input.txt
O ?= output.txt

build: # compile with -O2 optimization (balanced speed and size)
	gcc -Wall -Wextra -std=gnu11 -O2 $(F) -lm

run: # Also runs the code with the input
	gcc -Wall -Wextra -std=gnu11 -O2 $(F) -lm
	./a.out <$(I) >$(O)

debug: # Shows the debug prints
	gcc -DDEBUG -Wall -Wextra -std=gnu11 -O2 $(F) -lm
	./a.out <$(I) >$(O)

optimize: # compiles with -O3 (aggressive optimization) and -march=native (CPU-specific optimization).
	gcc -Wall -Wextra -std=gnu11 -march=native -O3 $(F) -lm
	./a.out <$(I) >$(O)

asan: # Compile with AddressSanitizer and UndefinedBehaviorSanitizer
	gcc -std=gnu11 -O0 -Wall -Werror -Wextra -fsanitize=address,undefined -g3 $(F) -lm
	./a.out <$(I) >$(O)

valgrind:
	gcc -std=gnu11 -O0 -Wall -Werror -Wextra -g3 $(F) -lm
	valgrind --show-error-list=yes --leak-check=full --show-leak-kinds=all --track-origins=yes ./a.out <$(I) >$(O)

callgrind:
	gcc -std=gnu11 -O2 -Wall -Werror -Wextra -g3 $(F) -lm
	valgrind --tool=callgrind ./a.out <$(I) >$(O)

clean:
	rm -f a.out
	rm -f callgrind.out.*
	rm -f massif.out.*
	rm -f vgcore.*
