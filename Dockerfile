# --- STAGE 1: Builder (Compiles C++) ---
FROM python:3.11-slim AS builder

# 1. Install System Compilers
RUN apt-get update && apt-get install -y \
    cmake \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Pybind11
RUN pip install --no-cache-dir pybind11

# 3. Copy C++ Source
WORKDIR /build
COPY cpp_engine/ ./cpp_engine/

# 4. Clean & Build
RUN rm -rf cpp_engine/build && mkdir -p cpp_engine/build
WORKDIR /build/cpp_engine/build

# 5. Compile for Linux
# Added -Wno-dev to suppress warnings
RUN cmake .. \
    -DPYTHON_EXECUTABLE=$(which python3) \
    -Dpybind11_DIR=$(python3 -m pybind11 --cmakedir) \
    -Wno-dev \
    && make

# --- STAGE 2: Runner (Runs Python App) ---
FROM python:3.11-slim

WORKDIR /app

# 1. Install System Dependencies
RUN apt-get update && apt-get install -y \
    libpq-dev \
    libstdc++6 \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# 2. Install Python Dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. Copy Code Structure
COPY backend/ ./backend/
COPY frontend/ ./frontend/

# 4. Copy Compiled C++ Engine
COPY --from=builder /build/cpp_engine/build/recommender*.so /usr/local/lib/python3.11/site-packages/

# 5. Set Working Directory
WORKDIR /app/backend

# 6. Expose Port 8000
EXPOSE 8000

# 7. DIRECT COMMAND 
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]