# shogun-docker
A simple python script to test [Shogun](https://github.com/shogun-toolbox/shogun) locally with Docker. 

## Usage
```
cmake_configs.py shogun-memory-test --path LOCAL_SHOGUN_PATH --result-path PATH_TO_STORE_RESULTS
```

The first time the script runs will take longer as it builds the Docker image.
The results are stored in `--result-path` for the three steps:
- cmake 
- build
- valgrind
