#!/usr/bin/env python3
import argparse
import docker
import os
import time
from pathlib import Path
import yaml

# argument parsing
parser = argparse.ArgumentParser(description=
	"""
	Tool to build and test different cmake configurations for shogun
	on any platform that supports Docker.
	This tool does not install or start Docker, this has to be done manually.
	The Dockerfile of this project is the same one as the official shogun
	Dockerfile, but also includes valgrind.
	""")
parser.add_argument('config_file', type=str, nargs=1,
					help='YAML configuration file with cmake flags')
parser.add_argument('--container', type=str, nargs='?', default="shogun-memory",
					help='name of docker container')
parser.add_argument('--path', type=str, nargs='?', default='./',
					help='local path to shogun')
parser.add_argument('--result_path', type=str, nargs='?', default='',
					help='path where logs will be stored')
parser.add_argument('--gtest_filter', type=str, nargs='?', default='*',
					help="gtest_filter argument passed on to gtest when running valgrind")
keep_build_parser = parser.add_mutually_exclusive_group(required=False)
keep_build_parser.add_argument('--keep_build', dest='keep_build', 
								action='store_true', 
								help="keep build. Requires bindings between host and container, which can slow down build time.")
keep_build_parser.add_argument('--discard_build', dest='keep_build', action='store_false',
								help="[EXPERIMENTAL] do not keep build. Uses a temporary directory (with docker's tmpfs), which improves build time.")
parser.set_defaults(feature=True)

NAME = "shogun-memory-test"
VERSION = 0.1
IMAGE_NAME = f"{NAME}:{VERSION}"

# bash commands
SETUP_CMD = "mkdir -p /opt/shogun; CCACHE_DIR=/shogun-ccache"
CMAKE_CMD = "cd {}; cmake -DCMAKE_INSTALL_PREFIX=$HOME/shogun-build -DENABLE_TESTING=ON {} /opt/shogun"
BUILD_CMD = "cd {}; make -j4"
VALGRIND_CMD = "cd {}; valgrind --leak-check=full bin/shogun-unit-test --gtest_filter={}"
CLEANUP_CMD = "rm -rf {}"

def write_to_file(file, output, mode, timeit=True):
	code = output[0]
	stream = output[1]
	start = time.time()	
	with open(file, mode) as f:
		for line in stream:
			f.write(line)
			f.flush()
	if timeit:
		print(f"[time: {time.time() - start:.2f} s]")

def main(client, args):
	path = args.path
	container_name = args.container
	# generate name of directory to store results
	result_path = f"build-{int(time.time())}" if args.result_path == '' else args.result_path
	current_dir = os.path.abspath('./')
	gtest_filter = args.gtest_filter
	yaml_config_file = args.config_file[0]
	keep_build = args.keep_build

	# if image doesn't exist build it
	if IMAGE_NAME not in [img.tags[0] for img in client.images.list()]:
		print("Building image (could take a while)...")
		img, logs = client.images.build(path=current_dir, tag=IMAGE_NAME, rm=True)

	else:
		print("Getting image locally")
		img = client.images.get(IMAGE_NAME)

	try:
		os.mkdir(result_path)
	except FileExistsError:
		pass

	configs = yaml.load(open(yaml_config_file, 'r'))['configs']

	for config in configs:

		config_name = config["name"]
		cmake_config = config["config"]

		print(f"CONFIGURATION: '{config_name}'")

		result_path_i = f"{current_dir}/{result_path}/config-{config_name}"

		os.mkdir(result_path_i)
		mount_build_path = f"/opt/{result_path}/build"

		# build or get ccache volume
		try:
			ccache_volume = client.volumes.get("shogun-ccache")
		except docker.errors.NotFound:
			ccache_volume = client.volumes.create("shogun-ccache")

		mounts = [
			docker.types.Mount(target="/root/.ccache", source=ccache_volume.id, type="volume"),
			docker.types.Mount(target="/opt/shogun", source=path, type='bind'),
		]

		if keep_build:
			os.mkdir(f"{result_path_i}/build")
			mounts.append(docker.types.Mount(target=mount_build_path, source=f"{result_path_i}/build", type='bind'))
			tmpfs = {}
		else:
			tmpfs = {mount_build_path: 'exec'}

		print("Starting container")
		try:
			container = client.containers.create(img.short_id, mounts=mounts, name=container_name, detach=True, tty=True, tmpfs=tmpfs)
		except docker.errors.APIError:
			answer = input(f"A container named '{container_name}' already exists. Would you like to stop and delete it? [y/N] ").lower()
			if answer == 'y':
				container = client.containers.get(container_name)
				container.stop()
				container.remove()
				container = client.containers.create(img.short_id, mounts=mounts, name=container_name, detach=True, tty=True,  tmpfs=tmpfs)
			elif answer=='n' or answer=='':
				print("Aborting.")
				return
			else:
				print('Invalid answer.')
				return
		except Exception as e:
			print(f"An error occured whilst creating the container:\n{e}\nAborting.")
			return
		container.start()
		container.exec_run(cmd=f"bash -c '{SETUP_CMD}'")

		write_to_file(os.path.join(result_path_i, "cmake_config.txt"), (0, [cmake_config, '\n']), 'w', timeit=False)
		
		print("Running cmake step...", end=" ", flush=True)
		cmake_logs = container.exec_run(cmd=f"bash -c '{CMAKE_CMD.format(mount_build_path, cmake_config)}'", stream=True)
		write_to_file(os.path.join(result_path_i, "cmake_output.txt"), cmake_logs, 'wb')
		
		print("Running build step...", end=" ", flush=True)
		build_logs = container.exec_run(cmd=f"bash -c '{BUILD_CMD.format(mount_build_path)}'", stream=True)
		write_to_file(os.path.join(result_path_i, "build_output.txt"), build_logs, 'wb')

		print("Running valgrind step...", end=" ", flush=True)
		valgrind_logs = container.exec_run(cmd=f"bash -c '{VALGRIND_CMD.format(mount_build_path, gtest_filter)}'", stream=True)
		write_to_file(os.path.join(result_path_i, "valgrind_output.txt"), valgrind_logs, 'wb')

		print("Running clean up step...", end=" ", flush=True)
		container.exec_run(cmd=f"bash -c '{CLEANUP_CMD.format(mount_build_path)}'")

		container.stop()
		container.remove()

if __name__ == '__main__':
	args = parser.parse_args()
	client = docker.from_env()

	try:
		main(client, args)
	except BaseException as e:
		print(f"An error occured:\n{e}")
		print("Stopping and deleting docker container...")
		try:
			container = client.containers.get(args.container)
			container.stop()
			container.remove()
		except Exception as e:
			print(f"Could not stop and delete container.\n{e}")