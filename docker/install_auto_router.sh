#!/bin/bash
pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
pip config set global.trusted-host mirrors.aliyun.com
pip install semantic_router==0.1.11 --no-deps
pip install aurelio-sdk==0.0.19