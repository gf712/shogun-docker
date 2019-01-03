#!/usr/bin/env python3
import argparse
import docker
import os
import time

# argument parsing
parser = argparse.ArgumentParser(description=
	"""
	Tool to build and test different cmake configurations for shogun
	on any platform that supports Docker.
	This tool does not install or start Docker, this has to be done manually.
	The Dockerfile of this project is the same one as the official shogun
	Dockerfile, but also includes valgrind.
	""")
parser.add_argument('container', type=str, nargs=1,
                    help='name of docker container')
parser.add_argument('--path', type=str, nargs='?', default='./',
                    help='local path to shogun')
parser.add_argument('--result_path', type=str, nargs='?', default='',
                    help='path where logs will be stored')

# cmake configs
CMAKE_CONFIG = ["-DCMAKE_BUILD_TYPE=Debug -DBUILD_META_EXAMPLES=ON -DENABLE_ASAN=ON -DENABLE_MSAN=ON -DENABLE_TSAN=ON -DENABLE_UBSAN=ON",
				"-DCMAKE_BUILD_TYPE=Debug -DBUILD_META_EXAMPLES=ON"]

NAME = "shogun-memory-test"
VERSION = 0.1
IMAGE_NAME = f"{NAME}:{VERSION}"

# bash commands
SETUP_CMD = "mkdir /opt/shogun/build"
CMAKE_CMD = "cd /opt/shogun/build; cmake -DCMAKE_INSTALL_PREFIX=$HOME/shogun-build -DENABLE_TESTING=ON {} .."
BUILD_CMD = "cd /opt/shogun/build; make -j4"
VALGRIND_CMD = "cd /opt/shogun/build; valgrind --leak-check=full bin/shogun-unit-test"

def write_to_file(file, stream, mode):
	with open(file, mode) as f:
		for line in stream:
			f.write(line)
			f.flush()

def main(args):
	client = docker.from_env()
	path = args.path
	container_name = args.container[0]
	# generate name of directory to store results
	result_path = f"build-{time.time()}" if args.result_path == '' else args.result_path

	# docker volumes
	volumes = {"$HOME/.ccache": {"bind":"/root/.ccache"}, 
			   path: {"bind":"/opt/shogun"}}

	# if image doesn't exist build it
	if IMAGE_NAME not in [img.tags[0] for img in client.images.list()]:
		print("Building image...")
		img = client.images.build(path=os.path.abspath('./'), tag=IMAGE_NAME)[0]
	else:
		print("Getting image locally")
		img = client.images.get(IMAGE_NAME)

	# if container hasn't been started yet start it here
	if IMAGE_NAME not in [container.image.tags[0] for container in client.containers.list()]:
		print("Starting container")
		container = client.containers.start(img.short_id, command=f"bash -c '{SETUP_CMD}'", volumes=volumes, name=container_name)
	else:
		print("Getting container")
		container_id = next(container.id for container in client.containers.list() if container.image.tags[0]==IMAGE_NAME)
		container = client.containers.get(container_id)
		if container.name != container_name:
			container.rename(container_name)

	# run each cmake config
	for i, cmake_config in enumerate(CMAKE_CONFIG):
		print(f"CONFIGURATION {i}")

		os.mkdir(result_path)

		write_to_file(os.path.join(result_path, "cmake_config.txt"), [cmake_config, '\n'], 'w')
		
		print("Running cmake step")
		cmake_logs = container.exec_run(cmd=f"bash -c '{CMAKE_CMD.format(cmake_config)}'", stream=True)
		write_to_file(os.path.join(result_path, "cmake_output.txt"), cmake_logs.output, 'wb')
		
		print("Running build step")
		build_logs = container.exec_run(cmd=f"bash -c '{BUILD_CMD}'")
		write_to_file(os.path.join(result_path, "build_output.txt"), build_logs.output, 'wb')

		print("Running valgrind test")
		valgrind_logs = container.exec_run(cmd=f"bash -c '{VALGRIND_CMD}'")
		write_to_file(os.path.join(result_path, "valgrind_output.txt"), valgrind_logs.output, 'wb')

if __name__ == '__main__':
	args = parser.parse_args()
	main(args)
