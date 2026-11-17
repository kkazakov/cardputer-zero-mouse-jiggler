#!/bin/bash

docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/src" -w /src \
  ubuntu:24.04 ./packaging/build-deb.sh