#!/usr/bin/env python3
import argparse
import docker
import os
import time
from pathlib import Path

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
SETUP_CMD = "mkdir -p /opt/shogun"
CMAKE_CMD = "cd {}; rm -rf *; cmake -DCMAKE_INSTALL_PREFIX=$HOME/shogun-build -DENABLE_TESTING=ON {} /opt/shogun"
BUILD_CMD = "cd {}; make -j4"
VALGRIND_CMD = "cd {}; valgrind --leak-check=full bin/shogun-unit-test"
CLEANUP_CMD = "rm -rf {}"

def write_to_file(file, output, mode):
	code = output[0]
	stream = output[1]
	with open(file, mode) as f:
		for line in stream:
			f.write(line)
			f.flush()

def main(client, args):
	path = args.path
	container_name = args.container[0]
	# generate name of directory to store results
	result_path = f"build-{int(time.time())}" if args.result_path == '' else args.result_path
	current_dir = os.path.abspath('./')

	# if image doesn't exist build it
	if IMAGE_NAME not in [img.tags[0] for img in client.images.list()]:
		print("Building image...")
		img, logs = client.images.build(path=current_dir, tag=IMAGE_NAME, rm=True)

	else:
		print("Getting image locally")
		img = client.images.get(IMAGE_NAME)

	os.mkdir(result_path)

	for i, cmake_config in enumerate(CMAKE_CONFIG):

		print(f"CONFIGURATION {i}")

		result_path_i = f"{current_dir}/{result_path}/config-{i}"

		os.mkdir(result_path_i)
		os.mkdir(f"{result_path_i}/build")
		mount_build_path = f"/opt/{result_path}/build"

		# docker volumes
		volumes = {f"{Path.home()}/.ccache": {"bind":"/root/.ccache"}, 
				   path: {"bind":"/opt/shogun"},
				   f"{result_path_i}/build":{"bind":mount_build_path}
				   }

		# if container hasn't been started yet start it here
		print("Starting container")
		try:
			container = client.containers.create(img.short_id, volumes=volumes, name=container_name, detach=True, tty=True)
		except Exception as e:
			print(f"An error occured whilst creating the container:\n{e}\nAborting.")
			return
		container.start()
		container.exec_run(cmd=f"bash -c '{SETUP_CMD}'")

		write_to_file(os.path.join(result_path_i, "cmake_config.txt"), (0, [cmake_config, '\n']), 'w')
		
		print("Running cmake step...", end=" ", flush=True)
		start = time.time()
		cmake_logs = container.exec_run(cmd=f"bash -c '{CMAKE_CMD.format(mount_build_path, cmake_config)}'", stream=True)
		write_to_file(os.path.join(result_path_i, "cmake_output.txt"), cmake_logs, 'wb')
		print(f"[time: {time.time() - start:.2f} s]")
		
		print("Running build step...", end=" ", flush=True)
		start = time.time()
		build_logs = container.exec_run(cmd=f"bash -c '{BUILD_CMD.format(mount_build_path)}'", stream=True)
		write_to_file(os.path.join(result_path_i, "build_output.txt"), build_logs, 'wb')
		print(f"[time: {time.time() - start:.2f} s]")

		print("Running valgrind step...", end=" ", flush=True)
		start = time.time()
		valgrind_logs = container.exec_run(cmd=f"bash -c '{VALGRIND_CMD.format(mount_build_path)}'", stream=True)
		write_to_file(os.path.join(result_path_i, "valgrind_output.txt"), valgrind_logs, 'wb')
		print(f"[time: {time.time() - start:.2f} s]")

		print("Running clean up step...", end=" ", flush=True)
		start = time.time()
		container.exec_run(cmd=f"bash -c '{CLEANUP_CMD.format(mount_build_path)}'")
		print(f"[time: {time.time() - start:.2f} s]")

		container.stop()
		container.remove()

if __name__ == '__main__':
	args = parser.parse_args()
	client = docker.from_env()

	try:
		main(client, args)
	except:
		print("Stopping and deleting docker container...")
		try:
			container = client.containers.get(args.container[0])
			container.stop()
			container.remove()
		except Exception as e:
			print("Could not stop and delete container", e)