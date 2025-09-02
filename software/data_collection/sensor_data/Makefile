# Makefile

# Compiler settings
CXX = g++
CXXFLAGS = -std=c++17 -O3

# Libraries
LIBS = -lrealsense2
CVLIBS = `pkg-config --cflags --libs opencv4` -lGL -lglfw -lGLU

# Default target
all: collector

collector: collector.cpp
	$(CXX) $(CXXFLAGS) -o collector collector.cpp $(LIBS) $(CVLIBS)

# Clean up
clean:
	rm -f cv collector test
