# shogun-docker
A simple python script to test [Shogun](https://github.com/shogun-toolbox/shogun) locally with Docker. 

## Usage
```
cmake_configs.py config.yml --path LOCAL_SHOGUN_PATH --result-path PATH_TO_STORE_RESULTS
```
The cmake flags to run for each build are stored in a YAML file (only need to have a name and the cmake flags, see config.yml)

The first time the script runs will take longer as it builds the Docker image.

The results are stored in `--result-path` for the three steps:
- cmake 
- build
- valgrind

To follow the progress of the run you can stream the log files on the terminal with `tail -f FILE`.

If you only want to run specific tests you can pass arguments directly to gtest_filter with `--gtest_filter`
