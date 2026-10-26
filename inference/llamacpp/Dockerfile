ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE} AS build
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake && rm -rf /var/lib/apt/lists/*
COPY source.tar.gz /tmp/source.tar.gz
ARG SOURCE_SHA256
ARG SOURCE_COMMIT
RUN printf '%s  /tmp/source.tar.gz\n' "$SOURCE_SHA256" | sha256sum -c - && mkdir /src && tar -xzf /tmp/source.tar.gz --strip-components=1 -C /src
RUN cmake -S /src -B /build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=ON -DGGML_CUDA=OFF -DGGML_OPENMP=OFF -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON -DLLAMA_BUILD_IS_DEV=OFF -DLLAMA_BUILD_COMMIT="$SOURCE_COMMIT" && cmake --build /build --target llama-server -j 12
FROM ${PYTHON_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
COPY --from=build /build/bin/llama-server /usr/local/bin/llama-server
ENTRYPOINT ["/usr/local/bin/llama-server"]
