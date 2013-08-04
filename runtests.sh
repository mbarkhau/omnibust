#!/bin/bash
watchmedo shell-command -w --patterns=*.py \
	--command="py.test tests.py;python tests.py"
