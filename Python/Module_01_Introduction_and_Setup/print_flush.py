import time
import sys

print("--- TESTING WITHOUT FLUSH ---")
for i in range(10):
    print(".", end="")  # No newline, data sits in the memory buffer
    time.sleep(0.5)     # You will see NOTHING for 2.5 seconds, then all dots appear at once
print("\nDone")

print("--- TESTING WITH FLUSH ---")
for i in range(10):
    print(".", end="", flush=True)  # Forces data out of memory instantly
    time.sleep(0.5)                 # You will see one dot appear every 0.5 seconds
print("\nDone")

## - ASCII / Latin-1 (e.g., a, 1, $): Uses 1 byte per character plus a 49-byte overhead. (4,047 characters = 4,096 bytes i.e., 4 KB)

# print("--- TESTING WITHOUT FLUSH ---")
# for i in range(20):
#     print(1000*"."+100*"-", end="")  # No newline, data sits in the memory buffer
#     time.sleep(0.5)     # You will see NOTHING for 2.5 seconds, then all dots appear at once
# print("\nDone")

# print("--- TESTING WITH FLUSH ---")
# for i in range(20):
#     print(1000*"."+100*"-", end="", flush=True)  # Forces data out of memory instantly
#     time.sleep(0.5)                 # You will see one dot appear every 0.5 seconds
# print("\nDone")